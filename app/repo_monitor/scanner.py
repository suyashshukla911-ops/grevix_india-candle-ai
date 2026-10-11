from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    "dist", "build", ".mypy_cache", ".ruff_cache", ".idea", ".vscode"
}
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".php", ".rb", ".swift", ".kt", ".kts", ".sql", ".html",
    ".css", ".scss", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".md",
    ".txt", ".env.example", ".xml", ".sh", ".ps1", ".dockerfile"
}

SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Generic API key assignment", re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("JWT-like token", re.compile(r"\beyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\b")),
    ("GitHub token-like value", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b")),
]

QUALITY_PATTERNS = [
    ("eval usage", re.compile(r"\beval\s*\(")),
    ("exec usage", re.compile(r"\bexec\s*\(")),
    ("debug print", re.compile(r"\bprint\s*\(")),
    ("TODO marker", re.compile(r"\bTODO\b", re.I)),
    ("FIXME marker", re.compile(r"\bFIXME\b", re.I)),
    ("broad exception", re.compile(r"except\s+Exception\s*[:(]")),
]

DEPENDENCY_FILES = {
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "poetry.lock",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "Gemfile", "Gemfile.lock"
}

@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str
    lines: int | None

@dataclass(frozen=True)
class Finding:
    id: str
    severity: str
    category: str
    title: str
    path: str
    line: int | None
    detail: str


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORED_DIRS for part in relative_parts):
            continue
        yield path


def _is_text_file(path: Path) -> bool:
    name = path.name.lower()
    return path.suffix.lower() in TEXT_EXTENSIONS or name in {"dockerfile", "makefile"} or name.startswith(".env")


def _read_text(path: Path) -> str | None:
    if not _is_text_file(path):
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(files: list[FileRecord]) -> str:
    canonical = "\n".join(f"{x.path}|{x.size}|{x.sha256}" for x in files)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _finding_id(category: str, path: str, line: int | None, title: str) -> str:
    raw = f"{category}|{path}|{line}|{title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def scan_repository(root: Path) -> dict:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Repository folder does not exist: {root}")

    files: list[FileRecord] = []
    findings: list[Finding] = []
    dependency_paths: list[str] = []
    total_lines = 0

    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        stat = path.stat()
        text = _read_text(path)
        lines = None
        if text is not None:
            lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
            total_lines += lines
        files.append(FileRecord(rel, stat.st_size, _hash_file(path), lines))

        if path.name in DEPENDENCY_FILES or "requirements" in path.name.lower():
            dependency_paths.append(rel)

        if text is None:
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            for title, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(
                        _finding_id("secret", rel, line_no, title), "critical", "security",
                        title, rel, line_no, "Potential hard-coded credential or token detected. Review and remove it from source control."
                    ))
            for title, pattern in QUALITY_PATTERNS:
                if pattern.search(line):
                    severity = "high" if title in {"eval usage", "exec usage"} else "low"
                    findings.append(Finding(
                        _finding_id("quality", rel, line_no, title), severity, "quality",
                        title, rel, line_no, "Code-quality rule matched. Review whether this pattern is justified, tested, or replaceable."
                    ))

    files.sort(key=lambda x: x.path)
    fingerprint = _fingerprint(files)
    critical = sum(x.severity == "critical" for x in findings)
    high = sum(x.severity == "high" for x in findings)
    low = sum(x.severity == "low" for x in findings)

    return {
        "repository": root.name,
        "root": str(root),
        "fingerprint": fingerprint,
        "scanned_at": None,
        "file_count": len(files),
        "total_lines": total_lines,
        "dependency_files": dependency_paths,
        "files": [asdict(x) for x in files],
        "findings": [asdict(x) for x in findings],
        "summary": {"critical": critical, "high": high, "low": low, "total": len(findings)},
    }


def compare_manifests(previous: dict | None, current: dict) -> dict:
    if not previous:
        return {"changed": True, "added": [x["path"] for x in current["files"]], "removed": [], "modified": [], "dependency_changed": bool(current["dependency_files"]), "reason": "No prior scan exists."}
    old = {x["path"]: x for x in previous.get("files", [])}
    new = {x["path"]: x for x in current.get("files", [])}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    modified = sorted(path for path in set(old) & set(new) if old[path]["sha256"] != new[path]["sha256"] or old[path]["size"] != new[path]["size"])
    dep_old = {p for p in previous.get("dependency_files", [])}
    dep_new = {p for p in current.get("dependency_files", [])}
    dep_changed = dep_old != dep_new or any(p in dep_new for p in modified)
    changed = bool(added or removed or modified or previous.get("fingerprint") != current.get("fingerprint"))
    if not changed:
        reason = "No repository changes detected since the last accepted scan."
    elif added or removed or modified:
        reason = "Repository content changed since the last completed scan."
    else:
        reason = "Repository fingerprint changed without a retained file-level delta."
    return {"changed": changed, "added": added, "removed": removed, "modified": modified, "dependency_changed": dep_changed, "reason": reason}
