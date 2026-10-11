# Runbook

## Normal use
Start the server without `--reload` to avoid watching the mutable monitored repository.

```powershell
python -m uvicorn app.main:app
```

## If you need live development reload
Restrict watch scope to application files and frontend files:

```powershell
python -m uvicorn app.main:app --reload --reload-dir app --reload-dir frontend
```

## Reset challenge state
Use **RESET WORKSPACE** in the Repository Health page. This restores the mutable repository from the seed copy and clears the accepted baseline.
