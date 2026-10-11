from __future__ import annotations

from threading import RLock

from app.config import settings
from app.market.data_store import OfflineMarketStore
from app.market.features import FEATURES, build_features, prepare_training_frame
from app.market.model import CandleModel


class StockAnalysisEngine:
    def __init__(self, store: OfflineMarketStore, environment_status_cb):
        self.store = store
        self.environment_status_cb = environment_status_cb
        self.models: dict[tuple[str, int], CandleModel] = {}
        self._lock = RLock()

    def invalidate(self) -> None:
        with self._lock:
            self.models.clear()

    def _get_model(self, symbol: str, interval: int, train_df, retrain: bool) -> CandleModel:
        key = (symbol, interval)
        with self._lock:
            model = self.models.get(key)
            if model is not None and not retrain:
                return model
            model = CandleModel(
                min_train_rows=settings.min_train_rows(interval),
                gate_target=settings.min_precision_gate,
                min_gate_signals=settings.min_gate_signals,
            )
            model.fit(train_df.tail(settings.max_training_rows), FEATURES)
            self.models[key] = model
            return model

    def analyze(self, symbol: str, interval: int = 5, retrain: bool = False) -> dict:
        symbol = symbol.upper().strip()
        raw = self.store.candles(symbol, interval)
        train = prepare_training_frame(raw)
        min_rows = settings.min_train_rows(interval)
        if len(train) < min_rows:
            raise ValueError(f"Not enough training rows for {interval}m: {len(train)} (minimum {min_rows})")

        model = self._get_model(symbol, interval, train, retrain)
        live = build_features(raw)
        usable = live.dropna(subset=FEATURES)
        latest = usable.iloc[[-1]]
        current_price = float(latest["close"].iloc[0])
        news_summary = self.store.news_summary(symbol)
        prediction = model.predict(latest, current_price, news_summary["impact"])
        env = self.environment_status_cb()

        if env["state"] == "STALE":
            trusted_signal = "REVALIDATE"
            trust_note = "Repository/model environment changed after the accepted scan. Previous verdict is stale."
        elif not prediction["validation"]["gate_met"]:
            trusted_signal = "NO-TRADE"
            trust_note = "The model did not meet the 90% validation precision gate, so the system abstains."
        else:
            trusted_signal = prediction["signal"]
            trust_note = "Environment is current and the model's selective signal passed the 90% validation precision gate."

        stock = next(x for x in self.store.symbols() if x["symbol"] == symbol)
        return {
            "instrument": stock,
            "interval": interval,
            "last_timestamp": latest["timestamp"].iloc[0].isoformat(),
            "current_price": current_price,
            "candles": [
                {"time": r.timestamp.isoformat(), "open": float(r.open), "high": float(r.high), "low": float(r.low), "close": float(r.close), "volume": int(r.volume)}
                for r in raw.tail(100).itertuples()
            ],
            "prediction": prediction,
            "news": {"summary": news_summary, "articles": self.store.news(symbol)},
            "validation": prediction["validation"],
            "environment": env,
            "trust_state": "STALE" if env["state"] == "STALE" else "CURRENT",
            "trusted_signal": trusted_signal,
            "trust_note": trust_note,
            "data_source": "offline seeded market dataset",
            "latency_note": "Cached per stock/timeframe after the first analysis; retraining is explicit.",
        }
