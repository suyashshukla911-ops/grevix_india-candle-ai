# Final Hotfix — 10.2.0-final-hotfix

## Root cause fixed
The market-data path used Python's boolean `or` between two pandas DataFrames:

`frame = chart_download(...) or yfinance_download(...)`

A non-empty DataFrame cannot be evaluated as a boolean, which raised:

`The truth value of a DataFrame is ambiguous`

That exception was converted by the API into HTTP 422 responses, making every stock/timeframe appear unavailable even when Yahoo returned usable data.

The fix uses explicit `None` checks instead. A second Yahoo chart endpoint is also tried before falling back to yfinance.

## Render fixes
- Health endpoint is now constant-time and does not scan repositories or refresh the catalogue.
- Render health check uses `/`.
- Docker no longer hardcodes Render's port; it uses `${PORT:-10000}`.
- Docker upgrades pip before installing application dependencies.

## Authentication
Local `.env` and Render environment variables are separate. Set `ADMIN_PASSWORD` in Render to the password you want to use, then redeploy. The application trims accidental surrounding whitespace.

## Security/package hygiene
The final archive intentionally excludes `.env`, `.venv`, `.git`, `runtime` state, pytest caches and Python caches. Do not commit those directories.
