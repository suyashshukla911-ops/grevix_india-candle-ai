from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.config import PRIORITY_STOCKS

BASE_DIR = Path(__file__).resolve().parents[2]
MARKET_DIR = BASE_DIR / "data" / "market"
NEWS_FILE = BASE_DIR / "data" / "news.json"

class OfflineMarketStore:
    def __init__(self) -> None:
        self._cache: dict[str, pd.DataFrame] = {}
        MARKET_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self) -> None:
        for idx, stock in enumerate(PRIORITY_STOCKS):
            path = MARKET_DIR / f"{stock['symbol'].lower()}.csv"
            if path.exists():
                continue
            self._generate_stock(stock["symbol"], idx + 7, path)
        if not NEWS_FILE.exists():
            NEWS_FILE.write_text("[]", encoding="utf-8")

    def _generate_stock(self, symbol: str, seed: int, path: Path) -> None:
        rng = np.random.default_rng(seed)
        dates = pd.bdate_range(end=pd.Timestamp.now(tz="Asia/Kolkata").normalize(), periods=85)
        frames = []
        base = 900 + seed * 120
        drift = (seed % 5 - 2) * 0.00006
        for day_i, day in enumerate(dates):
            times = pd.date_range(day + pd.Timedelta(hours=9, minutes=15), periods=75, freq="5min", tz="Asia/Kolkata")
            market_noise = rng.normal(0, 0.0018, len(times))
            intraday_wave = 0.0007 * np.sin(np.linspace(0, np.pi * 2, len(times)))
            ret = market_noise + intraday_wave + drift
            if day_i and day_i % 13 == 0:
                ret[0] += rng.normal(0, 0.008)
            close = base * np.exp(np.cumsum(ret))
            open_ = np.r_[base, close[:-1]]
            high = np.maximum(open_, close) * (1 + rng.uniform(0.0002, 0.0015, len(times)))
            low = np.minimum(open_, close) * (1 - rng.uniform(0.0002, 0.0015, len(times)))
            volume = rng.integers(80000, 650000, len(times))
            frames.append(pd.DataFrame({"timestamp": times, "open": open_, "high": high, "low": low, "close": close, "volume": volume}))
            base = float(close[-1])
        out = pd.concat(frames, ignore_index=True)
        out.to_csv(path, index=False)

    def symbols(self) -> list[dict[str, Any]]:
        return PRIORITY_STOCKS

    def _load(self, symbol: str) -> pd.DataFrame:
        symbol = symbol.upper().strip()
        if symbol not in {x["symbol"] for x in PRIORITY_STOCKS}:
            raise ValueError(f"Offline universe does not contain {symbol}")
        if symbol not in self._cache:
            df = pd.read_csv(MARKET_DIR / f"{symbol.lower()}.csv", parse_dates=["timestamp"])
            if df["timestamp"].dt.tz is None:
                df["timestamp"] = df["timestamp"].dt.tz_localize("Asia/Kolkata")
            self._cache[symbol] = df
        return self._cache[symbol].copy()

    def candles(self, symbol: str, interval: int = 5) -> pd.DataFrame:
        base = self._load(symbol)
        if interval == 5:
            return base
        if interval not in {15, 30, 60}:
            raise ValueError("Offline mode supports 5m, 15m, 30m and 60m intervals.")
        base = base.set_index("timestamp")
        rule = f"{interval}min"
        agg = base.resample(rule, origin="start_day", offset="9h15min").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna().reset_index()
        return agg

    def latest(self, symbol: str, interval: int = 5) -> pd.DataFrame:
        return self.candles(symbol, interval).tail(300).reset_index(drop=True)

    def news(self, symbol: str) -> list[dict[str, Any]]:
        stock = next(x for x in PRIORITY_STOCKS if x["symbol"] == symbol.upper())
        positive = [
            (f"{stock['name']} sees steady institutional demand", 0.35, "flows"),
            (f"{stock['name']} maintains strong operating outlook", 0.22, "earnings"),
        ]
        negative = [
            (f"Analysts flag near-term volatility for {stock['name']}", -0.18, "risk"),
        ]
        headlines = positive + negative
        return [
            {"title": t, "sentiment": s, "impact": s, "event": e, "domain": "offline-research", "url": "#"}
            for t, s, e in headlines
        ]

    def news_summary(self, symbol: str) -> dict[str, Any]:
        arts = self.news(symbol)
        positive = sum(1 for a in arts if a["sentiment"] > 0.15)
        negative = sum(1 for a in arts if a["sentiment"] < -0.15)
        impact = float(np.mean([a["impact"] for a in arts])) if arts else 0.0
        return {"headline_count": len(arts), "positive": positive, "negative": negative, "neutral": len(arts)-positive-negative, "impact": round(impact, 3), "top_event": max(arts, key=lambda x: abs(x["impact"]))["event"] if arts else "none"}
