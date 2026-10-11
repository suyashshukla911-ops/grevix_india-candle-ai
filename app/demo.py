from __future__ import annotations

import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DEMO_ROOT = BASE_DIR / "demo_repos"
CANONICAL = DEMO_ROOT / "overnight_demo_seed"
TARGET = DEMO_ROOT / "overnight_demo"


def seed_demo() -> Path:
    CANONICAL.mkdir(parents=True, exist_ok=True)
    (CANONICAL / "src").mkdir(exist_ok=True)
    (CANONICAL / "tests").mkdir(exist_ok=True)
    (CANONICAL / "README.md").write_text(
        "# Atlas Web\n\nDemo repository for the Missing Update Window challenge.\n",
        encoding="utf-8",
    )
    (CANONICAL / "requirements.txt").write_text("fastapi==0.115.6\n", encoding="utf-8")
    (CANONICAL / "src" / "app.py").write_text(
        "def health():\n    return {'ok': True}\n\n\ndef add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    (CANONICAL / "tests" / "test_app.py").write_text(
        "def test_health():\n    assert True\n",
        encoding="utf-8",
    )
    reset_demo()
    return TARGET


def reset_demo() -> Path:
    if not CANONICAL.exists():
        return seed_demo()
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(CANONICAL, TARGET)
    return TARGET


def simulate_overnight_update() -> Path:
    TARGET.mkdir(parents=True, exist_ok=True)
    app = TARGET / "src" / "app.py"
    existing = app.read_text(encoding="utf-8") if app.exists() else ""
    if "legacy_debug" not in existing:
        app.write_text(
            existing + "\n\n# Overnight update: generated debug helper\n"
            "def legacy_debug(value):\n    print(value)\n    return eval(value)\n\n"
            "TOKEN = 'ghp_FAKE_DEMO_TOKEN_SHOULD_NEVER_BE_COMMITTED'\n",
            encoding="utf-8",
        )
    req = TARGET / "requirements.txt"
    req.write_text(req.read_text(encoding="utf-8") + "\nrequests==2.31.0\n", encoding="utf-8")
    (TARGET / "src" / "feature_flags.py").write_text(
        "FEATURE_FLAG = 'nightly-rollout'\n",
        encoding="utf-8",
    )
    return TARGET
