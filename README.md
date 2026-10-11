# India Candle AI — TrustGraph

A competition-ready evolution of the original India Candle AI stock predictor.

## What stayed
The original product goal remains: estimate short-horizon Indian-stock movement from historical market data and present a BUY / SELL / NO-TRADE decision for paper analysis.

The original Tkinter implementation is preserved under `legacy_original/` and is not used by the web application.

## What changed for AfterCode
The product now asks two questions:

1. What does the model predict?
2. Can the environment that produced the prediction still be trusted?

The answer is governed by **TrustGraph**.

### TrustGraph gates
- Market data freshness
- Model validation / 90% selective-signal precision gate
- Repository freshness
- Dependency changes
- Security / code-quality state

A qualifying signal is `BUY` or `SELL`. If the model evidence is weak, the system returns `NO-TRADE`. If the data or repository is stale, it returns `REVALIDATE`.

## Yahoo Finance without an API key
The live provider tries:
1. `yfinance`
2. Yahoo chart/search HTTP endpoints
3. local disk cache
4. deterministic local demo fallback

The application does not scrape Yahoo HTML pages to discover symbols. The search layer uses Yahoo's query endpoint and the chart layer uses structured market data. The user can type many NSE/BSE tickers; the resolver tries `.NS` and `.BO`.

For the competition, the local fallback guarantees that the system remains demonstrable without a live Yahoo session.

## Start

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app
```

Open `http://127.0.0.1:8000`.

Use **`python -m uvicorn app.main:app`** for judging. No `--reload` is needed.

## Main demo
1. Market Predictor → choose `TCS` / `60m` or `RELIANCE` / `15m`.
2. `ANALYZE STOCK`.
3. Show prediction, confidence, validation gate, regime, backtest.
4. TrustGraph tab → show the individual evidence gates.
5. Repository Health → `SCAN & ACCEPT BASELINE`.
6. `SIMULATE OVERNIGHT UPDATE`.
7. The repository becomes `STALE`.
8. Return to Market Predictor and analyze again → trusted signal becomes `REVALIDATE`.
9. Repository Health → `SCAN & ACCEPT BASELINE`.
10. Analyze again → the current environment can become trusted if the 90% model gate passes.

## Repository modes
- Local monitored repository (default)
- Public GitHub repository clone without an API key
- Optional future GitHub push webhook boundary

The application never executes the monitored repository code. It only reads and fingerprints it.

## Additional capabilities
- automatic threshold optimization
- market-regime detection
- deterministic explainability
- validation-window backtest
- signal journal
- model versioning
- data freshness
- component fingerprints
- change-impact analysis
- overnight change report
- security score
- audit trail
- optional local `bandit` / `pip-audit` integration hooks if those tools are installed

## Disclaimer
Paper analysis only. No orders are placed. No prediction metric is a guarantee of future profit.

## Production-direction hooks
- Optional Basic Auth can be enabled with `DEMO_AUTH_ENABLED=true`.
- `POST /api/webhook/github` accepts GitHub push/ping events; when `GITHUB_WEBHOOK_SECRET` is set, HMAC SHA-256 is verified.
- If `bandit` is installed locally, repository scanning imports its findings.
- If `pip-audit` is installed locally, dependency vulnerabilities are imported.
