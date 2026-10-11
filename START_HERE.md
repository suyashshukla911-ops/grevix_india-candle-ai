# Start Here

## 1. Local run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app
```

Open `http://127.0.0.1:8000`.

## 2. First product check

- Search `TCS` and choose `5m`.
- Click **ANALYZE STOCK**.
- Confirm the data source/status is visible.
- Inspect the 5-minute chart, risk, validation and explanation.
- Add several symbols to the watchlist and click **REFRESH WATCHLIST**.

## 3. Broad-stock check

Try company names such as `Lohia`, `Regency`, or another listed security. Search results come from the bundled Indian-security catalogue plus provider search when reachable.

A security may be searchable while a requested Yahoo interval is unavailable. The app must show that as `UNAVAILABLE` rather than silently changing the timeframe.

## 4. Challenge Card 1 check

1. Open **Repository Health**.
2. Sign in with the configured admin password if required.
3. **SCAN & ACCEPT BASELINE**.
4. Confirm `CURRENT`.
5. Use **SIMULATE OVERNIGHT UPDATE**.
6. Confirm modified files, dependency change and `STALE`.
7. Return to Market Predictor and confirm the affected model is not treated as trusted.
8. Accept the new baseline and confirm `CURRENT`.

## 5. Generic GitHub repository check

1. Paste a public GitHub repository URL into **Clone & Monitor**.
2. Clone it.
3. Review the isolated external-audit state.
4. Accept its baseline.
5. Refresh the repository later and inspect drift, dependencies and security/code-quality findings.
6. Keep it external unless you explicitly choose **BIND TO MODEL TRUST**.

## 6. Important states

- `LIVE`: current provider data.
- `CACHED`: verified prior provider data.
- `MARKET CLOSED`: last completed session is valid for inspection.
- `UNAVAILABLE`: no usable data for the requested interval.
- `NO-TRADE`: model validation gate not met.
- `REVALIDATE`: repository/model/data freshness prevents a trusted action.
- `HOLD`: evidence is insufficient or liquidity is below the configured paper-analysis floor.

## 7. Tests

Development requirements are in `requirements-dev.txt`.

```powershell
python -m pip install -r requirements-dev.txt
pytest -q
```

`node --check frontend/app.js` can be used to validate the browser bundle syntax.
