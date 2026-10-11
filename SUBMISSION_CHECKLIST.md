# Final Submission Checklist

## What is included
- Market prediction core with Yahoo Finance adapter, caching, replayed last-session data, broad Indian-security catalog, risk, validation, backtesting, explainability and signal journal.
- TrustGraph / Repository Health for the Missing Update Window challenge.
- Generic public GitHub repository cloning, baseline/refresh, change impact and security/code-quality checks.
- Challenge Card 2 feedback evidence under `feedback/`.
- Render configuration (`render.yaml`) and Dockerfile.
- `requirements.txt` and `requirements-dev.txt`.
- `.python-version` pinned to Python 3.12.11.
- Automated regression tests under `tests/`.
- `FINAL_REMEDIATION_REPORT.pdf` documenting the remediation of the supplied audit findings.

## Local run
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
copy .env.example .env
python -m uvicorn app.main:app
```
Open `http://127.0.0.1:8000`.

## Verification
```powershell
pytest -q
node --check frontend/app.js
```
The source tree contains 27 regression tests. A 27/27 run was completed during the V3 hardening cycle; the final packaging changes were statically verified in the release environment.

## Render
Live demo:
https://grevix-india-candle-ai.onrender.com/

Render uses `render.yaml`. Set `ADMIN_PASSWORD`, `GITHUB_WEBHOOK_SECRET` and `MODEL_ARTIFACT_KEY` as appropriate in the Render service configuration.

## TrustGraph demonstration
1. Accept a baseline.
2. Confirm `CURRENT`.
3. Simulate or make a real model/config/dependency change.
4. Check for updates.
5. Show `STALE`, impact and required revalidation.
6. Re-accept the new baseline.
7. Confirm `CURRENT` and generate a fresh analysis.

## Important product boundary
India Candle AI is paper-analysis / research-support software. It does not place orders and does not guarantee future returns. A 90% signal-precision gate is a quality-control threshold on validated signals, not a promise of 90% live-market accuracy.
