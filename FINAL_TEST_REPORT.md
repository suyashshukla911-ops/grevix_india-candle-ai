# Final Verification Report — India Candle AI v3

## Environment

- Python: tested with Python 3.14 environment
- FastAPI + Uvicorn
- Offline seeded market dataset
- No API keys required

## Automated tests

```text
5 passed
```

Coverage includes:

- Market dataset and feature availability
- Prediction execution
- FastAPI core flow
- Security `eval()` detection
- Repository dependency-change detection
- CURRENT → STALE transition
- STALE prediction trust state = REVALIDATE

## Performance observations

Using the packaged deterministic model:

- First TCS / 60m analysis: about 1.3 seconds in local smoke test
- Cached TCS / 60m analysis: about 45 ms in local smoke test
- Recalibration TCS / 60m: about 1.6 seconds in local smoke test
- Health/stocks/repository status endpoints: a few milliseconds locally

The analysis endpoint runs in a worker thread, so model fitting no longer blocks FastAPI's request loop.

## Packaged default validation baseline

**TCS / 60m**

- Direction accuracy: 79.35%
- Selective signal precision: 91.43%
- Signal coverage: 69.57%
- Threshold: 0.82
- Validation rows: 92
- Qualified validation signals: 64
- 90% precision gate: PASS

## Honest 90% policy

The application does not claim that overall market-direction accuracy is 90%.

The 90% requirement is implemented as a **minimum validation precision gate for trusted BUY/SELL signals**. When a stock/timeframe cannot support that precision on its walk-forward validation window, the product abstains with **NO-TRADE**.

Examples from the packaged dataset:

- TCS / 60m: 91.43% selective signal precision → gate PASS
- INFY / 60m: 91.18% selective signal precision → gate PASS
- RELIANCE / 5m: 77.78% selective signal precision → gate NOT MET → NO-TRADE

## AfterCode challenge smoke test

```text
RESET WORKSPACE
        ↓
SCAN & ACCEPT BASELINE
        ↓
CURRENT
        ↓
SIMULATE OVERNIGHT UPDATE
        ↓
STALE
  modified: requirements.txt
  modified: src/predictor.py
  dependency change: YES
        ↓
Analyze stock
        ↓
REVALIDATE
        ↓
SCAN & ACCEPT BASELINE
        ↓
CURRENT
```

## Frontend checks

- Light theme
- No external chart/CDN dependency
- Stock selection works
- Timeframe selection works
- Analyze button has busy state
- Recalibrate button has busy state
- Repository actions have busy state
- API errors are translated into actionable local messages
- Redundant fetches removed from the analysis flow
