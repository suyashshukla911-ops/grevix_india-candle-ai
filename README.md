# Repository Sentinel — Missing Update Window Proof of Concept

This competition build is an **offline-first repository security + code-quality monitor** designed around the challenge card **“The Missing Update Window.”** It deliberately does not require a GitHub token, Upstox token, news API key, or internet connection for the demo flow.

## What the proof of concept demonstrates

1. **Baseline scan** — the scanner creates a SHA-256 fingerprint from the repository file manifest and records the findings.
2. **Update detection** — every page refresh rescans the local demo repository. If the live fingerprint differs from the accepted scan, the previous result is marked **STALE**.
3. **Change explanation** — the dashboard summarizes added, modified, and removed files plus dependency-file changes.
4. **Security + quality checks** — the offline scanner detects demo-friendly patterns such as hard-coded secrets, `eval`, `exec`, debug prints, broad exceptions, and TODO/FIXME markers.
5. **Explicit re-scan** — the system never silently promotes changed content to a “current” result. The participant must run a new scan to establish a new accepted baseline.
6. **Overnight simulation** — a button changes the demo repository after the baseline scan, introducing a fake credential, unsafe code pattern, and a dependency change. The old scan immediately becomes stale.
7. **Audit history** — accepted scans are retained with timestamp, fingerprint, file count, and finding totals.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app
```

Open:

`http://127.0.0.1:8000`

### Recommended judge/demo sequence

- Click **RUN CURRENT SCAN** → the dashboard becomes `BASELINE CURRENT`.
- Click **SIMULATE OVERNIGHT UPDATE** → the same previous scan becomes `RESULTS STALE`.
- Show **What changed?** → added/modified files and dependency change are visible.
- Show **Live findings** → the new fake secret + risky code are visible.
- Click **RUN CURRENT SCAN** → a new accepted scan is created and the status returns to `BASELINE CURRENT`.
- The **Accepted scan history** records both scan timestamps/fingerprints.

## Why no APIs are used

This submission is intentionally self-contained for an assessment environment. GitHub/Upstox/news connectors are **not required** to demonstrate the core challenge behavior.

A later personal/production version can replace the local repository provider with GitHub webhooks or scheduled polling. The UI and update-state model are already separated so that connector can be added without changing the stale-result rules.

## Important design decision

The system distinguishes between:

- **Live repository state** — what exists on disk now.
- **Accepted scan state** — the last scan the user explicitly ran.
- **Stale state** — live state differs from accepted scan state.

This prevents the most important failure mode in the challenge: showing an old security verdict as if it describes today's code.

## Scope

This is a proof of concept, not a production SAST engine or a CVE database. The finding rules are intentionally local, deterministic, and explainable so the challenge can be demonstrated without third-party services.

## Python 3.14 / Windows timezone note

The project includes `tzdata` in `requirements.txt` because some Python 3.14 Windows installations do not ship the IANA timezone database. The app also has an India Standard Time (+05:30) fallback so the local demo can still start if `tzdata` is temporarily unavailable.


### Optional development reload

If you need Uvicorn auto-reload during development, restrict the watched directories so the mutable demo repository does not trigger restarts:

```powershell
python -m uvicorn app.main:app --reload --reload-dir app --reload-dir frontend
```

Do not use a project-wide `--reload` for the challenge demo. The demo intentionally changes files to simulate the overnight update window.
