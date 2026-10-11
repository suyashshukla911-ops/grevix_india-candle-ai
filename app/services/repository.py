from __future__ import annotations

import ast
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import ROOT_DIR, settings
from app.services.db import audit

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules",
    "runtime", "data_cache", "archive", "dist", "build",
}
DEPENDENCY_NAMES = {
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "package.json",
    "package-lock.json", "poetry.lock", "Pipfile", "Pipfile.lock", "environment.yml",
}
TEXT_EXTS = {".py",".js",".ts",".tsx",".jsx",".json",".yml",".yaml",".toml",".ini",".env",".java",".go",".rs",".c",".cpp",".sql"}

COMPONENT_RULES = [
    ("model", lambda p: any(x in p.as_posix().lower() for x in ("app/ml/", "models/", "/model", "/predict", "/feature"))),
    ("data", lambda p: any(x in p.as_posix().lower() for x in ("app/data/", "data/", "/provider", "/dataset"))),
    ("services", lambda p: any(x in p.as_posix().lower() for x in ("app/services/", "/service", "/api/"))),
    ("frontend", lambda p: any(x in p.as_posix().lower() for x in ("frontend/", "/web/", "/ui/", "/static/"))),
    ("dependencies", lambda p: p.name.lower() in {x.lower() for x in DEPENDENCY_NAMES}),
    ("config", lambda p: p.name.lower() in {"config.py", ".env.example", ".env", "dockerfile", "docker-compose.yml", "settings.py", "render.yaml"}),
    ("docs", lambda p: p.suffix.lower() in {".md",".rst",".txt"} and p.name.lower() not in DEPENDENCY_NAMES),
]
RISK = {
    "model": ("HIGH", 1.0, "Prediction/model logic changed"),
    "services": ("HIGH", 0.9, "Service/API orchestration changed"),
    "dependencies": ("HIGH", 0.9, "Runtime dependency changed"),
    "data": ("HIGH", 0.85, "Market/data provider changed"),
    "config": ("MEDIUM", 0.65, "Runtime configuration changed"),
    "frontend": ("LOW", 0.15, "Presentation layer changed"),
    "docs": ("LOW", 0.05, "Documentation changed"),
    "other": ("MEDIUM", 0.5, "Other tracked file changed"),
}

def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def _finding_key(f: dict[str, Any]) -> str:
    return _json_hash((f.get("severity"), f.get("rule"), f.get("file"), f.get("line"), f.get("message")))

