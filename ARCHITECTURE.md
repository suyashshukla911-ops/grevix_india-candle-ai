# Architecture

```text
                         INDIA CANDLE AI
                               |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
  Market Provider        Feature Engine         Repository Monitor
  Yahoo / Cache /        OHLCV + context        Local model repo /
  Recorded session       + regime               public GitHub clone
        |                      |                      |
        +----------+-----------+----------------------+ 
                   |
                   v
             Analysis Engine
                   |
      +------------+------------+
      |            |            |
      v            v            v
   Model       Risk Engine   Explainability
      |            |            |
      +------------+------------+
                   |
                   v
                TrustGraph
                   |
        +----------+----------+
        |          |          |
      BUY/SELL   HOLD/NO-TRADE REVALIDATE
```

## Data layer

- Yahoo chart endpoint / yfinance.
- Verified disk/memory cache.
- Recorded last-session replay files for reproducibility and graceful provider failure.
- Bundled Indian-security catalogue snapshot plus runtime refresh.

## Model layer

- Time-ordered feature engineering.
- Calibrated HistGradientBoosting classifier.
- HistGradientBoosting regressors for next return/high/low/EOD context.
- Calibration/holdout separation.
- 90% precision + Wilson lower-bound gate.
- Model cache keyed by symbol, interval and prediction-environment fingerprint.

## Trust layer

The repository manifest tracks file hashes and component hashes. Components are classified as model, services, data, dependencies, config, frontend, docs or other. Change impact determines targeted, model+data, full or audit-only revalidation.

## Repository safety

External clones are shallow, size-limited, count-limited and isolated. The application never executes the monitored repository. Mutation routes require admin authentication.
