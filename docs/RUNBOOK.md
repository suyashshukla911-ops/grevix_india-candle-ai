# Competition Runbook

## Start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app
```

Open `http://127.0.0.1:8000`.

Do not use `--reload` during judging. The monitored demo repository intentionally changes during the challenge flow.

## Recommended 5-minute demonstration

1. **Market Predictor** — default TCS / 60m.
2. Click **ANALYZE STOCK** and show prediction, validation and the 90% precision gate.
3. Open **Repository Health**.
4. Click **SCAN & ACCEPT BASELINE**.
5. Click **SIMULATE OVERNIGHT UPDATE**.
6. Show **STALE**, modified source, dependency change and security/code-quality findings.
7. Return to **Market Predictor** and analyze again.
8. Show **REVALIDATE** instead of pretending the old verdict is still trusted.
9. Return to **Repository Health** and click **SCAN & ACCEPT BASELINE**.
10. Analyze again and show the environment is current.

## Manual update proof

Instead of the simulation button, edit:

`workspace\monitored_repository\src\predictor.py`

Then click **CHECK FOR UPDATES**. The same stale-state path should appear.

## Dependency proof

Edit:

`workspace\monitored_repository\requirements.txt`

Then click **CHECK FOR UPDATES**. The dashboard should show `dependency change = YES`.

## Tests

```powershell
pytest -q
```

Expected result for the packaged build: **5 passed**.