class RepositoryMonitor:
    """Repository auditor with a real model workspace and isolated external clones.

    The default model workspace is the actual application repository. External GitHub
    repositories are cloned into a per-session sandbox and are audit-only until explicitly
    bound to model trust.
    """
    def __init__(self, session_id: str | Path = "model", path: Path | None = None):
        # Backwards-compatible form: RepositoryMonitor(path)
        if isinstance(session_id, Path) and path is None:
            path = session_id
            session_id = f"test-{hashlib.sha256(str(path).encode()).hexdigest()[:12]}"
        self.session_id = re.sub(r"[^A-Za-z0-9_-]", "", str(session_id or "model"))[:64] or "model"
        self.session_dir = settings.runtime_dir / "sessions" / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._explicit_path = path is not None
        self.path = Path(path or settings.monitored_repo).resolve()
        self._path_override = path is not None
        self.state_path = self.session_dir / "repository_state.json"
        self.source_meta = self.session_dir / "repository_source.json"
        self._hash_cache: dict[str, tuple[int,int,int,str]] = {}
        self._manifest_cache: dict[str, Any] | None = None
        self._findings_cache: tuple[str, list[dict[str, Any]]] | None = None

    def source(self) -> dict[str, Any]:
        if self._explicit_path or getattr(self, "_path_override", False):
            return {"type": "local", "scope": "model", "path": str(self.path)}
        if self.source_meta.exists():
            try:
                data = json.loads(self.source_meta.read_text(encoding="utf-8"))
                if data.get("path"):
                    self.path = Path(data["path"]).resolve()
                return data
            except Exception:
                pass
        return {"type": "local", "scope": "model", "path": str(settings.monitored_repo.resolve())}

    def _save_source(self, meta: dict[str, Any]) -> dict[str, Any]:
        self.source_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        if self.state_path.exists():
            self.state_path.unlink()
        self._manifest_cache = None
        self._findings_cache = None
        self._hash_cache.clear()
        audit("repository-source", "changed", {"session": self.session_id, **meta})
        return meta

    def _cleanup_clones(self) -> None:
        base = self.session_dir / "github_repos"
        if not base.exists():
            return
        dirs = sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
        for old in dirs[settings.max_clones:]:
            shutil.rmtree(old, ignore_errors=True)

    def _dir_size_mb(self, path: Path) -> float:
        total = 0
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                continue
        return total / (1024 * 1024)

    def clone_public_github(self, url: str) -> dict[str, Any]:
        if not re.match(r"^https?://github\.com/[^/]+/[^/]+/?$", url.strip()):
            raise ValueError("Enter a public GitHub repository URL like https://github.com/owner/repository.")
        clean = url.rstrip("/")
        repo_slug = re.sub(r"[^A-Za-z0-9_.-]", "_", clean.rsplit("/", 1)[-1] or "repository")
        target = self.session_dir / "github_repos" / f"{repo_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git","clone","--depth","1","--no-tags",clean,str(target)],
                check=True, capture_output=True, text=True, timeout=180,
            )
        except FileNotFoundError as exc:
            raise ValueError("Git is not installed or not available on PATH.") from exc
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(target, ignore_errors=True)
            raise ValueError((exc.stderr or exc.stdout or "Git clone failed.").strip()[-1200:]) from exc
        if self._dir_size_mb(target) > settings.max_clone_mb:
            shutil.rmtree(target, ignore_errors=True)
            raise ValueError(f"Repository exceeds the {settings.max_clone_mb} MB safety limit.")
        self._cleanup_clones()
        self.path = target.resolve()
        return self._save_source({
            "type":"github-public","scope":"external","url":clean,
            "path":str(self.path),"remote_commit":self._git_head(self.path)
        })

    @staticmethod
    def _git_head(path: Path) -> str | None:
        try:
            return subprocess.run(["git","-C",str(path),"rev-parse","HEAD"],check=True,capture_output=True,text=True,timeout=15).stdout.strip()
        except Exception:
            return None

    def refresh_public_github(self) -> dict[str, Any]:
        source = self.source()
        if source.get("type") != "github-public":
            raise ValueError("No public GitHub repository is currently monitored in this session.")
        try:
            status = subprocess.run(["git","-C",str(self.path),"status","--porcelain"],check=True,capture_output=True,text=True,timeout=15).stdout.strip()
            if status:
                raise ValueError("Local changes are present. Run CHECK FOR UPDATES before refreshing from GitHub.")
            subprocess.run(["git","-C",str(self.path),"fetch","--depth","1","origin","HEAD"],check=True,capture_output=True,text=True,timeout=180)
            subprocess.run(["git","-C",str(self.path),"reset","--hard","FETCH_HEAD"],check=True,capture_output=True,text=True,timeout=60)
        except subprocess.CalledProcessError as exc:
            raise ValueError((exc.stderr or exc.stdout or "Git refresh failed.").strip()[-1200:]) from exc
        source["remote_commit"] = self._git_head(self.path)
        self.source_meta.write_text(json.dumps(source, indent=2), encoding="utf-8")
        self._manifest_cache = None; self._findings_cache = None; self._hash_cache.clear()
        return self.scan(False)

    def bind_to_model(self) -> dict[str, Any]:
        source = self.source()
        if source.get("type") != "github-public":
            return self.scan(False)
        source["scope"] = "model"
        return self._save_source(source)

    def _files(self):
        if not self.path.exists():
            return
        for base, dirs, files in os.walk(self.path, topdown=True, onerror=lambda _err: None):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            base_path = Path(base)
            for filename in files:
                p = base_path / filename
                try:
                    if p.stat().st_size > 5 * 1024 * 1024:
                        continue
                except OSError:
                    continue
                yield p

    @staticmethod
    def _component(rel: Path) -> str:
        for name, rule in COMPONENT_RULES:
            try:
                if rule(rel):
                    return name
            except Exception:
                pass
        return "other"

    def _hash_file(self, p: Path) -> str:
        st = p.stat()
        k = p.as_posix()
        hit = self._hash_cache.get(k)
        if hit and hit[:3] == (st.st_mtime_ns, st.st_ctime_ns, st.st_size):
            return hit[3]
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        digest = h.hexdigest()
        self._hash_cache[k] = (st.st_mtime_ns, st.st_ctime_ns, st.st_size, digest)
        return digest

    def manifest(self) -> dict[str, Any]:
        new_files: dict[str, dict[str, Any]] = {}
        components: dict[str, list[tuple[str,str]]] = {}
        for p in self._files() or []:
            rel = p.relative_to(self.path).as_posix()
            comp = self._component(Path(rel))
            digest = self._hash_file(p)
            new_files[rel] = {"sha256":digest,"size":p.stat().st_size,"component":comp}
            components.setdefault(comp,[]).append((rel,digest))
        component_hashes = {c:_json_hash(sorted(rows)) for c,rows in components.items()}
        overall = _json_hash(sorted((k,v["sha256"]) for k,v in new_files.items()))
        result={"fingerprint":overall,"files":new_files,"components":component_hashes,
                "generated_at":datetime.now().astimezone().isoformat(),"path":str(self.path)}
        self._manifest_cache=result
        return result

    def _ast_python_findings(self, path: Path, text: str) -> list[dict[str,Any]]:
        findings=[]
        try:
            tree=ast.parse(text, filename=str(path))
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name=node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name=f"{getattr(node.func.value,'id','')}.{node.func.attr}"
                if name in {"eval","exec"}:
                    rule = "security/dynamic-eval" if name == "eval" else "security/dynamic-exec"
                    findings.append({"severity":"HIGH","rule":rule,"message":f"Dynamic {name}() can execute untrusted code.","file":str(path.relative_to(self.path)),"line":node.lineno,"source":"ast"})
                elif name in {"os.system","subprocess.os.system"}:
                    findings.append({"severity":"HIGH","rule":"security/os-system","message":"os.system executes a shell command; prefer a validated argument list.","file":str(path.relative_to(self.path)),"line":node.lineno,"source":"ast"})
                elif name.endswith("pickle.loads"):
                    findings.append({"severity":"HIGH","rule":"security/pickle-loads","message":"pickle.loads can execute arbitrary code when input is untrusted.","file":str(path.relative_to(self.path)),"line":node.lineno,"source":"ast"})
                elif name.endswith("yaml.load") or name == "yaml.load":
                    findings.append({"severity":"HIGH","rule":"security/yaml-load","message":"yaml.load can construct unsafe objects; use safe_load for untrusted YAML.","file":str(path.relative_to(self.path)),"line":node.lineno,"source":"ast"})
                if isinstance(node.func, ast.Attribute):
                    for kw in node.keywords:
                        if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                            findings.append({"severity":"HIGH","rule":"security/verify-false","message":"TLS certificate verification is disabled.","file":str(path.relative_to(self.path)),"line":node.lineno,"source":"ast"})
                        if isinstance(kw.value, ast.JoinedStr) and name in {"execute","executemany","cursor.execute","conn.execute"}:
                            findings.append({"severity":"MEDIUM","rule":"security/sql-fstring","message":"SQL execution is built from an f-string; parameterize the query.","file":str(path.relative_to(self.path)),"line":node.lineno,"source":"ast"})
        return findings

    def _security_scan(self, fingerprint: str) -> list[dict[str,Any]]:
        if self._findings_cache and self._findings_cache[0] == fingerprint:
            return list(self._findings_cache[1])
        findings=[]
        token_re=re.compile(r"(?i)\b(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD|DB_PASSWORD|PRIVATE_KEY)\s*=\s*['\"]([^'\"]+)['\"]")
        for p in self._files() or []:
            if p.name.lower() != ".env" and p.suffix.lower() not in TEXT_EXTS:
                continue
            try:
                text=p.read_text(encoding="utf-8",errors="ignore")
            except Exception:
                continue
            rel=str(p.relative_to(self.path))
            if p.suffix.lower()==".py":
                findings.extend(self._ast_python_findings(p,text))
            if token_re.search(text):
                for m in token_re.finditer(text):
                    value=m.group(1).strip()
                    if value and value.lower() not in {"change-me","your-secret-here","your_api_key","example","changeme",""}:
                        findings.append({"severity":"HIGH","rule":"security/hardcoded-secret","message":"Credential-like secret assignment appears in tracked text.","file":rel,"line":text[:m.start()].count("\n")+1,"source":"pattern"})
                        break
            if p.suffix.lower() in {".js",".ts",".tsx",".jsx"} and re.search(r"\beval\s*\(",text):
                findings.append({"severity":"HIGH","rule":"security/js-eval","message":"JavaScript eval() can execute untrusted code.","file":rel,"line":text[:re.search(r"\beval\s*\(",text).start()].count("\n")+1,"source":"pattern"})
            if "shell=True" in text and p.suffix.lower()==".py":
                pos=text.find("shell=True")
                findings.append({"severity":"MEDIUM","rule":"quality/shell-true","message":"Shell execution broadens command-injection risk.","file":rel,"line":text[:pos].count("\n")+1,"source":"pattern"})
        if settings.deep_security_scan:
            findings.extend(self._deep_security_findings())
        # Deduplicate by stable finding signature.
        uniq={}
        for f in findings:
            uniq[_finding_key(f)]=f
        self._findings_cache=(fingerprint,list(uniq.values()))
        return list(uniq.values())

    def _deep_security_findings(self) -> list[dict[str,Any]]:
        findings=[]
        bandit = shutil.which("bandit")
        if bandit:
            try:
                result=subprocess.run([bandit,"-r",str(self.path),"-x",str(self.path/"runtime"),str(self.path/".venv"),str(self.path/"archive"),"-f","json","-q"],capture_output=True,text=True,timeout=60)
                payload=json.loads(result.stdout or "{}")
                for item in payload.get("results",[])[:100]:
                    findings.append({
                        "severity":str(item.get("issue_severity","LOW")).upper(),"rule":f"bandit/{item.get('test_id','unknown')}",
                        "message":item.get("issue_text","Bandit finding"),
                        "file":str(item.get("filename","")).replace(str(self.path),"").lstrip("/\\"),
                        "line":int(item.get("line_number") or 0),"source":"bandit",
                    })
            except Exception:
                pass
        pip_audit = shutil.which("pip-audit")
        if pip_audit:
            try:
                result=subprocess.run([pip_audit,"-f","json"],capture_output=True,text=True,timeout=90)
                payload=json.loads(result.stdout or "[]")
                items=payload if isinstance(payload,list) else payload.get("dependencies",[])
                for dep in items:
                    vulns=dep.get("vulns") or dep.get("vulnerabilities") or []
                    for vuln in vulns[:10]:
                        findings.append({
                            "severity":"HIGH","rule":f"dependency/{vuln.get('id','pip-audit')}",
                            "message":f"Installed dependency {dep.get('name','unknown')} {dep.get('version','')} has a reported vulnerability.",
                            "file":"requirements.txt","line":0,"source":"pip-audit",
                        })
            except Exception:
                pass
        return findings

    def _impact(self,before:dict[str,Any]|None,after:dict[str,Any]) -> dict[str,Any]:
        if not before:
            return {"added":len(after["files"]),"modified":0,"removed":0,"dependency_change":False,
                    "prediction_affecting":True,"items":[],"revalidation":"FULL"}
        old,new=before.get("files",{}),after.get("files",{})
        added=sorted(set(new)-set(old)); removed=sorted(set(old)-set(new))
        modified=sorted(k for k in set(old)&set(new) if old[k]["sha256"]!=new[k]["sha256"])
        items=[]; max_risk=0.0; prediction_affecting=False
        for kind,paths in (("added",added),("modified",modified),("removed",removed)):
            for path in paths:
                component=(new.get(path) or old.get(path)).get("component","other")
                sev,score,reason=RISK.get(component,RISK["other"])
                max_risk=max(max_risk,score)
                affects=component in {"model","services","dependencies","data","config"}
                prediction_affecting |= affects
                items.append({"kind":kind,"path":path,"component":component,"impact":sev,"reason":reason,"prediction_affecting":affects})
        dep=any((new.get(p) or old.get(p)).get("component")=="dependencies" for p in added+removed+modified)
        if dep: max_risk=max(max_risk,0.9); prediction_affecting=True
        if not items: depth="NONE"
        elif max_risk>=0.9: depth="FULL"
        elif max_risk>=0.6: depth="MODEL + DATA"
        elif max_risk>=0.2: depth="TARGETED"
        else: depth="AUDIT-ONLY"
        return {"added":len(added),"modified":len(modified),"removed":len(removed),"dependency_change":dep,
                "prediction_affecting":prediction_affecting,"items":items[:120],"revalidation":depth}

    def scan(self, accept: bool=False, record_audit: bool=True) -> dict[str,Any]:
        source=self.source()
        current=self.manifest()
        findings=self._security_scan(current["fingerprint"])
        baseline=None
        accepted_findings=[]
        if self.state_path.exists():
            try:
                state=json.loads(self.state_path.read_text(encoding="utf-8"))
                baseline=state.get("accepted")
                accepted_findings=state.get("accepted_findings") or []
                if baseline and baseline.get("path")!=current.get("path"):
                    baseline=None; accepted_findings=[]
            except Exception:
                baseline=None
        impact=self._impact(baseline,current)
        match=bool(baseline and baseline.get("fingerprint")==current.get("fingerprint"))
        state="CURRENT" if match else ("AWAITING BASELINE" if baseline is None else "STALE")
        if accept:
            self.state_path.write_text(json.dumps({
                "accepted":current,"accepted_findings":findings,
                "accepted_at":datetime.now().astimezone().isoformat(),"scope":source.get("scope","model")
            },indent=2),encoding="utf-8")
            baseline=current; accepted_findings=findings; state="CURRENT"
            if record_audit: audit("repository-scan","accepted",{"session":self.session_id,"fingerprint":current["fingerprint"],"findings":findings,"impact":impact})
        elif record_audit:
            audit("repository-check",state.lower(),{"session":self.session_id,"fingerprint":current["fingerprint"],"impact":impact})
        accepted_keys={_finding_key(f) for f in accepted_findings}
        for finding in findings:
            finding["accepted_baseline"] = _finding_key(finding) in accepted_keys
            finding["blocking"] = finding.get("severity") == "HIGH" and not finding["accepted_baseline"]
        new_high=[f for f in findings if f.get("severity")=="HIGH" and f.get("blocking")]
        severity_counts={s:0 for s in ("HIGH","MEDIUM","LOW")}
        for f in findings: severity_counts[f.get("severity","LOW")]=severity_counts.get(f.get("severity","LOW"),0)+1
        score=max(0,100-sum({"HIGH":30,"MEDIUM":10,"LOW":2}.get(f.get("severity","LOW"),1) for f in new_high))
        security_blocking=bool(new_high)
        return {
            "state":state,"scope":source.get("scope","model"),"source":source,"current":current,"accepted":baseline,
            "impact":impact,"findings":findings,"new_high_findings":new_high,"severity_counts":severity_counts,
            "security_score":score,"security_blocking":security_blocking,
            "revalidation_required":bool((state=="STALE" and source.get("scope")=="model" and impact.get("prediction_affecting")) or security_blocking),
            "baseline_definition":"The accepted baseline is a cryptographic snapshot of tracked files, component fingerprints, dependency state and accepted findings. It is a version record, not a security certification.",
            "monitoring_definition":"Every later check recomputes the manifest and compares it with the accepted baseline. External repositories are audited in an isolated clone; they affect stock-model trust only after explicit binding.",
        }

    def reset(self):
        self.path=settings.monitored_repo.resolve()
        self._save_source({"type":"local","scope":"model","path":str(self.path)})
        if self.state_path.exists(): self.state_path.unlink()
        self._manifest_cache=None; self._findings_cache=None; self._hash_cache.clear()
        audit("repository-reset","ok",{"session":self.session_id,"path":str(self.path)})
        return self.scan(False)

    def simulate_overnight(self):
        if self.path.resolve()!=settings.monitored_repo.resolve():
            raise ValueError("The overnight simulation only applies to the built-in model environment.")
        model_file=settings.monitored_repo / "app" / "ml" / "model.py"
        config_file=settings.monitored_repo / "app" / "config.py"
        dep_file=settings.monitored_repo / "requirements.txt"
        stamp=datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
        model_text=model_file.read_text(encoding="utf-8")
        model_file.write_text(model_text.rstrip()+f"\n# AFTERCODE_SIMULATION: prediction environment updated {stamp}\n",encoding="utf-8")
        config_text=config_file.read_text(encoding="utf-8")
        config_text=re.sub(r"^AFTERCODE_ENVIRONMENT_VERSION\s*=.*$", f"AFTERCODE_ENVIRONMENT_VERSION = '{stamp}'", config_text, flags=re.MULTILINE)
        if "AFTERCODE_ENVIRONMENT_VERSION" not in config_text:
            config_text=config_text.rstrip()+f"\nAFTERCODE_ENVIRONMENT_VERSION = '{stamp}'\n"
        config_file.write_text(config_text,encoding="utf-8")
        dep=dep_file.read_text(encoding="utf-8")
        dep_file.write_text(dep.rstrip()+f"\n# AFTERCODE_DEPENDENCY_UPDATE: verified configuration changed {stamp}\n",encoding="utf-8")
        self._manifest_cache=None; self._findings_cache=None; self._hash_cache.clear()
        audit("overnight-simulation","changed",{"session":self.session_id,"files":["app/ml/model.py","app/config.py","requirements.txt"]})
        return self.scan(False)
