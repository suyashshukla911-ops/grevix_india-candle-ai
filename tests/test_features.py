
import numpy as np
import pandas as pd

from app.ml.features import FEATURES, add_targets, build_features, prepare_training_frame


def mock_candles(n=800):
    ts = pd.date_range("2026-08-01 09:15", periods=n, freq="5min", tz="Asia/Kolkata")
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.15, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.01, 0.12, n)
    low = np.minimum(open_, close) - rng.uniform(0.01, 0.12, n)
    vol = rng.integers(1000, 10000, n)
    return pd.DataFrame({"timestamp":ts,"open":open_,"high":high,"low":low,"close":close,"volume":vol,"oi":0})


def test_features_are_numeric():
    df = mock_candles()
    out = prepare_training_frame(df)
    assert set(FEATURES).issubset(out.columns)
    assert len(out) > 100
    assert np.isfinite(out[FEATURES].to_numpy()).all()
