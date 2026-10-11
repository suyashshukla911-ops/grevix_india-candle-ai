from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    IST = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    # Python installations without the system/packaged IANA timezone database
    # can still run this India-only competition demo.
    IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


class RepositoryState:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / "state.json"
        self.data: dict[str, Any] = {"current_scan": None, "last_scan": None, "history": []}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {"current_scan": None, "last_scan": None, "history": []}

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def latest(self) -> dict | None:
        return self.data.get("last_scan")

    def current_snapshot(self) -> dict | None:
        return self.data.get("current_scan")

    def record_scan(self, result: dict) -> dict:
        scan = dict(result)
        scan["scanned_at"] = now_iso()
        scan_id = f"scan-{len(self.data.get('history', [])) + 1:04d}"
        scan["scan_id"] = scan_id
        self.data["last_scan"] = scan
        self.data["current_scan"] = scan
        self.data.setdefault("history", []).append({
            "scan_id": scan_id,
            "scanned_at": scan["scanned_at"],
            "fingerprint": scan["fingerprint"],
            "summary": scan["summary"],
            "file_count": scan["file_count"],
        })
        self.save()
        return scan

    def mark_stale(self, live_scan: dict, change: dict) -> dict:
        current = self.data.get("current_scan") or self.data.get("last_scan")
        if not current:
            return {"stale": False, "current": live_scan, "last_scan": None, "change": change}
        return {
            "stale": change["changed"],
            "current": live_scan,
            "last_scan": current,
            "change": change,
        }
