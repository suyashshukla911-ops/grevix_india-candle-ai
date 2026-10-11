
from fastapi.testclient import TestClient
from app.main import app

def test_bootstrap():
    c=TestClient(app)
    r=c.get("/api/bootstrap")
    assert r.status_code==200
    j=r.json()
    assert "repository" in j
    assert j["gate"]==0.90
