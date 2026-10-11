# Architecture — India Candle AI v3

```text
Browser UI
   │
   ▼
FastAPI request layer
   ├───────────────┬─────────────────────┐
   ▼               ▼                     ▼
Market Engine   Repository Sentinel   Market Overview
   │               │
   │               ├─ fingerprint + manifest
   │               ├─ security/code-quality scan
   │               ├─ accepted baseline + history
   │               └─ CURRENT / STALE state
   │
   ├─ LocalMarketStore
   ├─ feature engineering
   ├─ HistGradientBoosting models
   ├─ validation threshold selection
   ├─ 90% signal-precision gate
   ├─ next close/high/low/EOD
   └─ local research/news overlay
```

## Market path

`LocalMarketStore → interval cache → feature engineering → time-ordered validation → gradient boosting → 90% precision gate → prediction → environment freshness gate → UI`

Models are cached per `(symbol, interval)` to make repeated analysis fast. Recalibration explicitly replaces the cached model.

The 90% requirement is implemented as a **minimum validation precision gate for selective BUY/SELL signals**. Overall direction accuracy is reported separately and is not artificially inflated to 90%.

## Freshness path

`LocalRepositoryProvider → SHA-256 fingerprint + manifest → security/code-quality scan → accepted baseline → live comparison → CURRENT/STALE`

When the repository changes, the prior accepted result becomes stale. The market calculation remains inspectable, but `trusted_signal = REVALIDATE` until a new baseline is accepted.

## API execution model

CPU-bound analysis runs in FastAPI's worker thread pool. This keeps the request loop responsive and prevents model fitting from making unrelated browser requests fail.

## Extension boundary

A future `GitHubRepositoryProvider` can provide a repository snapshot to the sentinel without changing the dashboard state machine. A live market-data provider can replace `LocalMarketStore` behind the same engine interface.
