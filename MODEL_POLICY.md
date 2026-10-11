# India Candle AI — Model Policy

## 1. What the model predicts
The core engine learns from OHLCV history and technical/session features and produces:
- next-candle return/close scenario
- next-candle high/low scenario
- same-session EOD scenario
- probability of upward movement
- BUY / SELL / NO-TRADE / REVALIDATE

## 2. Validation
Validation is chronological; rows are not shuffled. A validation window is held out from the end of the historical sample.

## 3. 90% gate
The application does **not** claim that overall direction accuracy is 90%.

Instead, trusted BUY/SELL signals require selective validation precision >= `SIGNAL_PRECISION_GATE` (default 90%).

The threshold is automatically optimized across a grid. The objective is:

> maximize signal coverage subject to validation precision >= 90%.

When no threshold satisfies the gate, the application records a gate failure and abstains with NO-TRADE rather than inventing confidence.

## 4. Trust decision
A signal is trusted only when:
1. repository is CURRENT;
2. market data is CURRENT (or explicitly LOCAL DEMO);
3. model gate passes;
4. no high-severity unresolved repository/security state blocks the result.

When repository/data freshness fails, the signal becomes REVALIDATE.

## 5. Model version
Every training run creates a deterministic model version from:
- feature list
- threshold
- classifier choice
- dataset fingerprint
- gate setting

This allows an audit record to connect a result to the environment that produced it.

## 6. Limitations
Financial markets are stochastic. No metric shown by the application guarantees future profit or future accuracy.
