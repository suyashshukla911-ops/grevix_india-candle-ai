# Model Policy

## What the 90% requirement means

The project does not claim 90% overall market-direction accuracy. The 90% requirement is a **selective signal-precision gate**.

A BUY/SELL signal becomes eligible for trust only when all of the following hold on the untouched holdout window:

1. Holdout signal count meets the configured minimum (30 for intraday; 15 for daily).
2. Signal precision is at least 90%.
3. The 95% Wilson lower confidence bound is at least 90%.

The threshold itself is selected on the calibration window, not on the final holdout.

## Validation design

```text
Chronological history
        |
        +--> fit window
        |
        +--> calibration window
        |
        +--> untouched holdout
```

The classifier is calibrated with isotonic regression. The holdout is not used to choose the threshold.

## Decision hierarchy

```text
Repository/data freshness invalid
          -> REVALIDATE

Model quality gate fails
          -> NO-TRADE

Liquidity floor fails
          -> HOLD

Gate passes + qualifying probability
          -> BUY / SELL

Gate passes + probability inside threshold
          -> HOLD
```

## Confidence

Displayed confidence is the calibrated model probability transformed to a percentage. It is not artificially clamped to look like a stronger prediction.

## Backtest assumptions

Signals are entered at the next bar/session open and exited at the next bar/session close. Brokerage/slippage assumptions are included. The buy-and-hold comparator uses the first and last validation closes. A naive previous-return direction baseline is also reported.

Stop-loss and take-profit levels are volatility heuristics for paper analysis and are explicitly not backtest-validated guarantees.

## Real-world limitation

No statistical model can guarantee returns. A high validation precision can fail under regime changes, transaction costs, liquidity constraints and distribution shifts. The TrustGraph freshness layer therefore complements, rather than replaces, model validation.
