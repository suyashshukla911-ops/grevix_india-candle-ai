
from app.services.repository import RepositoryMonitor

def test_repository_current_stale_current(tmp_path):
    repo_dir=tmp_path/"repo"
    (repo_dir/"app"/"ml").mkdir(parents=True)
    (repo_dir/"app"/"ml"/"model.py").write_text("x=1")
    r=RepositoryMonitor(repo_dir)
    r.state_path=tmp_path/"state.json"
    assert r.scan(False)["state"]=="AWAITING BASELINE"
    assert r.scan(True)["state"]=="CURRENT"
    (repo_dir/"app"/"ml"/"model.py").write_text("x=2")
    s=r.scan(False)
    assert s["state"]=="STALE"
    assert s["impact"]["modified"]==1
    assert r.scan(True)["state"]=="CURRENT"

def test_security_scan(tmp_path):
    repo_dir=tmp_path/"repo"
    (repo_dir/"app").mkdir(parents=True)
    (repo_dir/"app"/"bad.py").write_text("x=eval('1+1')")
    r=RepositoryMonitor(repo_dir)
    r.state_path=tmp_path/"state.json"
    result=r.scan(False)
    assert any(x["rule"]=="security/dynamic-eval" for x in result["findings"])
