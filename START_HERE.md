# Start Here — India Candle AI TrustGraph

1. Create and activate a Python virtual environment.
2. `python -m pip install -r requirements.txt`
3. `copy .env.example .env` (PowerShell) or copy it manually.
4. Keep `ALLOW_FALLBACK=false` for the competition build so market analysis uses live/cached provider data.
5. Start with `python -m uvicorn app.main:app`.
6. Open `http://127.0.0.1:8000`.

### First-time workflow
- Search a stock by symbol/company name, or open **Browse Directory**. The directory is exchange-backed and also ships with a bundled catalogue snapshot so long-tail Indian securities remain searchable when an exchange refresh is unavailable.
- Choose 5m, 15m, 30m, 60m or 1d and run **Analyze Stock**.
- Use **Run Full Analysis** to execute data freshness + model gate + repository trust checks together.
- The watchlist uses lightweight quote retrieval; unavailable symbols remain visible with an explicit status instead of breaking the list.
- Use **Repository Health** for the AfterCode Missing Update Window workflow.
- Use **Clone & Monitor** for any public GitHub repository. Accept a baseline, then check/refresh it later. External repositories remain audit-only until explicitly bound to model trust.

### Important
A listed security can be searchable even when the selected intraday interval is not available from the market-data provider. The application reports that condition instead of silently substituting another timeframe.

Do not use `--reload` during judging; the monitored repository is intentionally mutable.
