# India Candle AI — AfterCode Adaptation

India Candle AI remains a stock-analysis product, but the AfterCode "Missing Update Window" requirement is now part of the product instead of a separate demo.

## What the product does

### 1. Market Predictor
- Works offline with a seeded Indian-equity intraday dataset.
- Trains a walk-forward machine-learning model on candle features.
- Estimates next close, next high, next low and end-of-day close.
- Produces BUY / SELL / NO-TRADE from the measured validation threshold.
- Adds a small contextual news-impact layer from local research data.
- Shows validation metrics instead of claiming certainty.

### 2. Repository Health / Missing Update Window
- Monitors a real local source workspace.
- Builds a content fingerprint across tracked source/config/dependency files.
- Stores an accepted scan baseline and audit history.
- Detects added, modified and removed files.
- Detects dependency-file changes.
- Scans for credential-like strings, eval/exec, shell=True, broad exception handling, debug prints and TODO/FIXME markers.
- Marks the accepted findings **STALE** when the live repository fingerprint changes.
- Keeps the old findings visible, but never represents them as current.
- A new scan explicitly accepts the new fingerprint and restores a CURRENT state.

### 3. Why this satisfies the challenge without throwing away the original product

The core problem stays: use software to produce useful stock-analysis decisions.
The challenge adds a new invariant: **a decision is trustworthy only when the source environment that produced it is still the accepted version.**

Therefore the repository sentinel is not a fake extra page. It is the freshness gate for the stock-analysis environment. When source code or dependency configuration changes, the previously trusted stock signal becomes REVALIDATE until the repository is rescanned.

The submission build intentionally uses a local provider and local data so it has zero API keys and zero external runtime dependencies. A future GitHub/market-data adapter can plug into the same interfaces.

## Run

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app
```

Open http://127.0.0.1:8000

## Challenge proof flow

1. Open **Repository Health**.
2. Click **SCAN & ACCEPT BASELINE**.
3. Click **Market Predictor** and analyze a stock.
4. Return to **Repository Health** and click **SIMULATE OVERNIGHT UPDATE**.
5. The repository becomes STALE and the changed files appear.
6. Analyze the stock again: the market calculation is shown for inspection, but the trusted signal becomes **REVALIDATE**.
7. Click **SCAN & ACCEPT BASELINE**.
8. The environment becomes CURRENT and a fresh stock analysis can be trusted again.

## Future API integration

The application has a provider boundary. In a production version, a GitHub provider can replace the local repository provider, and a live market-data provider can replace the seeded market store without changing the core UI state machine.
