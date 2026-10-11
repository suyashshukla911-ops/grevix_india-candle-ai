
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.db import audit

EXCLUDE_DIRS = {".git",".venv","venv","__pycache__",".pytest_cache","node_modules","runtime","data_cache"}
DEPENDENCY_NAMES = {
    "requirements.txt","requirements-dev.txt","pyproject.toml","package.json",
    "package-lock.json","poetry.lock","Pipfile","Pipfile.lock"
}
COMPONENT_RULES = [
    ("model", lambda p: "app/ml" in p.as_posix().replace("\\","/")),
    ("data", lambda p: "app/data" in p.as_posix().replace("\\","/")),
    ("services", lambda p: "app/services" in p.as_posix().replace("\\","/")),
    ("frontend", lambda p: "frontend" in p.as_posix().replace("\\","/")),
    ("dependencies", lambda p: p.name in DEPENDENCY_NAMES),
    ("config", lambda p: p.name in {"config.py",".env.example","Dockerfile"}),
    ("docs", lambda p: p.suffix.lower() in {".md",".rst"}),
]

RISK = {
    "model": ("HIGH", 1.00, "Model / feature logic changed"),
    "services": ("HIGH", 0.90, "Service orchestration changed"),
    "dependencies": ("HIGH", 0.90, "Runtime dependency changed"),
    "data": ("HIGH", 0.85, "Market/news provider changed"),
    "config": ("MEDIUM", 0.65, "Configuration changed"),
    "frontend": ("LOW", 0.25, "Presentation layer changed"),
    "docs": ("LOW", 0.05, "Documentation changed"),
    "other": ("MEDIUM", 0.50, "Other tracked file changed"),
}

