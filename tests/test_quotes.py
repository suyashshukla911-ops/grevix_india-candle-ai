from fastapi.testclient import TestClient
from app.main import app, market


def test_quotes_endpoint_keeps_unavailable_rows(monkeypatch):
    def fake_pulse(symbols):
        return [
            {"symbol": "TCS", "name": "TCS", "exchange": "NSE", "price": 100.0, "change": 1.0, "change_pct": 1.0, "data_status": "LIVE"},
            {"symbol": "LOHIA", "name": "Lohia", "exchange": "NSE", "price": None, "change": None, "change_pct": None, "data_status": "UNAVAILABLE"},
        ]
    monkeypatch.setattr(market, "pulse", fake_pulse)
    r = TestClient(app).get("/api/quotes?symbols=TCS,LOHIA")
    assert r.status_code == 200
    rows = r.json()["results"]
    assert any(x["symbol"] == "TCS" and x["data_status"] == "LIVE" for x in rows)
    assert any(x["symbol"] == "LOHIA" and x["data_status"] == "UNAVAILABLE" for x in rows)


def test_availability_endpoint_contract(monkeypatch):
    def fake_availability(symbol, intervals):
        return {"symbol": symbol, "intervals": [{"interval": i, "available": i == "1d", "status": "LIVE" if i == "1d" else "UNAVAILABLE", "detail": "test"} for i in intervals]}
    monkeypatch.setattr(market, "availability", fake_availability)
    r = TestClient(app).get("/api/stocks/availability?symbol=LOHIA")
    assert r.status_code == 200
    payload = r.json()
    assert payload["symbol"] == "LOHIA"
    assert len(payload["intervals"]) == 5
