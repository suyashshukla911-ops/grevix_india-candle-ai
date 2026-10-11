# India Candle AI — AfterCode v3

India Candle AI is an AI-assisted stock-analysis application adapted to the AfterCode **Missing Update Window** challenge.

## Product in one sentence

**Predict the next market move, but only treat BUY/SELL as trusted when the repository environment is current and the selected model's validation evidence supports a 90% minimum signal-precision gate.**

## Core product

- Offline Indian-equity universe: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, TATAMOTORS, BHARTIARTL.
- Timeframes: 5m, 15m, 30m and 60m.
- Historical OHLCV candles are stored locally for reproducible judging.
- Walk-forward feature engineering and deterministic gradient-boosting models.
- Predicts next close, high, low and end-of-day close.
- Contextual local research/news layer.
- Validation cards show direction accuracy, signal precision, coverage, threshold and MAE.
- Model cache makes repeat analysis fast; recalibration explicitly rebuilds the selected model.

## 90% precision policy

The product does **not** claim 90% overall market-direction accuracy. Instead, it uses a strict 90% validation precision gate for selective BUY/SELL signals. When the validation evidence cannot meet that requirement, the product abstains with **NO-TRADE**.

The default demo setup is **TCS / 60m**. On the packaged offline dataset its walk-forward benchmark is 79.35% direction accuracy and 91.43% selective signal precision.

## AfterCode adaptation

The Repository Health view monitors `workspace/monitored_repository` and provides:

- SHA-256 fingerprinting of tracked source/config/dependency files.
- Added/modified/removed file detection.
- Dependency-change detection.
- Security/code-quality findings.
- Accepted baseline + audit history.
- `CURRENT → STALE → CURRENT` state transitions.
- A concrete overnight update simulation.

If the repository changes, stock analysis can still be inspected, but the trusted signal becomes **REVALIDATE** until the repository is rescanned and accepted.

## Why the application feels faster

- Model fitting uses lightweight `HistGradientBoosting*` estimators.
- Models are cached per stock/timeframe.
- FastAPI runs analysis in a worker thread instead of blocking the request loop.
- The frontend no longer makes redundant status calls after every analysis.
- Repository status/history are fetched in parallel.
- The chart is rendered locally with Canvas and no external CDN dependency.

## Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app
```

Open `http://127.0.0.1:8000`.

## Tests

```powershell
pytest -q
```

## Submission position

The competition version intentionally has no live market API keys and no GitHub token. The local provider boundaries are deliberate so the evaluator can run the full product immediately. Live market/GitHub adapters can be added later without changing the core trust/state logic.
