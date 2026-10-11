# India Candle AI - TrustGraph

India Candle AI is an AI-assisted market-intelligence platform for Indian listed securities. It combines market-data freshness, time-series machine learning, chronological validation, risk analysis, explainability, backtesting, signal history and repository-aware trust.

## Live application

- Render: https://grevix-india-candle-ai.onrender.com/
- GitHub: https://github.com/suyashshukla911-ops/grevix_india-candle-ai

## The product problem

The original product asked:

> What does the recent market evidence suggest about the next move in an Indian security?

The AfterCode Missing Update Window challenge added a second real-world problem:

> Can the result still be trusted when the software environment that produced it changes?

India Candle AI therefore uses one decision workflow rather than a separate stock demo and repository demo.

```text
Market data freshness
        +
Model validation
        +
Risk / regime context
        +
Repository freshness when model-bound
        +
New security findings
        |
        v
     TRUSTGRAPH
        |
        +--> BUY / SELL / HOLD
        +--> NO-TRADE
        +--> REVALIDATE
        +--> DATA UNAVAILABLE
```

## What the user can do

### Market Predictor

1. Search an Indian security by symbol or company name.
2. Browse the bundled Indian-security directory.
3. Choose 5m, 15m, 30m, 60m or 1d.
4. Check interval availability before analysis.
5. Analyze the selected security.
6. Review the candlestick chart, next-range estimates, model validation, risk, market regime and explainability.
7. Use the watchlist for lightweight quote monitoring.
8. Review historical signals in Signal Journal.

### Data states are explicit

The platform distinguishes:

- `LIVE` - current provider data is available.
- `CACHED` - previously verified market data is being used because the provider is unavailable.
- `MARKET CLOSED` / recorded last session - the market is not currently trading and the last completed session is being used for inspection.
- `STALE` - a freshness gate is not satisfied.
- `UNAVAILABLE` - no usable provider or verified recorded data exists for the requested interval.

The application never silently changes the user's requested timeframe to another timeframe.

## Machine-learning model

The model uses OHLCV-derived time-series features such as:

- returns and momentum
- EMA structure
- RSI
- ATR and realized volatility
- MACD
- Bollinger position
- volume behaviour
- VWAP gap
- session/time structure
- Nifty, BankNifty and India VIX context when available
- market-regime classification

Validation is chronological. The classifier is fit on an earlier window, calibrated on a later window, and evaluated on an untouched holdout window.

### 90% selective-signal precision gate

India Candle AI does **not** claim 90% overall direction accuracy.

The product instead uses a conservative gate:

```text
Validation signal precision >= 90%
AND
minimum holdout signal count
AND
Wilson lower confidence bound >= 90%
        |
        v
BUY / SELL can become trusted
```

If the evidence does not satisfy the gate, the system returns `NO-TRADE` rather than manufacturing a high-confidence trade.

The threshold is selected on the calibration window; the reported precision and gate decision are computed on an untouched holdout window. This avoids reporting the same validation data used to choose the threshold as if it were unseen evidence.

## Risk and backtesting

The application reports:

- direction accuracy
- selective signal precision
- Wilson lower bound
- signal coverage
- validation rows
- next-return MAE and R2
- strategy return
- buy-and-hold return
- maximum drawdown
- profit factor where meaningful
- naive direction baseline
- transaction-cost/slippage assumptions
- liquidity floor

Backtests enter at the next bar/session open and exit at the next bar/session close, rather than pretending the signal candle close is tradeable. Costs are included in the paper return calculation.

Stop and target levels are explicitly marked as heuristic risk-management levels and are not presented as guaranteed profit levels.

## TrustGraph and the Missing Update Window

Repository Health is generic. The monitored repository does **not** have to be a stock project. It can be a Python application, API, web application, LMS, cybersecurity repository or another public software project.

### External repository workflow

```text
Public GitHub URL
        |
        v
Isolated shallow clone
        |
        v
Cryptographic baseline
+ file manifest
+ component fingerprints
+ dependency state
+ accepted findings
        |
        v
Later refresh / check
        |
        v
Added / modified / removed files
+ dependency changes
+ security/code-quality changes
+ change impact
        |
        v
Required revalidation scope
```

