from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import time
from importlib.metadata import version as pkg_version
from collections import defaultdict
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.config import INDEX_SYMBOLS, SECTOR_BY_SYMBOL, settings
from app.data.news import NewsService
from app.data.trading_calendar import session_state
from app.data.yahoo import YahooDataError, YahooProvider
from app.ml.features import FEATURES, build_features, explain_row, prepare_training_frame, regime_from_row
from app.ml.model import CandleModel
from app.services.db import audit, journal_signal, save_model_run
from app.services.repository import RepositoryMonitor

class AnalysisEngine:
    def __init__(self, market: YahooProvider, news: NewsService, repo: RepositoryMonitor):
        self.market = market
        self.news = news
        self.repo = repo
        self.models: dict[tuple[str,str,str], CandleModel] = {}
        self.training_bucket: dict[tuple[str,str,str], str] = {}
        self.snapshots: dict[tuple[str,str,str], dict[str,Any]] = {}
        self.locks: dict[tuple[str,str,str], threading.RLock] = defaultdict(threading.RLock)
        self._repo_cache: dict[str, tuple[float,dict[str,Any]]] = {}
        self._repo_cache_seconds=2
        self._context_cache: dict[tuple[str,int],tuple[float,dict[str,pd.DataFrame]]] = {}
        self._context_cache_seconds=300

    def invalidate_repository_cache(self, session_id: str = "model") -> None:
        self._repo_cache.pop(session_id,None)

    @staticmethod
    def _dataset_fingerprint(frame: pd.DataFrame) -> str:
        sample=frame[["timestamp","open","high","low","close","volume"]].tail(3000).copy()
        return hashlib.sha256(sample.round(8).to_csv(index=False).encode()).hexdigest()

    @staticmethod
    def _training_bucket(snapshot) -> str:
        # A new model is not retrained for every incoming candle. It refreshes on a
        # configurable cadence or after an explicit retrain/environment change.
        ts=pd.Timestamp(snapshot.latest_timestamp)
        minutes=max(1,settings.model_refresh_minutes)
        epoch=int(ts.timestamp()//(minutes*60))
        return f"{epoch}:{snapshot.source}:{snapshot.data_status}"

    def _repo_state(self, repo_monitor: RepositoryMonitor) -> dict[str,Any]:
        sid=repo_monitor.session_id
        now=time.time()
        hit=self._repo_cache.get(sid)
        if hit and now-hit[0] < self._repo_cache_seconds:
            return hit[1]
        state=repo_monitor.scan(False,record_audit=False)
        self._repo_cache[sid]=(now,state)
        return state

    def _context(self, interval:str, days:int) -> dict[str,pd.DataFrame]:
        key=(interval,int(days))
        now=time.time()
        hit=self._context_cache.get(key)
        if hit and now-hit[0] < self._context_cache_seconds:
            return hit[1]
        out={}
        for name,symbol in INDEX_SYMBOLS.items():
            try:
                context_days = 900 if interval == "1d" else min(days,60)
                snap=self.market.history(symbol,interval,days=context_days)
                out[name]=snap.frame[["timestamp","close"]].copy()
            except Exception:
                out[name]=pd.DataFrame()
        self._context_cache[key]=(now,out)
        return out

    @staticmethod
    def _prediction_environment_fingerprint(repo:dict[str,Any])->str:
        if repo.get("scope")!="model": return ""
        accepted=repo.get("accepted")
        current=repo.get("current") or {}
        source=accepted if repo.get("state")=="STALE" and accepted else current
        comps=source.get("components") or {}
        payload={k:comps.get(k,"") for k in ("model","services","data","dependencies","config")}
        package_versions={}
        for package in ("numpy", "pandas", "scikit-learn", "scipy", "yfinance"):
            try:
                package_versions[package]=pkg_version(package)
            except Exception:
                package_versions[package]="unknown"
        payload["installed_packages"]=package_versions
        if not any(payload.values()): return ""
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()

    def _artifact_path(self,symbol,interval,env_fp):
        safe=re.sub(r"[^A-Za-z0-9_.-]","_",symbol)
        return settings.runtime_dir/"models"/f"{safe}_{interval}_{env_fp[:12]}.joblib"

    def _artifact_sign(self,path:Path)->str:
        key=settings.model_artifact_key.encode()
        if not key: return ""
        return hmac.new(key,path.read_bytes(),hashlib.sha256).hexdigest()

    def _load_artifact(self,path:Path):
        if not settings.model_artifact_key or not path.exists():
            return None
        sig=path.with_suffix(path.suffix+".sig")
        if not sig.exists(): return None
        try:
            expected=self._artifact_sign(path)
            actual=sig.read_text(encoding="utf-8").strip()
            if not hmac.compare_digest(expected,actual): return None
            return joblib.load(path)
        except Exception:
            return None

    def _save_artifact(self,path:Path,model):
        if not settings.model_artifact_key: return
        try:
            joblib.dump(model,path,compress=3)
            path.with_suffix(path.suffix+".sig").write_text(self._artifact_sign(path),encoding="utf-8")
        except Exception:
            pass

    def _get_model(self,snapshot,repo_state,force_retrain=False):
        env_fp=self._prediction_environment_fingerprint(repo_state)
        key=(snapshot.resolved_symbol,snapshot.interval,env_fp)
        bucket=self._training_bucket(snapshot)
        if not force_retrain and key in self.models and self.training_bucket.get(key)==bucket:
            return self.models[key],False,"cache",env_fp

        path=self._artifact_path(snapshot.resolved_symbol,snapshot.interval,env_fp or "none")
        if not force_retrain and self.training_bucket.get(key)!=bucket:
            loaded=self._load_artifact(path)
            if loaded is not None and getattr(loaded,"report",None):
                self.models[key]=loaded; self.training_bucket[key]=bucket
                return loaded,False,"disk-cache",env_fp

        days=self.market.training_days(snapshot.interval)
        context=self._context(snapshot.interval,min(days,60))
        train=prepare_training_frame(snapshot.frame,context=context)
        is_daily = snapshot.interval == "1d"
        min_rows = settings.min_train_rows_daily if is_daily else settings.min_train_rows
        if len(train)<min_rows:
            raise ValueError(
                f"Not enough clean training rows for {snapshot.symbol} at {snapshot.interval}. "
                f"Need {min_rows}, have {len(train)}. "
                "For daily data the engine uses an adapted warm-up window; for intraday data Yahoo retention may limit history."
            )
        model=CandleModel(min_train_rows=min_rows)
        model.fit(
            train, FEATURES, dataset_fingerprint=self._dataset_fingerprint(snapshot.frame),
            environment_fingerprint=env_fp,
            min_signal_count=(settings.min_signal_count_daily if is_daily else settings.min_signal_count),
            min_validation_rows=(15 if is_daily else 30),
            min_calibration_rows=(15 if is_daily else 30),
        )
        self.models[key]=model; self.training_bucket[key]=bucket
        self._save_artifact(path,model)
        save_model_run(snapshot.symbol,snapshot.interval,model.report.model_version,model.report.public())
        audit("model-trained","ok",{"symbol":snapshot.symbol,"interval":snapshot.interval,"model_version":model.report.model_version,
                                   "precision":model.report.signal_precision,"gate_pass":model.report.gate_pass})
        return model,True,"forced-retrain" if force_retrain else "environment-or-scheduled-refresh",env_fp

    @staticmethod
    def _data_state(snapshot):
        latest=pd.Timestamp(snapshot.latest_timestamp).to_pydatetime()
        mins={"1m":1,"2m":2,"5m":5,"15m":15,"30m":30,"60m":60,"90m":90,"1h":60,"1d":1440}.get(snapshot.interval,60)
        if snapshot.source=="REPLAY":
            # Recorded last-session data is valid for inspection while the market is
            # closed. During an open session it is explicitly stale and cannot be trusted.
            if session_state() == "OPEN":
                status, ok = "STALE", False
            else:
                status, ok = "MARKET_CLOSED", True
        else:
            from app.data.trading_calendar import freshness_state
            status,ok=freshness_state(latest,mins)
        return status,ok

    @staticmethod
    def _risk(latest_row:pd.Series,prediction:dict[str,Any])->dict[str,Any]:
        atr_pct=float(latest_row.get("atr_pct",0.0) or 0.0)
        vol20=float(latest_row.get("volatility_20",0.0) or 0.0)
        realized=max(atr_pct,vol20*1.6)
        if realized<0.005: level,score="LOW",82
        elif realized<0.012: level,score="MODERATE",61
        elif realized<0.025: level,score="HIGH",38
        else: level,score="VERY HIGH",18
        stop_pct=max(realized*1.5,0.004)
        target_pct=max(abs(float(prediction.get("expected_return_pct",0)))/100*1.4,stop_pct*1.25)
        action=prediction.get("trading_action","HOLD")
        price=float(prediction["predicted_close"]/(1+float(prediction.get("expected_return_pct",0))/100))
        if action=="BUY":
            stop=price*(1-stop_pct); target=price*(1+target_pct); capital="BUY with risk limits"
        elif action=="SELL / EXIT":
            stop=price*(1+stop_pct); target=price*(1-target_pct); capital="SELL / EXIT existing position"
        else:
            stop=target=None; capital="HOLD"
        return {"level":level,"score":score,"atr_pct":round(atr_pct*100,3),"realized_volatility_pct":round(realized*100,3),
                "stop_loss":round(stop,2) if stop is not None else None,"take_profit":round(target,2) if target is not None else None,
                "risk_reward":round(target_pct/stop_pct,2) if stop_pct else 0.0,"capital_action":capital,
                "guidance":"Paper-analysis levels only; recheck live price/liquidity before any real order."}

    def analyze(self,symbol,interval,force_retrain=False,refresh_data=False,repo_monitor:RepositoryMonitor|None=None):
        if interval not in {"5m","15m","30m","60m","1d"}:
            raise ValueError("Choose 5m, 15m, 30m, 60m or 1d.")
        monitor=repo_monitor or self.repo
        lock_key=(monitor.session_id,symbol.upper(),interval)
        with self.locks[lock_key]:
            started=time.time()
            snap=self.market.history(symbol,interval,self.market.training_days(interval),refresh=refresh_data)
            repo_state=self._repo_state(monitor)
            model, retrained, cache_state, env_fp=self._get_model(snap,repo_state,force_retrain)
            days=self.market.training_days(interval)
            context=self._context(interval,min(days,60))
            live=build_features(snap.frame,context=context).dropna(subset=FEATURES)
            if live.empty: raise ValueError("Not enough clean rows for feature generation.")
            latest=live.iloc[[-1]]
            price=float(latest.close.iloc[0])
            regime=regime_from_row(latest.iloc[0],live)
            data_state,data_current=self._data_state(snap)
            model_bound=repo_state.get("scope")=="model"
            repo_current=repo_state.get("state")=="CURRENT" if model_bound else True
            value_traded=float((latest.close.iloc[0]*latest.volume.iloc[0]) if "volume" in latest.columns else 0)
            median_value=float((live.close*live.volume).tail(20).median())
            liquidity_ok=median_value >= settings.min_value_traded_inr
            articles=self.news.fetch(snap.resolved_symbol,snap.name,limit=8)
            news=self.news.aggregate(articles)
            prediction=model.predict(latest,price,news["impact"],regime,repo_current,data_current,session_state()=="OPEN",liquidity_ok)
            if repo_state.get("security_blocking") and model_bound:
                prediction["signal"]="REVALIDATE"; prediction["trading_action"]="REVALIDATE"
            if not liquidity_ok and prediction["signal"] not in {"REVALIDATE"}:
                prediction["signal"]="HOLD"; prediction["trading_action"]="HOLD"
            prediction["explanation"]=__import__("app.ml.features",fromlist=["explain_row"]).explain_row(latest.iloc[0],prediction["signal"],model.report.gate_pass)
            prediction["environment"]={
                "repository":repo_state["state"] if model_bound else "EXTERNAL AUDIT",
                "repository_scope":repo_state.get("scope","model"),"data":data_state,
                "model_gate":"PASS" if model.report.gate_pass else "FAIL","model_version":model.report.model_version,
                "training_seconds":model.report.training_seconds,"dataset_fingerprint":model.report.dataset_fingerprint[:16],
                "environment_fingerprint":env_fp[:16],"model_cache_state":cache_state,
                "repository_revalidation":repo_state.get("revalidation_required",False),
                "repository_security":"BLOCKED" if repo_state.get("security_blocking") and model_bound else "CLEAR",
                "liquidity":"PASS" if liquidity_ok else "LOW LIQUIDITY",
                "market_session":session_state(),
                "data_source":snap.source,
            }
            prediction["risk"]=self._risk(latest.iloc[0],prediction)
            prediction["trust"]=self.trust_score(model,repo_state,snap,data_current,regime,news["impact"],model_bound,liquidity_ok)
            last_ts=latest.timestamp.iloc[0]
            candles=snap.frame.tail(min(settings.max_candles_display,settings.chart_candles))
            result={
                "instrument":{"symbol":snap.symbol,"yahoo_symbol":snap.resolved_symbol,"name":snap.name,
                              "exchange":snap.exchange,"sector":SECTOR_BY_SYMBOL.get(snap.resolved_symbol.replace(".NS","").replace(".BO","").upper(),"Unknown")},
                "interval":interval,"current_price":price,"last_timestamp":last_ts.isoformat(),
                "data":{"status":data_state,"freshness_seconds":round(snap.freshness_seconds,1),"fetched_at":snap.fetched_at,
                        "history_rows":len(snap.frame),"training_rows":model.report.train_rows,"source":snap.source},
                "prediction":prediction,"news":{"summary":news,"articles":articles},"regime":regime,
                "model":model.report.public(),"model_operations":{"retrained":retrained,"training_seconds":model.report.training_seconds,
                    "model_version":model.report.model_version,"dataset_fingerprint":model.report.dataset_fingerprint[:16],
                    "environment_fingerprint":env_fp[:16],"cache_state":cache_state,"training_bucket":self._training_bucket(snap)},
                "backtest":model.backtest(),
                "candles":[{"time":r.timestamp.isoformat(),"open":float(r.open),"high":float(r.high),"low":float(r.low),
                            "close":float(r.close),"volume":float(r.volume)} for r in candles.itertuples()],
                "retrained":retrained,"elapsed_ms":round((time.time()-started)*1000,1),
                "paper_only":True,"liquidity":{"median_value_traded_inr":round(median_value,2),"minimum_value_traded_inr":settings.min_value_traded_inr,"ok":liquidity_ok},
            }
            journal_signal({"symbol":snap.resolved_symbol,"interval":interval,"candle_ts":last_ts.isoformat(),
                            "signal":prediction["signal"],"confidence":prediction["confidence"],"probability_up":prediction["probability_up"],
                            "precision":model.report.signal_precision,"model_version":model.report.model_version,
                            "repo_state":repo_state["state"],"data_state":data_state,"current_price":price,"predicted_close":prediction["predicted_close"],
                            "actual_close":None,"settle_price":price})
            self.snapshots[(monitor.session_id,snap.resolved_symbol,interval)]=result
            return result

    def trust_score(self,model,repo,snapshot,data_current,regime,news_impact,model_bound,liquidity_ok):
        score=100; checks=[]
        if model_bound:
            if repo["state"]!="CURRENT":
                score-=30; checks.append({"name":"Repository freshness","status":"FAIL","detail":"The model-bound environment changed; accept a new baseline."})
            else: checks.append({"name":"Repository freshness","status":"PASS","detail":"Accepted baseline matches the current model environment."})
        else: checks.append({"name":"Repository scope","status":"INFO","detail":"External repository is audit-only and does not affect the model."})
        if data_current:
            checks.append({"name":"Market data freshness","status":"PASS","detail":snapshot.data_status})
        else:
            score-=25; checks.append({"name":"Market data freshness","status":"FAIL","detail":"Market data is stale or unavailable."})
        if model_bound and repo.get("security_blocking"):
            score-=30; checks.append({"name":"New security findings","status":"FAIL","detail":"A new HIGH-severity finding blocks model trust until re-baselined."})
        elif model_bound:
            checks.append({"name":"New security findings","status":"PASS","detail":"No new HIGH-severity finding blocks model trust."})
        if model.report.gate_pass:
            checks.append({"name":"90% signal precision gate","status":"PASS","detail":f"{model.report.signal_precision*100:.2f}% with {model.report.signal_count} holdout signals; Wilson lower bound {model.report.precision_lower_bound*100:.2f}%."})
        else:
            score-=30; checks.append({"name":"90% signal precision gate","status":"FAIL","detail":f"{model.report.signal_precision*100:.2f}% with {model.report.signal_count} signals; lower bound {model.report.precision_lower_bound*100:.2f}%."})
        if not liquidity_ok:
            score-=15; checks.append({"name":"Liquidity","status":"WARN","detail":"Median recent value traded is below the configured paper-trading floor."})
        else: checks.append({"name":"Liquidity","status":"PASS","detail":"Recent median value traded meets the configured paper-analysis floor."})
        if regime["volatility"]=="HIGH":
            score-=8; checks.append({"name":"Volatility","status":"WARN","detail":"High"} )
        else: checks.append({"name":"Volatility","status":"PASS","detail":regime["volatility"]})
        if abs(news_impact)>0.60:
            score-=5; checks.append({"name":"News conflict","status":"WARN","detail":f"impact {news_impact:+.2f}"})
        else: checks.append({"name":"News conflict","status":"PASS","detail":f"impact {news_impact:+.2f}"})
        score=max(0,min(100,score))
        if model_bound and repo["state"]!="CURRENT": status="REVALIDATION REQUIRED"
        elif model_bound and repo.get("security_blocking"): status="SECURITY REVALIDATION REQUIRED"
        elif not data_current: status="DATA REVALIDATION REQUIRED"
        elif not model.report.gate_pass: status="NO-TRADE QUALITY GATE"
        elif not liquidity_ok: status="LIQUIDITY HOLD"
        elif score>=80: status="TRUSTED"
        else: status="CAUTION"
        return {"score":round(score,1),"status":status,"checks":checks}

    def full_analysis(self,symbol,interval,repo_monitor=None):
        return self.analyze(symbol,interval,False,True,repo_monitor)

    def backtest_only(self,symbol,interval,repo_monitor=None):
        return self.analyze(symbol,interval,False,False,repo_monitor)["backtest"]
