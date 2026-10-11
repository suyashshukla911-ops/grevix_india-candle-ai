from app.market.data_store import OfflineMarketStore
from app.market.engine import StockAnalysisEngine
from app.market.features import FEATURES, prepare_training_frame


def test_offline_dataset_has_enough_rows():
    store = OfflineMarketStore()
    df = store.candles('RELIANCE', 5)
    train = prepare_training_frame(df)
    assert len(train) > 500
    assert set(FEATURES).issubset(train.columns)


def test_prediction_runs_with_offline_data():
    store = OfflineMarketStore()
    status = lambda: {'state':'CURRENT'}
    engine = StockAnalysisEngine(store, status)
    result = engine.analyze('TCS', 5)
    assert result['trusted_signal'] in {'BUY','SELL','NO-TRADE'}
    assert result['data_source'] == 'offline seeded market dataset'
