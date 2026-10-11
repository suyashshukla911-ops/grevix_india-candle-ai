from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

commands = [
    [sys.executable, "-m", "pytest", "-q"],
    [sys.executable, "-m", "compileall", "-q", "app"],
]

for command in commands:
    print("$", " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)

print("Build verification passed.")
