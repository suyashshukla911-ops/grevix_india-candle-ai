from __future__ import annotations

import concurrent.futures
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:
    yf = None

from app.config import COMMON_INDIAN_STOCKS, INDEX_SYMBOLS, settings
from app.data.catalog import IndianSecurityCatalog

IST = ZoneInfo("Asia/Kolkata")
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 IndiaCandleAI/4.0"
})

_INTERVAL_MAP = {
    "1m": "1m", "2m": "2m", "3m": "5m", "5m": "5m", "10m": "5m",
    "15m": "15m", "30m": "30m", "60m": "60m", "90m": "90m", "1h": "60m", "1d": "1d",
}
# Conservative windows that work across Yahoo's changing intraday retention rules.
_MAX_DAYS = {
    "1m": 7, "2m": 30, "5m": 60, "15m": 60, "30m": 60, "60m": 180, "90m": 180, "1h": 180, "1d": 3650,
}

# A failed symbol/interval should never disable Yahoo for every other stock.
# Keep a short negative cache per symbol+interval instead.
NO_DATA_TTL_SECONDS = 90
QUOTE_MEMORY_TTL_SECONDS = 30

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
        return self.source == "LIVE"

class YahooDataError(RuntimeError):
    pass

class YahooProvider:
    """Yahoo market-data adapter with full-search symbol resolution and caching.

    Price retrieval remains Yahoo-based. Security discovery is independent and uses
    the current NSE equity catalogue plus Yahoo search, so the UI is not limited to
    a small hard-coded watchlist.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir or settings.runtime_dir / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = IndianSecurityCatalog()
        self._memory: dict[tuple[str, str], tuple[float, MarketSnapshot]] = {}
        self._negative_cache: dict[tuple[str, str], float] = {}
        self._quote_memory: dict[str, tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def candidates(raw: str) -> list[str]:
        value = (raw or "").strip().upper()
        if not value:
            return []
        if value.startswith("^") or "." in value:
            return [value]
        return [f"{value}.NS", f"{value}.BO"]

    def _row_candidates(self, row: dict[str, Any]) -> list[str]:
        out: list[str] = []
        y = str(row.get("yahoo_symbol") or "").strip().upper()
        if y:
            out.append(y)
        # If NSE is unavailable, a BSE code may still have a Yahoo series.
        bse = str(row.get("bse_code") or "").strip()
        if bse and bse.isdigit():
            out.append(f"{bse}.BO")
        return list(dict.fromkeys(out))

    def resolve_symbol(self, raw: str) -> tuple[str, str, str]:
        value = (raw or "").strip()
        if not value:
            raise ValueError("Enter a stock symbol or company name.")
        upper = value.upper()
        if upper.startswith("^") or "." in upper:
            ex = "NSE" if upper.endswith(".NS") else ("BSE" if upper.endswith(".BO") else "INDEX")
            return upper, upper.replace(".NS", "").replace(".BO", ""), ex
        # Direct NSE catalogue resolution first.
        row = self.catalog.get(upper)
        if row:
            candidates = self._row_candidates(row)
            primary = candidates[0] if candidates else row.get("yahoo_symbol", f"{upper}.NS")
            exchange = "NSE" if str(primary).endswith(".NS") else "BSE"
            return primary, row["name"], exchange
        # Search Yahoo + catalogue for names and partial symbols.
        results = self.search(value, limit=12)
        if results:
            r = results[0]
            return r.get("yahoo_symbol") or f"{r['symbol']}.NS", r.get("name") or r["symbol"], r.get("exchange", "NSE")
        return f"{upper}.NS", upper, "NSE"

    def _live_allowed(self, symbol: str, interval: str) -> bool:
        until = self._negative_cache.get((symbol.upper(), interval), 0.0)
        if time.time() >= until:
            self._negative_cache.pop((symbol.upper(), interval), None)
            return True
        return False

    def _record_no_data(self, symbol: str, interval: str) -> None:
        self._negative_cache[(symbol.upper(), interval)] = time.time() + NO_DATA_TTL_SECONDS

    def _cache_key(self, symbol: str, interval: str, days: int) -> str:
        return hashlib.sha256(f"{symbol}|{interval}|{days}".encode()).hexdigest()[:20]

    def _cache_paths(self, symbol: str, interval: str, days: int) -> tuple[Path, Path]:
        key = self._cache_key(symbol, interval, days)
        return self.cache_dir / f"{key}.csv", self.cache_dir / f"{key}.json"

    def _write_cache(self, symbol: str, interval: str, days: int, frame: pd.DataFrame) -> None:
        csv_path, meta_path = self._cache_paths(symbol, interval, days)
        frame.to_csv(csv_path, index=False)
        meta_path.write_text(json.dumps({
            "symbol": symbol, "interval": interval, "days": days, "written": time.time()
        }), encoding="utf-8")

    def _read_cache(self, symbol: str, interval: str, days: int) -> Optional[pd.DataFrame]:
        csv_path, meta_path = self._cache_paths(symbol, interval, days)
        if not csv_path.exists() or not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            age_hours = (time.time() - float(meta.get("written", 0))) / 3600
            if age_hours > max(2.0, settings.max_cache_hours):
                return None
            return self._clean(pd.read_csv(csv_path, parse_dates=["timestamp"]))
        except Exception:
            return None

    @staticmethod
    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        lower_map = {str(c).strip().lower(): c for c in out.columns}
        for name in ["timestamp", "open", "high", "low", "close", "volume"]:
            if name not in out.columns and name in lower_map:
                out[name] = out.pop(lower_map[name])
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [x for x in required if x not in out.columns]
        if missing:
            raise YahooDataError(f"Market data missing columns: {', '.join(missing)}")
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True).dt.tz_convert(IST)
        for c in ["open", "high", "low", "close", "volume"]:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.dropna(subset=["open", "high", "low", "close"]).sort_values("timestamp")
        out = out.drop_duplicates("timestamp").reset_index(drop=True)
        out["volume"] = out["volume"].fillna(0)
        return out

    def _download_chart_endpoint(self, symbol: str, interval: str, days: int) -> Optional[pd.DataFrame]:
        yf_interval = _INTERVAL_MAP.get(interval, interval)
        range_days = min(max(days, 5), _MAX_DAYS.get(interval, days))
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{quote_plus(symbol)}?range={range_days}d&interval={yf_interval}"
            "&includePrePost=false&events=history"
        )
        try:
            r = _SESSION.get(url, timeout=min(settings.data_timeout_seconds, 5.0))
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
            return self._clean(pd.DataFrame({
                "timestamp": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(IST),
                "open": q.get("open", []), "high": q.get("high", []),
                "low": q.get("low", []), "close": q.get("close", []),
                "volume": q.get("volume", []),
            }))
        except Exception:
            return None

    def _download_yfinance(self, symbol: str, interval: str, days: int) -> Optional[pd.DataFrame]:
        if yf is None:
            return None
        yf_interval = _INTERVAL_MAP.get(interval, interval)
        range_days = min(max(days, 5), _MAX_DAYS.get(interval, days))
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(
                period=f"{range_days}d", interval=yf_interval, auto_adjust=False,
                actions=False, prepost=False, repair=True,
                timeout=min(settings.data_timeout_seconds, 5.0),
            )
            if hist is None or hist.empty:
                return None
            hist = hist.reset_index()
            ts_col = "Datetime" if "Datetime" in hist.columns else "Date"
            return self._clean(pd.DataFrame({
                "timestamp": hist[ts_col], "open": hist["Open"], "high": hist["High"],
                "low": hist["Low"], "close": hist["Close"], "volume": hist.get("Volume", 0),
            }))
        except Exception:
            return None

    def _synthetic(self, raw: str, interval: str, days: int) -> pd.DataFrame:
        seed = int(hashlib.sha256(f"{raw}|{interval}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        bars_per_day = {"1m":375,"2m":188,"5m":75,"15m":25,"30m":13,"60m":7,"90m":5,"1h":7,"1d":1}.get(interval, 25)
        n = max(500, min(days * bars_per_day, 7000))
        if interval == "1d":
            ts = pd.bdate_range(end=pd.Timestamp.now(tz=IST).normalize(), periods=n, tz=IST)
        else:
            all_days = pd.bdate_range(end=pd.Timestamp.now(tz=IST).normalize(), periods=max(days, 50))
            times = []
            step = int(interval.rstrip("mh")) * (60 if interval.endswith("h") else 1)
            for d in all_days:
                start = d + pd.Timedelta(hours=9, minutes=15)
                stamps = pd.date_range(start=start, periods=bars_per_day, freq=f"{step}min")
                stamps = stamps[stamps.hour * 60 + stamps.minute <= 15 * 60 + 30]
                times.extend(stamps.tolist())
            ts = pd.DatetimeIndex(times[-n:])
        base = 900 + (seed % 500)
        regime = np.sin(np.linspace(0, 16*np.pi, len(ts))) * 0.0012
        persistence = np.zeros(len(ts))
        noise = rng.normal(0, 0.0009, len(ts))
        for i in range(1, len(ts)):
            persistence[i] = 0.55*persistence[i-1] + regime[i] + noise[i]
        close = base * np.exp(np.cumsum(persistence))
        open_ = np.r_[close[0], close[:-1]]
        spread = np.abs(rng.normal(0.0007, 0.00025, len(ts))) * close
        return self._clean(pd.DataFrame({
            "timestamp": ts, "open": open_, "high": np.maximum(open_, close)+spread,
            "low": np.minimum(open_, close)-spread, "close": close,
            "volume": rng.integers(100_000, 1_500_000, len(ts)).astype(float),
        }))

    def history(self, raw: str, interval: str, days: Optional[int] = None, refresh: bool = False) -> MarketSnapshot:
        interval = interval or settings.default_interval
        requested_symbol, resolved_name, exchange = self.resolve_symbol(raw)
        effective_days = min(int(days or settings.train_days), _MAX_DAYS.get(interval, int(days or settings.train_days)))
        key = (requested_symbol.upper(), interval)
        now = time.time()
        cached_mem = self._memory.get(key)
        if cached_mem and not refresh and now - cached_mem[0] < 45:
            return cached_mem[1]

        explicit_exchange = "." in (raw or "")
        if requested_symbol.startswith("^"):
            candidates = [requested_symbol]
        elif explicit_exchange:
            candidates = [requested_symbol]
        else:
            row = self.catalog.get(str(raw).strip().upper()) or self.catalog.get(requested_symbol)
            if row:
                candidates = self._row_candidates(row)
            elif requested_symbol.endswith(".NS"):
                candidates = [requested_symbol, requested_symbol[:-3] + ".BO"]
            elif requested_symbol.endswith(".BO"):
                candidates = [requested_symbol, requested_symbol[:-3] + ".NS"]
            else:
                candidates = self.candidates(requested_symbol)

        for candidate in candidates:
            frame = None
            if self._live_allowed(candidate, interval):
                frame = self._download_chart_endpoint(candidate, interval, effective_days)
                if frame is None:
                    frame = self._download_yfinance(candidate, interval, effective_days)
            if frame is not None and len(frame) >= 60:
                self._write_cache(candidate, interval, effective_days, frame)
                latest = frame["timestamp"].iloc[-1]
                snap = MarketSnapshot(
                    symbol=raw.strip().upper(), resolved_symbol=candidate,
                    name=resolved_name if resolved_name and "." not in resolved_name else candidate.replace(".NS","").replace(".BO",""),
                    exchange="NSE" if candidate.endswith(".NS") else ("BSE" if candidate.endswith(".BO") else exchange),
                    interval=interval, source="LIVE", data_status="LIVE",
                    fetched_at=datetime.now(IST).isoformat(), latest_timestamp=latest.isoformat(),
                    freshness_seconds=max(0.0, (pd.Timestamp.now(tz=IST)-latest).total_seconds()), frame=frame,
                )
                self._memory[key] = (now, snap)
                return snap

            cached = self._read_cache(candidate, interval, effective_days)
            if cached is not None and len(cached) >= 60:
                latest = cached["timestamp"].iloc[-1]
                snap = MarketSnapshot(
                    symbol=raw.strip().upper(), resolved_symbol=candidate, name=resolved_name,
                    exchange="NSE" if candidate.endswith(".NS") else "BSE", interval=interval,
                    source="CACHED", data_status="CACHED", fetched_at=datetime.now(IST).isoformat(),
                    latest_timestamp=latest.isoformat(),
                    freshness_seconds=max(0.0, (pd.Timestamp.now(tz=IST)-latest).total_seconds()), frame=cached,
                )
                self._memory[key] = (now, snap)
                return snap

        if settings.allow_fallback:
            frame = self._synthetic(raw, interval, effective_days)
            latest = frame["timestamp"].iloc[-1]
            snap = MarketSnapshot(
                symbol=raw.strip().upper(), resolved_symbol=requested_symbol, name=resolved_name,
                exchange=exchange or "NSE", interval=interval, source="FALLBACK",
                data_status="FALLBACK", fetched_at=datetime.now(IST).isoformat(),
                latest_timestamp=latest.isoformat(), freshness_seconds=0.0, frame=frame,
            )
            self._memory[key] = (now, snap)
            return snap

        for candidate in candidates:
            self._record_no_data(candidate, interval)
        raise YahooDataError(
            f"Yahoo Finance returned no usable {interval} data for {raw}. "
            "The security can still be listed in the directory, but this timeframe is unavailable from Yahoo. "
            "Try 15m, 30m, 60m, or 1d, or refresh when the market provider has data."
        )

    def search(self, query: str, limit: int = 30) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return [dict(r) for r in self.catalog.load()[:limit]]

        def catalog_search():
            return self.catalog.search(q, limit=limit)

        def yahoo_search():
            url = f"https://query1.finance.yahoo.com/v1/finance/search?q={quote_plus(q)}&quotesCount={max(limit, 30)}&newsCount=0"
            try:
                r = _SESSION.get(url, timeout=min(settings.data_timeout_seconds, 4.0))
                r.raise_for_status()
                return r.json().get("quotes", [])
            except Exception:
                return []

        # Exchange-directory lookup and Yahoo symbol resolution run concurrently so
        # searching a long-tail company does not wait for one provider before trying
        # the other.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = (pool.submit(catalog_search), pool.submit(yahoo_search))
            catalog_rows = futures[0].result()
            yahoo_rows = futures[1].result()

        out: list[dict[str, Any]] = []
        seen = set()
        for row in catalog_rows:
            key = row["yahoo_symbol"]
            if key not in seen:
                out.append(dict(row))
                seen.add(key)

        for item in yahoo_rows:
            if item.get("quoteType") not in {"EQUITY", "ETF", "INDEX"}:
                continue
            sym = str(item.get("symbol", ""))
            if not sym or sym in seen:
                continue
            ex = "NSE" if sym.endswith(".NS") else ("BSE" if sym.endswith(".BO") else item.get("exchange", ""))
            out.append({
                "symbol": sym.replace(".NS", "").replace(".BO", ""),
                "yahoo_symbol": sym,
                "name": item.get("longname") or item.get("shortname") or sym,
                "exchange": ex,
                "source": "Yahoo search",
            })
            seen.add(sym)
        return out[:limit]

    def catalog_status(self, refresh: bool = False) -> dict[str, Any]:
        if refresh:
            try:
                self.catalog.load(force=True)
            except Exception:
                pass
        return self.catalog.status()

    def availability(self, raw: str, intervals: list[str] | None = None) -> dict[str, Any]:
        intervals = intervals or ["5m", "15m", "30m", "60m", "1d"]
        def check(interval: str) -> dict[str, Any]:
            try:
                # Availability probing uses the smallest reasonable window that still
                # produces enough rows for the provider's training-safe history contract.
                days = {"5m": 5, "15m": 5, "30m": 10, "60m": 15, "1d": 120}.get(interval, 30)
                snap = self.history(raw, interval, days=days, refresh=False)
                return {
                    "interval": interval, "available": True, "status": snap.data_status,
                    "detail": f"{len(snap.frame)} candles · latest {snap.latest_timestamp}",
                    "yahoo_symbol": snap.resolved_symbol,
                }
            except Exception as exc:
                return {
                    "interval": interval, "available": False, "status": "UNAVAILABLE",
                    "detail": str(exc), "yahoo_symbol": "",
                }
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(intervals))) as pool:
            checks = list(pool.map(check, intervals))
        return {"symbol": raw.strip().upper(), "intervals": checks}

    def snapshot_quote(self, symbol: str, allow_stale_cache: bool = True) -> dict[str, Any]:
        key = str(symbol).strip().upper()
        hit = self._quote_memory.get(key)
        if hit and time.time() - hit[0] < QUOTE_MEMORY_TTL_SECONDS:
            return dict(hit[1])

        row = self.catalog.get(key)
        name = row.get("name", key) if row else key
        exchange = row.get("exchange", "NSE") if row else ("BSE" if key.isdigit() else "NSE")
        candidates = self._row_candidates(row) if row else self.candidates(key)
        for candidate in candidates:
            frame = None
            if self._live_allowed(candidate, "1d"):
                # Quote path is intentionally lightweight: a 5-day daily chart is enough
                # to show price/change and avoids running the full prediction engine.
                frame = self._download_chart_endpoint(candidate, "1d", 5)
                if frame is None:
                    frame = self._download_yfinance(candidate, "1d", 5)
            if frame is not None and not frame.empty:
                last = float(frame["close"].iloc[-1])
                prev = float(frame["close"].iloc[-2]) if len(frame) > 1 else last
                result = {
                    "symbol": key, "name": name, "exchange": "NSE" if candidate.endswith(".NS") else "BSE",
                    "yahoo_symbol": candidate, "price": last,
                    "change": last - prev, "change_pct": ((last-prev)/prev*100.0) if prev else 0.0,
                    "data_status": "LIVE", "latest_timestamp": frame["timestamp"].iloc[-1].isoformat(),
                }
                self._quote_memory[key] = (time.time(), result)
                return result

            if allow_stale_cache:
                # Accept older cached daily data for the watchlist only. We label it
                # explicitly so the UI never confuses it with a live quote.
                cached = self._read_cache(candidate, "1d", 5)
                if cached is not None and not cached.empty:
                    last = float(cached["close"].iloc[-1])
                    prev = float(cached["close"].iloc[-2]) if len(cached) > 1 else last
                    result = {
                        "symbol": key, "name": name, "exchange": "NSE" if candidate.endswith(".NS") else "BSE",
                        "yahoo_symbol": candidate, "price": last,
                        "change": last-prev, "change_pct": ((last-prev)/prev*100.0) if prev else 0.0,
                        "data_status": "CACHED", "latest_timestamp": cached["timestamp"].iloc[-1].isoformat(),
                    }
                    self._quote_memory[key] = (time.time(), result)
                    return result

        return {
            "symbol": key, "name": name, "exchange": exchange, "yahoo_symbol": candidates[0] if candidates else "",
            "price": None, "change": None, "change_pct": None, "data_status": "UNAVAILABLE",
            "latest_timestamp": None,
        }

    def pulse(self, symbols: list[str]) -> list[dict[str, Any]]:
        unique = list(dict.fromkeys([str(s).strip().upper() for s in symbols if str(s).strip()]))[:24]
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(unique)))) as pool:
            results = list(pool.map(self.snapshot_quote, unique))
        return results
