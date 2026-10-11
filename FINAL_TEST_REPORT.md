# Final Local Validation Report

Date: 11 October 2026

## Automated tests

- `python -m pytest -q`
- Result: **2 passed**

## HTTP smoke test

Validated against a real Uvicorn process on `127.0.0.1`:

1. Reset demo repository
2. Establish baseline scan
3. Confirm baseline is `stale: false`
4. Simulate overnight repository update
5. Confirm baseline becomes `stale: true`
6. Confirm modified files: `requirements.txt`, `src/app.py`
7. Confirm added file: `src/feature_flags.py`
8. Confirm dependency change is detected
9. Run a new scan
10. Confirm status returns to `stale: false`
11. Confirm accepted scan history contains multiple scans

Result: **HTTP SMOKE TEST PASSED**

## Python 3.14 Windows compatibility

The project explicitly installs `tzdata` and also contains a fixed IST (+05:30) fallback for systems where the IANA timezone database is unavailable.
