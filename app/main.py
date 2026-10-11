from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.demo import reset_demo, seed_demo, simulate_overnight_update
from app.repo_monitor.scanner import compare_manifests, scan_repository
from app.repo_monitor.state import RepositoryState

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
STATE_ROOT = BASE_DIR / "data_state"
seed_demo()
DEMO_ROOT = BASE_DIR / "demo_repos"

app = FastAPI(title="Repository Sentinel", version="2.0.0")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def _state_for(path: Path) -> RepositoryState:
    repo_state = STATE_ROOT / path.name
    return RepositoryState(repo_state)


def _live(repo_path: Path) -> dict[str, Any]:
    live = scan_repository(repo_path)
    state = _state_for(repo_path)
    previous = state.latest()
    change = compare_manifests(previous, live)
    return {"stale": bool(previous and change["changed"]), "current": live, "last_scan": previous, "change": change}


def _public_scan(scan: dict | None) -> dict | None:
    if not scan:
        return None
    return {
        "scan_id": scan.get("scan_id"),
        "scanned_at": scan.get("scanned_at"),
        "fingerprint": scan.get("fingerprint"),
        "summary": scan.get("summary"),
        "file_count": scan.get("file_count"),
        "total_lines": scan.get("total_lines"),
        "dependency_files": scan.get("dependency_files", []),
        "findings": scan.get("findings", []),
    }


def _public_live(status: dict) -> dict:
    live = status["current"]
    change = status["change"]
    return {
        "stale": status["stale"],
        "repository": live["repository"],
        "root": live["root"],
        "fingerprint": live["fingerprint"],
        "file_count": live["file_count"],
        "total_lines": live["total_lines"],
        "dependency_files": live["dependency_files"],
        "summary": live["summary"],
        "change": change,
        "findings": live["findings"],
    }


def _repo_path(name: str = "overnight_demo") -> Path:
    safe = Path(name).name
    path = DEMO_ROOT / safe
    if path.resolve().parent != DEMO_ROOT.resolve() or not path.exists():
        raise HTTPException(404, "Demo repository not found.")
    return path.resolve()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "mode": "offline",
        "api_keys_required": False,
        "demo_repository": "overnight_demo",
        "message": "All challenge flows run against local repository snapshots. No GitHub or market API is required.",
    }


@app.get("/api/repository")
def repository(name: str = "overnight_demo"):
    path = _repo_path(name)
    return _public_live(_live(path))


@app.post("/api/repository/scan")
def repository_scan(name: str = "overnight_demo"):
    path = _repo_path(name)
    result = scan_repository(path)
    saved = _state_for(path).record_scan(result)
    return {
        "ok": True,
        "scan": _public_scan(saved),
        "status": _public_live(_live(path)),
        "message": "Scan completed. These findings are now the current baseline until the repository changes.",
    }


@app.post("/api/repository/simulate-update")
def repository_simulate_update(name: str = "overnight_demo"):
    path = _repo_path(name)
    simulate_overnight_update()
    return {
        "ok": True,
        "status": _public_live(_live(path)),
        "message": "Simulated overnight repository changes. No scan was automatically accepted as current; the dashboard now marks the previous result STALE.",
    }


@app.post("/api/repository/reset")
def repository_reset(name: str = "overnight_demo"):
    path = _repo_path(name)
    reset_demo()
    # Preserve history, but make the live state visible as changed until the user explicitly rescans.
    return {
        "ok": True,
        "status": _public_live(_live(path)),
        "message": "Demo repository restored. Run a scan to establish a fresh baseline.",
    }


@app.get("/api/history")
def history(name: str = "overnight_demo"):
    path = _repo_path(name)
    state = _state_for(path)
    return {"history": state.data.get("history", [])[-10:]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
