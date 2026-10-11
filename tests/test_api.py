from fastapi.testclient import TestClient
from app.main import app


def test_core_api_flow():
    client = TestClient(app)
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/stocks').status_code == 200
    assert client.post('/api/repository/scan').status_code == 200
    status = client.get('/api/repository/status').json()
    assert status['state'] == 'CURRENT'
    assert client.post('/api/repository/simulate-overnight-update').status_code == 200
    status = client.get('/api/repository/status').json()
    assert status['state'] == 'STALE'
    analysis = client.get('/api/analyze?symbol=RELIANCE&interval=5')
    assert analysis.status_code == 200
    assert analysis.json()['trusted_signal'] == 'REVALIDATE'
    assert client.post('/api/repository/reset').status_code == 200
