
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from typing import Any

import pandas as pd
import joblib
import re

from app.config import INDEX_SYMBOLS, SECTOR_BY_SYMBOL, settings
from app.data.news import NewsService
from app.data.yahoo import YahooDataError, YahooProvider
from app.ml.features import FEATURES, build_features, explain_row, prepare_training_frame, regime_from_row
from app.ml.model import CandleModel
from app.services.repository import RepositoryMonitor
from app.services.db import audit, journal_signal, save_model_run

class AnalysisEngine:
    def __init__(self, market: YahooProvider, news: NewsService, repo: RepositoryMonitor):
        self.market = market
        self.news = news
        self.repo = repo
        self.models: dict[tuple[str,str], CandleModel] = {}
        self.snapshots: dict[tuple[str,str], dict[str,Any]] = {}
        self.lock = threading.RLock()

    def _dataset_fingerprint(self, frame: pd.DataFrame) -> str:
        sample = frame[["timestamp","open","high","low","close","volume"]].tail(1200).copy()
        payload = sample.round(8).to_csv(index=False).encode()
        return hashlib.sha256(payload).hexdigest()

    def _context(self, interval: str, days: int) -> dict[str,pd.DataFrame]:
        out = {}
        for name, symbol in INDEX_SYMBOLS.items():
            try:
                snap = self.market.history(symbol, interval, days=min(days, 45))
                out[name] = snap.frame[["timestamp","close"]].copy()
            except Exception:
                out[name] = pd.DataFrame()
        return out

    def _get_model(self, snapshot, interval: str, force_retrain: bool = False):
        key=(snapshot.resolved_symbol, interval)
        dataset_fp=self._dataset_fingerprint(snapshot.frame)
        model=self.models.get(key)
        if model and not force_retrain and model.report and model.report.dataset_fingerprint == dataset_fp:
            return model, False

        model_file = settings.runtime_dir / "models" / (
            re.sub(r"[^A-Za-z0-9_.-]", "_", snapshot.resolved_symbol)
            + f"_{interval}_{dataset_fp[:12]}.joblib"
        )
        if not force_retrain and model_file.exists():
            try:
                loaded = joblib.load(model_file)
                if getattr(loaded, "report", None) and loaded.report.dataset_fingerprint == dataset_fp:
                    self.models[key] = loaded
                    return loaded, False
            except Exception:
                pass

        context=self._context(interval, settings.train_days)
        train=prepare_training_frame(snapshot.frame, context=context)
        if len(train) < settings.min_train_rows:
            raise ValueError(
                f"Not enough clean training rows for {snapshot.symbol} at {interval}. "
                f"Need {settings.min_train_rows}, have {len(train)}."
            )
        model=CandleModel(min_train_rows=settings.min_train_rows)
        model.fit(train, FEATURES, dataset_fingerprint=dataset_fp)
        self.models[key]=model
        try:
            joblib.dump(model, model_file)
        except Exception:
            pass
        save_model_run(snapshot.symbol, interval, model.report.model_version, model.report.public())
        audit("model-trained","ok",{"symbol":snapshot.symbol,"interval":interval,"model_version":model.report.model_version})
        return model, True

    def _data_state(self, snapshot) -> tuple[str, bool]:
        if snapshot.source == "LOCAL DEMO":
            return "SIMULATED", True
        # A live intraday sample is considered current if it is not more than
        # twice the selected interval behind the present time; 1d uses a looser bound.
        minutes = int(interval_to_minutes(snapshot.interval))
        limit = max(20*60, minutes*120) if snapshot.interval=="1d" else max(20*60, minutes*120)
        current = snapshot.freshness_seconds <= limit
        return ("CURRENT" if current else "STALE"), current

    def analyze(self, symbol: str, interval: str, force_retrain: bool=False) -> dict[str,Any]:
        with self.lock:
            if interval not in {"1m","2m","3m","5m","10m","15m","30m","60m","90m","1h"}:
                raise ValueError("Unsupported interval.")
            snap=self.market.history(symbol, interval, settings.train_days)
            repo=self.repo.scan(False)
            model, retrained=self._get_model(snap, interval, force_retrain)
            context=self._context(interval, min(settings.train_days, 45))
            live_features=build_features(snap.frame, context=context).dropna(subset=FEATURES)
            if live_features.empty:
                raise ValueError("Not enough clean live rows for feature generation.")
            latest=live_features.iloc[[-1]]
            price=float(latest.close.iloc[0])
            regime=regime_from_row(latest.iloc[0], live_features)
            data_state, data_current=self._data_state(snap)
            repo_current = repo["state"] == "CURRENT"
            articles=self.news.fetch(snap.resolved_symbol,snap.name,limit=8)
            news=self.news.aggregate(articles)
            prediction=model.predict(
                latest, price, news["impact"], regime,
                repo_current=repo_current, data_current=data_current
            )
            explain=explain_row(latest.iloc[0], prediction["signal"], model.report.gate_pass)
            prediction["explanation"]=explain
            prediction["environment"]={
                "repository":repo["state"],
                "data":data_state,
                "model_gate":"PASS" if model.report.gate_pass else "FAIL",
                "model_version":model.report.model_version,
            }
            prediction["trust"] = self.trust_score(
                model=model, repo=repo, snapshot=snap, data_current=data_current,
                regime=regime, news_impact=news["impact"]
            )
            last_ts=latest.timestamp.iloc[0]
            candles=snap.frame.tail(settings.max_candles_display)
            result={
                "instrument":{
                    "symbol":snap.symbol,
                    "yahoo_symbol":snap.resolved_symbol,
                    "name":snap.name,
                    "exchange":snap.exchange,
                    "sector":SECTOR_BY_SYMBOL.get(snap.symbol.replace(".NS","").replace(".BO","").upper(),"Unknown"),
                },
                "interval":interval,
                "current_price":price,
                "last_timestamp":last_ts.isoformat(),
                "data":{
                    "source":snap.source,
                    "status":data_state,
                    "freshness_seconds":round(snap.freshness_seconds,1),
                    "fetched_at":snap.fetched_at,
                    "history_rows":len(snap.frame),
                    "training_rows":model.report.train_rows,
                },
                "prediction":prediction,
                "news":{"summary":news,"articles":articles},
                "regime":regime,
                "model":model.report.public(),
                "backtest":model.backtest(),
                "candles":[
                    {"time":r.timestamp.isoformat(),"open":float(r.open),"high":float(r.high),"low":float(r.low),"close":float(r.close),"volume":float(r.volume)}
                    for r in candles.itertuples()
                ],
                "retrained":retrained,
            }
            journal_signal({
                "symbol":snap.symbol,"interval":interval,"signal":prediction["signal"],
                "confidence":prediction["confidence"],"probability_up":prediction["probability_up"],
                "precision":model.report.signal_precision,"model_version":model.report.model_version,
                "repo_state":repo["state"],"data_state":data_state,"current_price":price,
                "predicted_close":prediction["predicted_close"]
            })
            self.snapshots[(snap.symbol,interval)] = result
            return result

    def trust_score(self, model: CandleModel, repo: dict[str,Any], snapshot, data_current: bool,
                    regime: dict[str,str], news_impact: float) -> dict[str,Any]:
        score=100.0
        checks=[]
        if repo["state"] != "CURRENT":
            score -= 35; checks.append(("Repository","FAIL","Revalidation required"))
        else:
            checks.append(("Repository","PASS","Accepted baseline matches live fingerprint"))
        if data_current or snapshot.source=="LOCAL DEMO":
            checks.append(("Market data","PASS",snapshot.source))
        else:
            score -= 25; checks.append(("Market data","FAIL","Latest candle is stale"))
        if model.report.gate_pass:
            checks.append(("90% signal gate","PASS",f"{model.report.signal_precision*100:.2f}%"))
        else:
            score -= 30; checks.append(("90% signal gate","FAIL",f"{model.report.signal_precision*100:.2f}%"))
        if regime["volatility"]=="HIGH":
            score -= 8
            checks.append(("Volatility","WARN","High"))
        else:
            checks.append(("Volatility","PASS",regime["volatility"]))
        if abs(news_impact) > 0.60:
            score -= 5
            checks.append(("News conflict","WARN",f"impact {news_impact:+.2f}"))
        else:
            checks.append(("News conflict","PASS",f"impact {news_impact:+.2f}"))
        score=max(0,min(100,score))
        status="TRUSTED" if score>=80 and repo["state"]=="CURRENT" and model.report.gate_pass else (
            "REVALIDATION REQUIRED" if repo["state"]!="CURRENT" or not data_current else "NO-TRADE QUALITY GATE"
        )
        return {"score":round(score,1),"status":status,"checks":[{"name":a,"status":b,"detail":c} for a,b,c in checks]}

    def full_analysis(self, symbol: str, interval: str) -> dict[str,Any]:
        # One backend call for the entire workflow.
        return self.analyze(symbol, interval, force_retrain=False)

    def backtest_only(self, symbol: str, interval: str) -> dict[str,Any]:
        result=self.analyze(symbol,interval,force_retrain=False)
        return result["backtest"]

def interval_to_minutes(v:str) -> int:
    if v.endswith("m"): return int(v[:-1])
    if v.endswith("h"): return int(v[:-1])*60
    return 1
