
from __future__ import annotations

from datetime import date, timedelta
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from app.config import SECTOR_BY_SYMBOL, settings
from app.data.news import NewsService
from app.data.upstox import Instrument, UpstoxClient, UpstoxError
from app.ml.features import FEATURES, build_features, prepare_training_frame
from app.ml.model import CandleModel


INDEX_ALIASES = {
    "nifty": ["Nifty 50", "NIFTY 50"],
    "banknifty": ["Nifty Bank", "BANKNIFTY"],
    "vix": ["India VIX", "INDIA VIX"],
}


class AnalysisEngine:
    def __init__(self, upstox: UpstoxClient, news: NewsService):
        self.upstox = upstox
        self.news = news
        self.models: dict[tuple[str, int], CandleModel] = {}

    def _resolve_context(self) -> dict[str, Instrument]:
        context = {}
        for key, aliases in INDEX_ALIASES.items():
            for alias in aliases:
                try:
                    ins = self.upstox.resolve_symbol(alias)
                    context[key] = ins
                    break
                except Exception:
                    continue
        return context

    def _context_history(self, interval: int, from_date: date, to_date: date) -> dict[str, pd.DataFrame]:
        out = {}
        for key, ins in self._resolve_context().items():
            try:
                out[key] = self.upstox.get_historical(ins.instrument_key, interval, from_date, to_date)
            except Exception:
                out[key] = pd.DataFrame()
        return out

    def analyze(self, instrument: Instrument, interval: int | None = None, force_retrain: bool = False) -> dict:
        interval = int(interval or settings.default_interval)
        if interval < 1 or interval > 300:
            raise ValueError("Interval must be 1..300 minutes.")

        to_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        from_date = to_date - timedelta(days=settings.train_calendar_days)
        history = self.upstox.get_historical(instrument.instrument_key, interval, from_date, to_date)
        if history.empty:
            raise UpstoxError("No historical candles returned for this instrument.")

        # Keep incomplete current-day history out of training.
        today = to_date
        history_train = history.loc[history["timestamp"].dt.date != today].copy()
        context_hist = self._context_history(interval, from_date, to_date)
        context_train = {
            k: v.loc[v["timestamp"].dt.date != today].copy()
            for k, v in context_hist.items()
        }

        train = prepare_training_frame(history_train, context=context_train)
        if len(train) < settings.min_train_rows:
            raise ValueError(
                f"Insufficient intraday history for {instrument.trading_symbol}: "
                f"{len(train)} clean rows. Increase the available training window or use a larger interval."
            )

        key = (instrument.instrument_key, interval)
        model = self.models.get(key)
        if model is None or force_retrain:
            model = CandleModel(min_train_rows=settings.min_train_rows)
            model.fit(train, FEATURES)
            self.models[key] = model

        # Current-day candles are pulled from the intraday endpoint and merged with history.
        live = self.upstox.get_intraday(instrument.instrument_key, interval)
        combined = pd.concat([history_train, live], ignore_index=True)
        combined = combined.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        context_live = {}
        context_keys = self._resolve_context()
        for name, ctx_ins in context_keys.items():
            try:
                hist_ctx = self.upstox.get_intraday(ctx_ins.instrument_key, interval)
            except Exception:
                hist_ctx = pd.DataFrame()
            if hist_ctx.empty:
                hist_ctx = context_train.get(name, pd.DataFrame())
            context_live[name] = hist_ctx

        feat_all = build_features(combined, context=context_live)
        usable = feat_all.dropna(subset=FEATURES).copy()
        if usable.empty:
            raise ValueError("Not enough current candles to build live features.")
        latest = usable.iloc[[-1]]
        current_price = float(latest["close"].iloc[0])

        # Current news is deliberately separated from historical training to avoid look-ahead leakage.
        sector = SECTOR_BY_SYMBOL.get(instrument.trading_symbol.upper(), "Unknown")
        articles = self.news.search(
            instrument.name or instrument.trading_symbol,
            instrument.trading_symbol,
            timespan="24h",
        )
        news_summary = self.news.aggregate(articles)

        prediction = model.predict(latest, current_price, news_impact=news_summary["impact"])
        last_timestamp = latest["timestamp"].iloc[0]

        return {
            "instrument": {
                "name": instrument.name,
                "short_name": instrument.short_name,
                "symbol": instrument.trading_symbol,
                "exchange": instrument.exchange,
                "segment": instrument.segment,
                "instrument_key": instrument.instrument_key,
                "sector": sector,
            },
            "interval": interval,
            "last_timestamp": last_timestamp.isoformat(),
            "current_price": current_price,
            "candles": [
                {
                    "time": row.timestamp.isoformat(),
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "volume": int(row.volume) if pd.notna(row.volume) else 0,
                }
                for row in combined.tail(300).itertuples()
            ],
            "prediction": prediction,
            "news": {
                "summary": news_summary,
                "articles": articles[:20],
            },
            "model": prediction["validation"],
            "market_state": {
                "history_rows": len(history_train),
                "training_rows": len(train),
                "live_rows": len(live),
                "model_key": f"{instrument.trading_symbol}:{interval}m",
                "note": (
                    "Signal is gated by walk-forward validation. "
                    "No model can guarantee 100% future accuracy."
                ),
            },
        }
