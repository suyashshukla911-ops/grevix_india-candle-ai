import pandas as pd

from app.data.yahoo import YahooProvider


def _frame():
    ts = pd.date_range("2026-10-01", periods=70, freq="5min", tz="Asia/Kolkata")
    close = [100 + i * 0.1 for i in range(70)]
    return pd.DataFrame({
        "timestamp": ts,
        "open": close,
        "high": [x + 1 for x in close],
        "low": [x - 1 for x in close],
        "close": close,
        "volume": [1000] * 70,
    })


def test_history_accepts_dataframe_from_chart_endpoint(monkeypatch, tmp_path):
    provider = YahooProvider(cache_dir=str(tmp_path))
    frame = _frame()
    provider._download_chart_endpoint = lambda *args, **kwargs: frame
    provider._download_yfinance = lambda *args, **kwargs: None
    provider._record_no_data = lambda *args, **kwargs: None

    snapshot = provider.history("TCS", "5m", days=5, refresh=True)

    assert snapshot.source == "LIVE"
    assert len(snapshot.frame) == 70
