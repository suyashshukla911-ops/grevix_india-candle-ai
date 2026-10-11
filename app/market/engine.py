from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

import pandas as pd

from app.config import settings
from app.market.data_store import OfflineMarketStore
from app.market.features import FEATURES, build_features, prepare_training_frame
from app.market.model import CandleModel

class StockAnalysisEngine:
    def __init__(self, store: OfflineMarketStore, environment_status_cb):
        self.store = store
        self.environment_status_cb = environment_status_cb
        self.models: dict[tuple[str, int], CandleModel] = {}

    def analyze(self, symbol: str, interval: int = 5, retrain: bool = False) -> dict:
        symbol = symbol.upper().strip()
        raw = self.store.candles(symbol, interval)
        if raw.empty:
            raise ValueError("No offline candles available.")
        train = prepare_training_frame(raw)
        if len(train) < settings.min_train_rows:
            raise ValueError(f"Not enough training rows: {len(train)}")
        key = (symbol, interval)
        model = self.models.get(key)
        if model is None or retrain:
            model = CandleModel(min_train_rows=settings.min_train_rows)
            model.fit(train.tail(settings.max_training_rows), FEATURES)
            self.models[key] = model
        live = build_features(raw)
        usable = live.dropna(subset=FEATURES)
        latest = usable.iloc[[-1]]
        current_price = float(latest["close"].iloc[0])
        news_summary = self.store.news_summary(symbol)
        prediction = model.predict(latest, current_price, news_summary["impact"])
        env = self.environment_status_cb()
        if env["state"] == "STALE":
            trusted_signal = "REVALIDATE"
            trust_note = "Repository/model environment changed after the accepted scan. Previous model verdict is stale."
        else:
            trusted_signal = prediction["signal"]
            trust_note = "Environment matches the accepted repository baseline."
        stock = next(x for x in self.store.symbols() if x["symbol"] == symbol)
        return {
            "instrument": stock,
            "interval": interval,
            "last_timestamp": latest["timestamp"].iloc[0].isoformat(),
            "current_price": current_price,
            "candles": [
                {"time": r.timestamp.isoformat(), "open": float(r.open), "high": float(r.high), "low": float(r.low), "close": float(r.close), "volume": int(r.volume)}
                for r in raw.tail(120).itertuples()
            ],
            "prediction": prediction,
            "news": {"summary": news_summary, "articles": self.store.news(symbol)},
            "validation": prediction["validation"],
            "environment": env,
            "trust_state": "STALE" if env["state"] == "STALE" else "CURRENT",
            "trusted_signal": trusted_signal,
            "trust_note": trust_note,
            "data_source": "offline seeded market dataset",
        }
