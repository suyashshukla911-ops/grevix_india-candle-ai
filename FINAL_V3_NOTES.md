# India Candle AI — Final Stability & Market-Data Pass

This release focuses on the issues observed during real local use after Challenge Card 2.

## Fixed

- Watchlist now uses a lightweight quote path instead of the full ML analysis engine.
- One unavailable Yahoo symbol no longer suppresses quotes for other watchlist symbols.
- Watchlist keeps unavailable securities visible with `DATA UNAVAILABLE` rather than dropping the row.
- Recent cached quotes can be shown as `CACHED` without being mislabeled as live.
- Yahoo no-data handling is per symbol/timeframe instead of using a global circuit breaker.
- Search and the Browse Directory remain broad and searchable across the bundled exchange catalogue.
- A bundled Indian-security catalogue snapshot is included so the directory remains useful even when an exchange refresh is unavailable at startup.
- Failed market-data requests now trigger an explicit timeframe-availability panel instead of a generic retry state.
- Retraining/full-analysis requests force a fresh market-data request so the user can explicitly refresh before recalibration.
- Frontend analysis requests are de-duplicated so the same stock/timeframe is not analyzed twice concurrently.
- The candlestick workflow keeps the adaptive 5m/15m/30m/60m/1d chart windows and latest-candle OHLC detail.
- Render deployment configuration is included.

## Trust behavior remains unchanged

The model still treats 90% as a selective signal-precision gate, not a blanket accuracy claim. A signal can remain inspectable while being withheld as `NO-TRADE` or `REVALIDATE` when evidence or freshness gates fail.

## Validation

Automated tests: `19 passed`.

A live FastAPI smoke test also confirmed `/api/health` and `/api/bootstrap` return HTTP 200 and the bundled catalogue exposes 3,182 securities in the prepared package.