External repositories are audit-only by default. They affect model trust only after an explicit `BIND TO MODEL TRUST` action.

For the built-in model environment, the overnight proof-of-concept changes real files in `app/ml/`, `app/config.py` and `requirements.txt`. A new fingerprint is detected, the environment becomes stale, and a fresh baseline is required before the prediction environment becomes trusted again.

### Design principle

> Detect automatically. Trust explicitly.

## Security monitoring

The repository scanner uses Python AST checks for high-risk constructs such as `eval`, `exec`, `os.system`, unsafe `pickle.loads`, `yaml.load`, disabled TLS verification, and unsafe SQL f-strings. It also checks for credential-like assignments including `DB_PASSWORD`, private-key patterns and JavaScript `eval()`.

The optional deep scan uses Bandit and pip-audit. Accepted baseline findings are recorded as accepted observations; only newly introduced HIGH findings block a model-bound trust decision.

## Security boundaries

- Repository mutation routes require admin authentication.
- External repositories are cloned into isolated per-session directories.
- Clone size and count are capped.
- `.git`, virtual environments, caches and runtime directories are excluded from recursive application scanning.
- The monitored repository code is never executed by Repository Health.
- GitHub webhook processing requires a configured HMAC secret.
- `source/local` arbitrary-path scanning is not exposed as a public endpoint.
- Joblib model artifacts are only loaded when an artifact signing key is configured and the signature verifies.

## Market-data architecture

Yahoo Finance is the primary provider in the competition build. Yahoo can be incomplete or unavailable for some Indian securities and intraday intervals, especially from hosted/cloud environments. The platform therefore uses a layered provider boundary:

```text
Yahoo live data
     |
     +--> verified cache
     |
     +--> recorded last-session dataset (explicitly labelled)
     |
     +--> unavailable
```

The recorded last-session data is real recorded candle data, not synthetic data. It is provided for reproducibility and graceful failure when the provider is unreachable. Freshness and TrustGraph still prevent stale recorded data from becoming a trusted live signal.

## Model environment reproducibility

Every model artifact is associated with:

- data fingerprint
- repository/environment fingerprint
- installed package versions
- feature configuration
- threshold
- validation metrics
- timestamp

A prediction-environment change invalidates the matching cached model artifact and forces a fresh training cycle after the new baseline is accepted.

## Signal Journal

Signals are deduplicated by symbol, timeframe, candle timestamp and model version. When a later candle becomes available, the journal can score earlier BUY/SELL signals using the realized close movement. This creates an auditable record rather than a stream of repeated refresh events.

## Challenge Card 2 - Real-world feedback

Real user-feedback evidence is stored under `/feedback/`. The folder contains the public/community post evidence, genuine responses and the feedback record. The intended evidence chain is:

```text
Real user feedback
        |
        v
Usability problem identified
        |
        v
Product change
        |
        v
Before / after proof
```

## Local run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app
```

Open `http://127.0.0.1:8000`.

For judging, do not use `--reload` because the repository-monitor workspace is intentionally mutable.

## Production / Render

This project is a FastAPI application, so the deployed backend needs a Web Service rather than a static-only host.

`render.yaml` is included for Render. The intended command is:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The free Render filesystem is ephemeral. For production use, persistent model/audit storage should be moved to a persistent disk or managed database; the included SQLite/runtime storage is suitable for the competition deployment and reproducible local testing.

## Repository structure

```text
app/
  data/          market provider, catalog, calendar, news, replay data
  ml/            feature engineering and model training
  services/      analysis engine, audit DB, repository monitor
  main.py        FastAPI application
frontend/        browser UI
feedback/        Challenge Card 2 evidence
archive/         preserved legacy code for reference only
tests/           automated regression tests
Dockerfile
render.yaml
requirements.txt
requirements-dev.txt
```

## Safety

This is a paper-analysis and research-support application. It does not place orders. Model validation, risk scores and trust states are decision-support controls, not guarantees of future returns or profitability. Public-facing use of investment recommendations must comply with applicable financial regulations and platform policies.
