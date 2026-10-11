# Model Policy and Validation Baselines

## The 90% requirement

The competition build uses **90% minimum validation precision** as a gate for trusted BUY/SELL signals.

This is **not** a claim that the overall stock-direction model predicts the future with 90% accuracy. Short-horizon market direction is noisy, and the honest product behaviour is to abstain when the validation evidence does not support the required precision.

The model reports both:

- **Direction accuracy** — accuracy across the complete walk-forward validation window.
- **Signal precision** — precision of the selectively-issued BUY/SELL signals.

The model chooses a probability threshold on the validation window. It maximises usable signal coverage while retaining the 90% precision requirement when possible.

If no threshold can satisfy the 90% requirement with a minimum number of validation signals, the model sets `gate_met = false` and the product returns **NO-TRADE** rather than fabricating a 90% result.

## Interval baselines

| Timeframe | Minimum clean training rows | Decision policy |
|---|---:|---|
| 5m | 500 | 90% signal-precision gate |
| 15m | 400 | 90% signal-precision gate |
| 30m | 300 | 90% signal-precision gate |
| 60m | 250 | 90% signal-precision gate |

The 60m threshold is intentionally lower because resampling produces fewer observations. This prevents a valid 60m dataset from being rejected just because it has fewer rows than the 5m dataset.

## Default demonstration baseline

The packaged default selection is **TCS / 60m**. On the included offline dataset, the deterministic walk-forward validation produced:

- Direction accuracy: **79.35%**
- Signal precision: **91.43%**
- Signal coverage: **69.57%**
- Threshold: **0.82**
- Validation rows: **92**
- Qualified validation signals: **64**

These values are a benchmark for the packaged offline dataset, not a promise about live market performance.

## Speed policy

Models are cached per `(stock, timeframe)` in process memory. The first analysis for a combination trains the model; repeated analysis reuses it. Recalibration explicitly rebuilds that model.

API analysis runs in a worker thread so model fitting does not block other FastAPI requests or trigger browser-level `Failed to fetch` errors caused by an unresponsive event loop.
