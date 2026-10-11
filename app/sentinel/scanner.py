from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

IGNORE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".sentinel", "node_modules"}
TRACKED_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".md", ".txt", ".env"}
DEPENDENCY_NAMES = {"requirements.txt", "pyproject.toml", "package.json", "package-lock.json", "poetry.lock", "Pipfile", "Pipfile.lock"}

@dataclass
class Finding:
    severity: str
    category: str
    rule: str
    file: str
    line: int
    message: str

@dataclass
class ScanResult:
    fingerprint: str
    scanned_at: str
    files: int
    lines: int
    dependency_files: int
    findings: list[Finding]
    manifest: dict[str, str]


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in IGNORE_DIRS for part in rel_parts):
            continue
        if path.suffix.lower() not in TRACKED_SUFFIXES and path.name not in DEPENDENCY_NAMES:
            continue
        yield path


def fingerprint(root: Path) -> tuple[str, dict[str, str]]:
    manifest: dict[str, str] = {}
    digest = hashlib.sha256()
    for path in sorted(iter_files(root), key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        h = hashlib.sha256(data).hexdigest()
        manifest[rel] = h
        digest.update(rel.encode("utf-8")); digest.update(b"\0"); digest.update(h.encode("ascii")); digest.update(b"\0")
    return digest.hexdigest(), manifest

SECRET_PATTERNS = [
    ("CRITICAL", "hardcoded-secret", re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
    ("HIGH", "private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]

def scan(root: Path) -> ScanResult:
    import datetime as dt
    findings: list[Finding] = []
    files = list(iter_files(root))
    total_lines = 0
    dep_count = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        if path.name in DEPENDENCY_NAMES:
            dep_count += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = text.splitlines()
        total_lines += len(lines)
        for number, line in enumerate(lines, start=1):
            stripped = line.strip()
            for severity, rule, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(severity, "security", rule, rel, number, "Potential credential-like value detected."))
            if re.search(r"\beval\s*\(", line):
                findings.append(Finding("HIGH", "security", "dynamic-eval", rel, number, "Dynamic eval() can execute untrusted code."))
            if re.search(r"\bexec\s*\(", line):
                findings.append(Finding("HIGH", "security", "dynamic-exec", rel, number, "Dynamic exec() can execute arbitrary code."))
            if "subprocess" in line and "shell=True" in line:
                findings.append(Finding("HIGH", "security", "shell-true", rel, number, "subprocess shell=True increases command-injection risk."))
            if stripped.startswith("except Exception:"):
                findings.append(Finding("MEDIUM", "quality", "broad-except", rel, number, "Broad exception handling can hide failures."))
            if "TODO" in line or "FIXME" in line:
                findings.append(Finding("LOW", "quality", "todo-marker", rel, number, "Unresolved TODO/FIXME marker."))
            if re.search(r"\bprint\s*\(", line) and path.suffix.lower() == ".py":
                findings.append(Finding("LOW", "quality", "debug-print", rel, number, "Debug print found in application code."))
    fp, manifest = fingerprint(root)
    findings.sort(key=lambda f: ({"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}.get(f.severity,9), f.file, f.line))
    return ScanResult(fp, dt.datetime.now(dt.timezone.utc).isoformat(), len(files), total_lines, dep_count, findings, manifest)
