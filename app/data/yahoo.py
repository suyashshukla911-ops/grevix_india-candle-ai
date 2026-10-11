
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:  # optional at import time; requirements installs it for live mode
    yf = None

from app.config import COMMON_INDIAN_STOCKS, INDEX_SYMBOLS, settings

IST = ZoneInfo("Asia/Kolkata")
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "IndiaCandleAI/TrustGraph (educational competition build)"
})

_INTERVAL_MAP = {
    "1m": "1m", "2m": "2m", "3m": "5m", "5m": "5m", "10m": "5m",
    "15m": "15m", "30m": "30m", "60m": "60m", "90m": "90m", "1h": "60m",
    "1d": "1d",
}

@dataclass
class MarketSnapshot:
    symbol: str
    resolved_symbol: str
    name: str
    exchange: str
    interval: str
    source: str
    data_status: str
    fetched_at: str
    latest_timestamp: str
    freshness_seconds: float
    frame: pd.DataFrame

    @property
    def is_live(self) -> bool:
        return self.source.startswith("Yahoo")

class YahooDataError(RuntimeError):
    pass

class YahooProvider:
    """
    Yahoo Finance adapter with:
      1) yfinance when installed
      2) Yahoo chart/search HTTP endpoints
      3) disk cache
      4) deterministic local synthetic fallback
    No API key is required.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir or settings.runtime_dir / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory: dict[tuple[str, str], MarketSnapshot] = {}
        self._live_disabled_until = 0.0
        self._live_failures = 0

    @staticmethod
    def normalize_symbol(raw: str) -> str:
        value = (raw or "").strip().upper()
        if not value:
            raise ValueError("Enter a stock symbol.")
        if value.startswith("^"):
            return value
        if "." in value:
            return value
        return f"{value}.NS"

    @staticmethod
    def candidates(raw: str) -> list[str]:
        value = (raw or "").strip().upper()
        if "." in value or value.startswith("^"):
            return [value]
        # NSE first, then BSE.
        return [f"{value}.NS", f"{value}.BO"]

    def _live_allowed(self) -> bool:
        return time.time() >= self._live_disabled_until

    def _record_live_failure(self):
        self._live_failures += 1
        # Fast-fail after the first outage so an offline competition machine
        # never waits through repeated network timeouts.
        cooldown = 120 if self._live_failures < 3 else 300
        self._live_disabled_until = time.time() + cooldown

    def _record_live_success(self):
        self._live_failures = 0
        self._live_disabled_until = 0.0

    def _cache_key(self, symbol: str, interval: str, days: int) -> str:
        payload = f"{symbol}|{interval}|{days}".encode()
        return hashlib.sha256(payload).hexdigest()[:20]

    def _cache_paths(self, symbol: str, interval: str, days: int) -> tuple[Path, Path]:
        key = self._cache_key(symbol, interval, days)
        return self.cache_dir / f"{key}.csv", self.cache_dir / f"{key}.json"

    def _write_cache(self, symbol: str, interval: str, days: int, frame: pd.DataFrame, source: str):
        csv_path, meta_path = self._cache_paths(symbol, interval, days)
        frame.to_csv(csv_path, index=False)
        meta_path.write_text(json.dumps({
            "symbol": symbol, "interval": interval, "days": days,
            "source": source, "written": time.time()
        }, indent=2), encoding="utf-8")

    def _read_cache(self, symbol: str, interval: str, days: int) -> Optional[pd.DataFrame]:
        csv_path, meta_path = self._cache_paths(symbol, interval, days)
        if not csv_path.exists() or not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            age_hours = (time.time() - float(meta.get("written", 0))) / 3600.0
            max_age = max(2.0, settings.max_cache_hours)
            if age_hours > max_age:
                return None
            df = pd.read_csv(csv_path, parse_dates=["timestamp"])
            return self._clean(df)
        except Exception:
            return None

    @staticmethod
    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        rename = {c.lower(): c for c in out.columns}
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        for c in required:
            if c not in out.columns and c in rename:
                out[c] = out.pop(rename[c])
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True).dt.tz_convert(IST)
        for c in ["open", "high", "low", "close", "volume"]:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.dropna(subset=["open", "high", "low", "close"]).sort_values("timestamp")
        out = out.drop_duplicates("timestamp").reset_index(drop=True)
        out["volume"] = out["volume"].fillna(0)
        return out

    def _download_yfinance(self, symbol: str, interval: str, days: int) -> Optional[pd.DataFrame]:
        if yf is None:
            return None
        yf_interval = _INTERVAL_MAP.get(interval, interval)
        try:
            # yfinance handles Yahoo's current interval/retention rules better than
            # manually scraping HTML pages.
            ticker = yf.Ticker(symbol)
            hist = ticker.history(
                period=f"{max(days, 7)}d",
                interval=yf_interval,
                auto_adjust=False,
                actions=False,
                prepost=False,
                repair=True,
                timeout=min(settings.data_timeout_seconds, 4.0),
            )
            if hist is None or hist.empty:
                return None
            hist = hist.reset_index()
            ts_col = "Datetime" if "Datetime" in hist.columns else "Date"
            frame = pd.DataFrame({
                "timestamp": hist[ts_col],
                "open": hist["Open"],
                "high": hist["High"],
                "low": hist["Low"],
                "close": hist["Close"],
                "volume": hist.get("Volume", 0),
            })
            return self._clean(frame)
        except Exception:
            return None

    def _download_chart_endpoint(self, symbol: str, interval: str, days: int) -> Optional[pd.DataFrame]:
        yf_interval = _INTERVAL_MAP.get(interval, interval)
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{quote_plus(symbol)}?range={max(days, 7)}d&interval={yf_interval}"
            "&includePrePost=false&events=history"
        )
        try:
            r = _SESSION.get(url, timeout=min(settings.data_timeout_seconds, 4.0))
            r.raise_for_status()
            payload = r.json()
            result = (payload.get("chart") or {}).get("result") or []
            if not result:
                return None
            result = result[0]
            timestamps = result.get("timestamp") or []
            q = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            if not timestamps:
                return None
            frame = pd.DataFrame({
                "timestamp": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(IST),
                "open": q.get("open", []),
                "high": q.get("high", []),
                "low": q.get("low", []),
                "close": q.get("close", []),
                "volume": q.get("volume", []),
            })
            return self._clean(frame)
        except Exception:
            return None

    def _synthetic(self, raw: str, interval: str, days: int) -> tuple[str, pd.DataFrame]:
        """
        Deterministic demo fallback used only when live Yahoo and cache are unavailable.
        The labels contain mild momentum persistence so the validation gate can produce
        meaningful selective signals without pretending they came from the market.
        """
        seed = int(hashlib.sha256(f"{raw}|{interval}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        bars_per_day = {"1m": 375, "2m": 188, "3m": 125, "5m": 75, "10m": 38,
                        "15m": 25, "30m": 13, "60m": 7, "1h": 7}.get(interval, 25)
        n = max(500, min(days * bars_per_day, 7000))
        # Build market hours only, five days per week.
        all_days = pd.bdate_range(end=pd.Timestamp.now(tz=IST).normalize(), periods=max(days, 50))
        times = []
        for d in all_days:
            start = d + pd.Timedelta(hours=9, minutes=15)
            freq_min = int(interval.replace("m", "")) if interval.endswith("m") else 60
            stamps = pd.date_range(start=start, periods=bars_per_day, freq=f"{freq_min}min")
            stamps = stamps[stamps.hour * 60 + stamps.minute <= 15*60+30]
            times.extend(stamps.tolist())
        ts = pd.DatetimeIndex(times[-n:])
        # Smooth stochastic trend with observable momentum persistence.
        base = 900 + (seed % 500)
        regime = np.sin(np.linspace(0, 16*np.pi, len(ts))) * 0.0012
        persistence = np.zeros(len(ts))
        noise = rng.normal(0, 0.0009, len(ts))
        for i in range(1, len(ts)):
            persistence[i] = 0.55*persistence[i-1] + regime[i] + noise[i]
        close = base * np.exp(np.cumsum(persistence))
        open_ = np.r_[close[0], close[:-1]]
        spread = np.abs(rng.normal(0.0007, 0.00025, len(ts))) * close
        high = np.maximum(open_, close) + spread
        low = np.minimum(open_, close) - spread
        vol = rng.integers(100_000, 1_500_000, len(ts)).astype(float)
        frame = pd.DataFrame({
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        })
        return "LOCAL DEMO", self._clean(frame)

    def history(self, raw: str, interval: str, days: Optional[int] = None) -> MarketSnapshot:
        days = int(days or settings.train_days)
        interval = interval or settings.default_interval
        memory_key = (raw.upper(), interval)
        if memory_key in self._memory:
            snap = self._memory[memory_key]
            # Reuse in-memory data for fast repeated clicks.
            return snap

        for candidate in self.candidates(raw):
            frame = None
            if self._live_allowed():
                # Prefer Yahoo's structured chart endpoint: it is lighter than
                # rendering/reading the finance website HTML and works across a
                # much larger ticker set.
                frame = self._download_chart_endpoint(candidate, interval, days)
                if frame is None:
                    frame = self._download_yfinance(candidate, interval, days)
            if frame is not None and len(frame) >= 60:
                self._record_live_success()
                self._write_cache(candidate, interval, days, frame, "Yahoo Finance")
                latest = frame["timestamp"].iloc[-1]
                now = pd.Timestamp.now(tz=IST)
                freshness = max(0.0, (now - latest).total_seconds())
                name = candidate.replace(".NS", "").replace(".BO", "")
                snap = MarketSnapshot(
                    symbol=raw.upper(),
                    resolved_symbol=candidate,
                    name=name,
                    exchange="NSE" if candidate.endswith(".NS") else ("BSE" if candidate.endswith(".BO") else "Yahoo"),
                    interval=interval,
                    source="Yahoo Finance",
                    data_status="LIVE",
                    fetched_at=datetime.now(IST).isoformat(),
                    latest_timestamp=latest.isoformat(),
                    freshness_seconds=freshness,
                    frame=frame,
                )
                self._memory[memory_key] = snap
                return snap

            cached = self._read_cache(candidate, interval, days)
            if cached is not None and len(cached) >= 60:
                latest = cached["timestamp"].iloc[-1]
                freshness = max(0.0, (pd.Timestamp.now(tz=IST) - latest).total_seconds())
                name = candidate.replace(".NS", "").replace(".BO", "")
                snap = MarketSnapshot(
                    symbol=raw.upper(),
                    resolved_symbol=candidate,
                    name=name,
                    exchange="NSE" if candidate.endswith(".NS") else "BSE",
                    interval=interval,
                    source="Yahoo cache",
                    data_status="CACHED",
                    fetched_at=datetime.now(IST).isoformat(),
                    latest_timestamp=latest.isoformat(),
                    freshness_seconds=freshness,
                    frame=cached,
                )
                self._memory[memory_key] = snap
                return snap

        if self._live_allowed():
            self._record_live_failure()
        source, frame = self._synthetic(raw, interval, days)
        latest = frame["timestamp"].iloc[-1]
        snap = MarketSnapshot(
            symbol=raw.upper(),
            resolved_symbol=f"{raw.upper()}.NS",
            name=raw.upper(),
            exchange="LOCAL",
            interval=interval,
            source=source,
            data_status="SIMULATED",
            fetched_at=datetime.now(IST).isoformat(),
            latest_timestamp=latest.isoformat(),
            freshness_seconds=0.0,
            frame=frame,
        )
        self._memory[memory_key] = snap
        return snap

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return [{"symbol": s, "name": n, "exchange": "NSE", "source": "curated"} for s, n in COMMON_INDIAN_STOCKS[:limit]]
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={quote_plus(q)}&quotesCount={limit}&newsCount=0"
        try:
            r = _SESSION.get(url, timeout=min(settings.data_timeout_seconds, 4.0))
            r.raise_for_status()
            quotes = r.json().get("quotes", [])
            out = []
            for item in quotes:
                qtype = item.get("quoteType")
                if qtype not in {"EQUITY", "ETF", "INDEX"}:
                    continue
                symbol = str(item.get("symbol", ""))
                if symbol.endswith(".NS"):
                    ex = "NSE"
                elif symbol.endswith(".BO"):
                    ex = "BSE"
                else:
                    ex = item.get("exchange", "")
                out.append({
                    "symbol": symbol.replace(".NS", "").replace(".BO", ""),
                    "yahoo_symbol": symbol,
                    "name": item.get("longname") or item.get("shortname") or symbol,
                    "exchange": ex,
                    "source": "Yahoo search",
                })
            if out:
                return out[:limit]
        except Exception:
            pass
        ql = q.lower()
        out = [{"symbol": s, "name": n, "exchange": "NSE", "source": "curated"}
               for s, n in COMMON_INDIAN_STOCKS if ql in s.lower() or ql in n.lower()]
        return out[:limit]

    def snapshot_quote(self, symbol: str) -> dict[str, Any]:
        snap = self.history(symbol, "1d", days=20)
        last = float(snap.frame["close"].iloc[-1])
        prev = float(snap.frame["close"].iloc[-2]) if len(snap.frame) > 1 else last
        change = last - prev
        return {
            "symbol": snap.symbol,
            "name": snap.name,
            "exchange": snap.exchange,
            "price": last,
            "change_pct": (change / prev * 100.0) if prev else 0.0,
            "source": snap.source,
        }

    def pulse(self, symbols: list[str]) -> list[dict[str, Any]]:
        results = []
        for s in symbols:
            try:
                results.append(self.snapshot_quote(s))
            except Exception:
                continue
        results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        return results
