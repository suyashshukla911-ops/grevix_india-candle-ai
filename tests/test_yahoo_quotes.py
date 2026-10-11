from pathlib import Path

import pandas as pd

from app.data.yahoo import YahooProvider


def _frame():
    ts = pd.date_range("2026-10-01", periods=70, freq="D", tz="Asia/Kolkata")
    close = [100 + i for i in range(70)]
    return pd.DataFrame({
        "timestamp": ts, "open": close, "high": [x + 1 for x in close],
        "low": [x - 1 for x in close], "close": close, "volume": [1000] * 70
    })


def test_pulse_keeps_unavailable_symbols_visible(tmp_path):
    provider = YahooProvider(cache_dir=str(tmp_path))
    frame = _frame()

    def fake_chart(symbol, interval, days):
        if symbol == "GOOD.NS":
            return frame
        return None

    provider._download_chart_endpoint = fake_chart
    provider._download_yfinance = lambda *args, **kwargs: None
    provider.catalog.get = lambda sym: {"symbol": sym, "name": sym, "exchange": "NSE", "yahoo_symbol": f"{sym}.NS"} if sym in {"GOOD", "BAD"} else None

    rows = provider.pulse(["GOOD", "BAD"])
    assert len(rows) == 2
    assert any(r["symbol"] == "GOOD" and r["data_status"] == "LIVE" for r in rows)
    assert any(r["symbol"] == "BAD" and r["data_status"] == "UNAVAILABLE" for r in rows)


def test_unavailable_symbol_does_not_disable_other_symbols(tmp_path):
    provider = YahooProvider(cache_dir=str(tmp_path))
    frame = _frame()
    calls = []

    def fake_chart(symbol, interval, days):
        calls.append(symbol)
        return frame if symbol == "GOOD.NS" else None

    provider._download_chart_endpoint = fake_chart
    provider._download_yfinance = lambda *args, **kwargs: None
    provider.catalog.get = lambda sym: {"symbol": sym, "name": sym, "exchange": "NSE", "yahoo_symbol": f"{sym}.NS"} if sym in {"BAD", "GOOD"} else None

    first = provider.snapshot_quote("BAD")
    second = provider.snapshot_quote("GOOD")
    assert first["data_status"] == "UNAVAILABLE"
    assert second["data_status"] == "LIVE"
    assert "GOOD.NS" in calls
