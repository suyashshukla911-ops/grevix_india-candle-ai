from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.sentinel.scanner import fingerprint, scan, ScanResult

class SentinelState:
    def __init__(self, repo_root: Path, state_file: Path):
        self.repo_root = repo_root
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            self.data = json.loads(self.state_file.read_text(encoding="utf-8"))
        else:
            self.data = {"accepted": None, "history": []}

    def _save(self) -> None:
        self.state_file.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def status(self) -> dict[str, Any]:
        live_fp, live_manifest = fingerprint(self.repo_root)
        accepted = self.data.get("accepted")
        if not accepted:
            return {"state":"READY", "message":"No accepted repository baseline yet.", "accepted":None, "live_fingerprint":live_fp, "live_manifest":live_manifest, "changes":{"added":[],"modified":[],"removed":[],"dependencies_changed":False}}
        old = accepted.get("manifest", {})
        added = sorted(set(live_manifest) - set(old))
        removed = sorted(set(old) - set(live_manifest))
        modified = sorted(k for k in set(live_manifest) & set(old) if live_manifest[k] != old[k])
        deps = {p for p in set(added + removed + modified) if Path(p).name in {"requirements.txt","pyproject.toml","package.json","package-lock.json","poetry.lock","Pipfile","Pipfile.lock"}}
        state = "CURRENT" if live_fp == accepted["fingerprint"] else "STALE"
        return {
            "state": state,
            "message": "Accepted scan matches the live repository." if state == "CURRENT" else "Repository changed after the accepted scan. Previous findings are stale.",
            "accepted": accepted,
            "live_fingerprint": live_fp,
            "live_manifest": live_manifest,
            "changes": {"added":added,"modified":modified,"removed":removed,"dependencies_changed":bool(deps)},
        }

    def run_scan(self) -> dict[str, Any]:
        result = scan(self.repo_root)
        record = {
            "fingerprint": result.fingerprint,
            "scanned_at": result.scanned_at,
            "files": result.files,
            "lines": result.lines,
            "dependency_files": result.dependency_files,
            "findings": [asdict(f) for f in result.findings],
            "manifest": result.manifest,
        }
        self.data["accepted"] = record
        self.data.setdefault("history", []).append(record)
        self.data["history"] = self.data["history"][-10:]
        self._save()
        return record

    def findings(self) -> list[dict[str, Any]]:
        return list((self.data.get("accepted") or {}).get("findings", []))

    def history(self) -> list[dict[str, Any]]:
        return list(reversed(self.data.get("history", [])))

    def reset_state(self) -> None:
        self.data = {"accepted": None, "history": []}
        self._save()
