from __future__ import annotations

import shutil
from pathlib import Path

from app.sentinel.state import SentinelState


class RepositoryService:
    def __init__(self, root: Path, state_file: Path, seed_root: Path):
        self.root = root
        self.seed_root = seed_root
        self.state = SentinelState(root, state_file)
        self.root.mkdir(parents=True, exist_ok=True)
        self.seed_root.mkdir(parents=True, exist_ok=True)
        if not any(self.root.iterdir()):
            self.reset_repository()

    def reset_repository(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for child in list(self.root.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        for child in self.seed_root.iterdir():
            target = self.root / child.name
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
        self.state.reset_state()

    def simulate_overnight_update(self) -> None:
        predictor = self.root / "src" / "predictor.py"
        text = predictor.read_text(encoding="utf-8")
        if "SIMULATED_UPDATE" not in text:
            text += (
                "\n# SIMULATED_UPDATE: overnight refactor introduced a new evaluation path\n"
                "def refreshed_signal(payload):\n"
                "    return eval(payload.get('expression', '0'))\n"
            )
            predictor.write_text(text, encoding="utf-8")
        req = self.root / "requirements.txt"
        req_text = req.read_text(encoding="utf-8")
        if "numpy==2.3.0" not in req_text:
            req.write_text(req_text.replace("numpy>=2.2", "numpy==2.3.0"), encoding="utf-8")

    def status(self):
        return self.state.status()

    def scan(self):
        return self.state.run_scan()

    def history(self):
        return self.state.history()