class RepositoryMonitor:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or settings.monitored_repo)
        self.path.mkdir(parents=True, exist_ok=True)
        self.state_path = settings.runtime_dir / "repository_state.json"
        self.source_meta = settings.runtime_dir / "repository_source.json"

    def set_path(self, path: str) -> dict[str, Any]:
        p = Path(path).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            raise ValueError("Repository path must exist and be a directory.")
        self.path = p
        meta = {"type":"local","path":str(p)}
        self.source_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        audit("repository-source", "changed", meta)
        return meta

    def clone_public_github(self, url: str) -> dict[str, Any]:
        if not url.startswith(("https://github.com/", "http://github.com/")):
            raise ValueError("Only public GitHub HTTPS URLs are supported in the competition build.")
        target = settings.runtime_dir / "github_repo"
        if target.exists():
            shutil.rmtree(target)
        subprocess.run(["git","clone","--depth","1",url,str(target)], check=True, capture_output=True, text=True, timeout=90)
        self.path = target
        meta = {"type":"github-public","url":url,"path":str(target)}
        self.source_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        audit("repository-source", "github-cloned", meta)
        return meta

    def source(self) -> dict[str, Any]:
        if self.source_meta.exists():
            try:
                return json.loads(self.source_meta.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"type":"local","path":str(self.path)}

    def _files(self):
        for p in self.path.rglob("*"):
            if not p.is_file():
                continue
            if any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            yield p

    @staticmethod
    def _component(rel: Path) -> str:
        rp = rel.as_posix()
        for name, rule in COMPONENT_RULES:
            try:
                if rule(rel):
                    return name
            except Exception:
                continue
        return "other"

    @staticmethod
    def _hash_file(p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def manifest(self) -> dict[str, Any]:
        files = {}
        components = {}
        for p in self._files():
            rel = p.relative_to(self.path)
            digest = self._hash_file(p)
            component = self._component(rel)
            files[rel.as_posix()] = {"sha256":digest,"size":p.stat().st_size,"component":component}
            components.setdefault(component, []).append((rel.as_posix(), digest))
        component_hashes = {}
        for c, rows in components.items():
            payload = json.dumps(sorted(rows), separators=(",",":")).encode()
            component_hashes[c] = hashlib.sha256(payload).hexdigest()
        overall = hashlib.sha256(
            json.dumps(sorted((k,v["sha256"]) for k,v in files.items()), separators=(",",":")).encode()
        ).hexdigest()
        return {
            "fingerprint": overall,
            "files": files,
            "components": component_hashes,
            "generated_at": datetime.now().astimezone().isoformat(),
            "path": str(self.path),
        }

    def _security_scan(self):
        findings = []
        patterns = [
            ("HIGH","security/dynamic-eval",re.compile(r"\beval\s*\("),"Dynamic eval() can execute untrusted code."),
            ("HIGH","security/exec",re.compile(r"\bexec\s*\("),"Dynamic exec() can execute untrusted code."),
            ("HIGH","security/private-key",re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),"Private key material appears in source."),
            ("HIGH","security/token",re.compile(r"(?i)(api[_-]?key|secret|token)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]"),"Credential-like hardcoded value appears in source."),
            ("MEDIUM","quality/shell-true",re.compile(r"shell\s*=\s*True"),"Shell execution broadens command-injection risk."),
            ("LOW","quality/debug-print",re.compile(r"\bprint\s*\("),"Debug print remains in tracked code."),
            ("LOW","quality/todo",re.compile(r"\b(?:TODO|FIXME)\b"),"TODO/FIXME marker remains in tracked source."),
        ]
        for p in self._files():
            if p.suffix.lower() not in {".py",".js",".ts",".tsx",".jsx",".json",".yml",".yaml",".toml",".ini",".env"}:
                continue
            try:
                text = p.read_text(encoding="utf-8",errors="ignore")
            except Exception:
                continue
            rel = p.relative_to(self.path).as_posix()
            for sev, rule, pattern, msg in patterns:
                for match in pattern.finditer(text):
                    line = text[:match.start()].count("\n")+1
                    findings.append({"severity":sev,"rule":rule,"message":msg,"file":rel,"line":line})
                    if len([x for x in findings if x["file"]==rel and x["rule"]==rule]) >= 3:
                        break
        return findings

    def _impact(self, before: dict[str,Any] | None, after: dict[str,Any]) -> dict[str,Any]:
        if not before:
            return {"added":len(after["files"]),"modified":0,"removed":0,"dependency_change":False,"items":[],"revalidation":"FULL"}
        old = before.get("files",{})
        new = after.get("files",{})
        added = sorted(set(new)-set(old))
        removed = sorted(set(old)-set(new))
        modified = sorted(k for k in set(old)&set(new) if old[k]["sha256"] != new[k]["sha256"])
        items=[]
        max_risk=0.0
        for kind, paths in [("added",added),("modified",modified),("removed",removed)]:
            for path in paths:
                component = (new.get(path) or old.get(path)).get("component","other")
                sev, score, reason = RISK.get(component,RISK["other"])
                max_risk=max(max_risk,score)
                items.append({"kind":kind,"path":path,"component":component,"impact":sev,"reason":reason})
        dep = any((new.get(p) or old.get(p)).get("component")=="dependencies" for p in set(added+removed+modified))
        if dep:
            max_risk=max(max_risk,0.9)
        if max_risk >= 0.9:
            depth="FULL"
        elif max_risk >= 0.6:
            depth="MODEL + DATA"
        elif max_risk >= 0.2:
            depth="TARGETED"
        else:
            depth="LIGHT"
        return {
            "added":len(added),"modified":len(modified),"removed":len(removed),
            "dependency_change":dep,"items":items[:80],
            "revalidation":depth
        }

    def scan(self, accept: bool = False) -> dict[str,Any]:
        current = self.manifest()
        findings = self._security_scan()
        baseline = None
        if self.state_path.exists():
            try:
                baseline = json.loads(self.state_path.read_text(encoding="utf-8")).get("accepted")
            except Exception:
                baseline = None
        impact = self._impact(baseline, current)
        current_match = bool(baseline and baseline.get("fingerprint")==current.get("fingerprint"))
        state = "CURRENT" if current_match else ("AWAITING BASELINE" if baseline is None else "STALE")
        if accept:
            self.state_path.write_text(json.dumps({
                "accepted": current,
                "accepted_findings": findings,
                "accepted_at": datetime.now().astimezone().isoformat()
            }, indent=2), encoding="utf-8")
            audit("repository-scan","accepted",{"fingerprint":current["fingerprint"],"findings":findings,"impact":impact})
            state="CURRENT"
        else:
            audit("repository-check",state.lower(),{"fingerprint":current["fingerprint"],"impact":impact})
        # Optional local enterprise-style hooks. These are intentionally optional:
        # if Bandit or pip-audit is installed, their findings are imported; the
        # competition build does not require them and does not call a remote API.
        if shutil.which("bandit"):
            try:
                proc = subprocess.run(
                    ["bandit", "-r", str(self.path / "app"), "-f", "json", "-q"],
                    capture_output=True, text=True, timeout=25
                )
                payload = json.loads(proc.stdout or "{}")
                for issue in payload.get("results", []):
                    findings.append({
                        "severity": str(issue.get("issue_severity","LOW")).upper(),
                        "rule": f"bandit/{issue.get('test_id','unknown')}",
                        "message": issue.get("issue_text","Bandit finding"),
                        "file": str(issue.get("filename","")).replace(str(self.path)+"/",""),
                        "line": int(issue.get("line_number") or 0),
                    })
            except Exception:
                pass
        if shutil.which("pip-audit") and (self.path / "requirements.txt").exists():
            try:
                proc = subprocess.run(
                    ["pip-audit", "-r", str(self.path / "requirements.txt"), "--format", "json"],
                    capture_output=True, text=True, timeout=30
                )
                payload = json.loads(proc.stdout or "[]")
                for pkg in (payload if isinstance(payload, list) else payload.get("dependencies", [])):
                    vulns = pkg.get("vulns", [])
                    for vuln in vulns:
                        findings.append({
                            "severity": "HIGH",
                            "rule": f"pip-audit/{vuln.get('id','unknown')}",
                            "message": f"{pkg.get('name','dependency')}: {vuln.get('description','dependency vulnerability')}",
                            "file": "requirements.txt",
                            "line": 0,
                        })
            except Exception:
                pass
        security_score = max(0, 100 - sum({"HIGH":35,"MEDIUM":15,"LOW":4}.get(f["severity"],1) for f in findings))
        return {
            "state":state,
            "source":self.source(),
            "current":current,
            "accepted":baseline,
            "impact":impact,
            "findings":findings,
            "security_score":security_score,
            "revalidation_required": state == "STALE",
        }

    def _restore_demo_workspace(self):
        if self.path.resolve() != settings.monitored_repo.resolve():
            return
        seed = {
            "app/ml/model.py": "# monitored model component\nMODEL_VERSION = 'demo-1.0'\n",
            "app/data/provider.py": "# monitored market provider component\nPROVIDER = 'yahoo'\n",
            "app/services/trust.py": "# monitored trust component\n",
            "frontend/index.html": "<!-- monitored presentation component -->\n",
            "requirements.txt": "numpy>=2.1\nscikit-learn>=1.6\n",
            "README.md": "# Monitored repository sample\n",
        }
        for rel, content in seed.items():
            p=self.path/rel
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(content,encoding="utf-8")

    def reset(self):
        if self.state_path.exists():
            self.state_path.unlink()
        self._restore_demo_workspace()
        audit("repository-reset","ok",{"path":str(self.path)})
        return self.scan(False)

    def simulate_overnight(self):
        # Work only inside the monitored sample repository, never inside the application source.
        if self.path.resolve() != settings.monitored_repo.resolve():
            raise ValueError("Overnight simulation is available only for the bundled demo workspace.")
        model_file = self.path / "app" / "ml" / "model.py"
        dep_file = self.path / "requirements.txt"
        model_file.parent.mkdir(parents=True, exist_ok=True)
        base = model_file.read_text(encoding="utf-8") if model_file.exists() else "# demo monitored model\n"
        # Make each simulation reproducibly different from the accepted baseline.
        stamp = datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
        model_file.write_text(base.rstrip() + f"\n# overnight update {stamp}: feature threshold changed\n", encoding="utf-8")
        dep_file.write_text("numpy>=2.1\nscikit-learn>=1.7\n# overnight dependency update\n", encoding="utf-8")
        audit("overnight-simulation","changed",{"model_file":str(model_file),"dependency_file":str(dep_file)})
        return self.scan(False)
