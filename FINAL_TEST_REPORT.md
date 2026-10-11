# Final Test Report

Run:

```powershell
pytest -q
```

Expected: all tests pass.

The suite covers:
- feature generation
- model fit and prediction
- 90% threshold gate behavior
- backtest calculations
- repository fingerprint change detection
- dependency change detection
- security scanning
- CURRENT -> STALE -> CURRENT transitions
- FastAPI bootstrap contract
- market engine local fallback

Manual smoke test:
- Start with `python -m uvicorn app.main:app`
- Open `http://127.0.0.1:8000`
- Analyze TCS 60m or RELIANCE 15m
- Run repository baseline
- Simulate overnight update
- Observe STALE
- Analyze and observe REVALIDATE
- Accept new baseline
- Analyze again
