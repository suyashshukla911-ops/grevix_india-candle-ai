$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".venv\Scripts\python.exe" -m uvicorn app.main:app
