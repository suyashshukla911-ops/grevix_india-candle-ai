# Runbook

## Install
```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
```

## Start
```powershell
python -m uvicorn app.main:app
```

Open `http://127.0.0.1:8000`.

Do not use `--reload` during the competition demo. The monitored repository is intentionally mutable.

## Demo
1. Open Market Predictor.
2. `TCS`, `60m`.
3. `ANALYZE STOCK`.
4. Show confidence, 90% gate, regime, backtest and TrustGraph state.
5. Open Repository Health.
6. `SCAN & ACCEPT BASELINE`.
7. `SIMULATE OVERNIGHT UPDATE`.
8. Confirm `STALE`, 2 modified files, dependency change, `FULL` revalidation.
9. Go back to Market Predictor and analyze.
10. Confirm `REVALIDATE`.
11. Accept the new repository baseline.
12. Analyze again.

## Manual change test
Open:
`workspace\monitored_repository\app\ml\model.py`
Add a comment and save.
Then use `CHECK FOR UPDATES`.
The repository should become `STALE`.

## Yahoo behavior
When Yahoo is reachable, the provider uses Yahoo structured chart/search data.
When Yahoo is unreachable, a fast circuit-breaker prevents repeated waits and the provider falls back to a disk cache or clearly labeled `LOCAL DEMO` data.
