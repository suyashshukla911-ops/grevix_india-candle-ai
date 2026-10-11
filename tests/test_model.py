
import numpy as np
import pandas as pd

from app.ml.features import FEATURES, prepare_training_frame
from app.ml.model import CandleModel


def mock_candles(n=1200):
    ts = pd.date_range("2026-08-01 09:15", periods=n, freq="5min", tz="Asia/Kolkata")
    rng = np.random.default_rng(12)
    noise = rng.normal(0, 0.08, n)
    close = 100 + np.cumsum(noise + 0.02)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 0.05
    low = np.minimum(open_, close) - 0.05
    vol = rng.integers(1000, 12000, n)
    return pd.DataFrame({"timestamp":ts,"open":open_,"high":high,"low":low,"close":close,"volume":vol,"oi":0})


def test_model_can_fit_and_predict():
    train = prepare_training_frame(mock_candles())
    model = CandleModel(min_train_rows=500)
    report = model.fit(train, FEATURES)
    assert report.direction_accuracy >= 0
    latest = train.iloc[[-1]]
    result = model.predict(latest, float(latest.close.iloc[0]), news_impact=0.0)
    assert result["signal"] in {"BUY", "SELL", "NO-TRADE"}
