import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import settings
from app.data.catalog import IndianSecurityCatalog
from app.data.trading_calendar import freshness_state, session_state
from app.data.yahoo import YahooProvider
from app.ml.features import FEATURES, prepare_training_frame
from app.ml.model import CandleModel, wilson_lower
from app.services.db import init_db, journal_signal, recent
from app.services.repository import RepositoryMonitor


def daily_frame(n=90):
    ts = pd.date_range("2026-06-01 09:15", periods=n, freq="B", tz="Asia/Kolkata")
    rng = np.random.default_rng(12)
    close = 100 * np.cumprod(1 + rng.normal(0.001, 0.015, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.005
    low = np.minimum(open_, close) * 0.995
    volume = rng.integers(100000, 300000, n)
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low, "close": close, "volume": volume})


def test_daily_training_frame_does_not_drop_every_row():
    out = prepare_training_frame(daily_frame())
    assert len(out) >= 50
    assert set(FEATURES).issubset(out.columns)


def test_context_features_merge_without_duplicate_column_error():
    frame = daily_frame()
    base = frame[["timestamp", "close"]].copy()
    context = {"nifty": base, "banknifty": base, "vix": base}
    out = prepare_training_frame(frame, context=context)
    assert all(x in out.columns for x in ("nifty_return", "banknifty_return", "vix_return"))


def test_weekend_is_market_closed_not_stale():
    now = pd.Timestamp("2026-10-11 11:00", tz="Asia/Kolkata").to_pydatetime()
    latest = pd.Timestamp("2026-10-09 15:15", tz="Asia/Kolkata").to_pydatetime()
    status, ok = freshness_state(latest, 5, now=now)
    assert status == "MARKET_CLOSED"
    assert ok is True
    assert session_state(now) == "MARKET_CLOSED"


def test_catalog_snapshot_is_broad_and_searchable(tmp_path):
    c = IndianSecurityCatalog(tmp_path / "catalog.json")
    rows = c.load()
    assert len(rows) >= 3000
    assert c.search("lohia", 5)
    assert c.search("regency", 5)


def test_replay_quote_is_fast_path_for_closed_market():
    p = YahooProvider(cache_dir=Path('/tmp/ica-hardening-cache'))
    q = p.snapshot_quote("TCS")
    assert q["data_status"] in {"REPLAY", "CACHED", "LIVE"}
    assert q["price"] is None or q["price"] > 0


def test_accepted_high_finding_is_not_blocking(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    bad = repo / "bad.py"
    bad.write_text("x = eval('1+1')", encoding="utf-8")
    r = RepositoryMonitor(repo)
    r.state_path = tmp_path / "state.json"
    first = r.scan(True)
    assert first["state"] == "CURRENT"
    accepted = r.scan(False)
    assert accepted["security_blocking"] is False
    assert any(f["accepted_baseline"] for f in accepted["findings"])
    bad.write_text("import os\nos.system('echo hi')", encoding="utf-8")
    changed = r.scan(False)
    assert changed["security_blocking"] is True
    assert changed["new_high_findings"]


def test_wilson_lower_bound_is_conservative():
    assert wilson_lower(30, 30) < 0.95
    assert wilson_lower(100, 100) > 0.96


def test_backtest_buy_hold_uses_price_window_not_compounded_next_return():
    from app.ml.model import CandleModel
    m = CandleModel(min_train_rows=30)
    m.report = type("R", (), {"threshold": 0.7})()
    m.validation_predictions = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=3, tz="Asia/Kolkata"),
        "open": [100, 100, 100], "close": [100, 110, 121],
        "actual_return": [0.10, 0.10, 0.0], "execution_return": [0.10, 0.10, 0.0],
        "return_1": [0.0, 0.10, 0.10], "p_up": [0.8, 0.8, 0.5],
    })
    out = m.backtest()
    assert out["buy_hold_return_pct"] == 21.0
