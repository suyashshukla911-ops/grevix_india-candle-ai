# Architecture and prediction logic

## Target hierarchy

The system is optimized in this order:

1. **Correct market data**
2. **Correct session/candle construction**
3. **No-lookahead feature engineering**
4. **Walk-forward validation**
5. **Selective BUY/SELL gating**
6. **News/event overlay**
7. **EOD repricing**

This matters because a sophisticated ML model trained on incomplete or delayed market data will still fail.

## Candle targets

For each observed candle `t`:

- `next_return = Close[t+1] / Close[t] - 1`
- `next_high_return = High[t+1] / Close[t] - 1`
- `next_low_return = Low[t+1] / Close[t] - 1`
- `direction = 1(next_return > 0)`
- `eod_return = SessionClose / Close[t] - 1`

The last candle of each historical session is excluded from training.

## Session awareness

Features include:

- overnight gap from previous session close to today's first open
- position inside the NSE cash-session clock
- session VWAP distance
- current session high/low distance
- time-of-day cyclical encoding
- NIFTY, BANKNIFTY and INDIA VIX context

Therefore the next day's opening price is allowed to gap instead of assuming it equals the previous close.

## Accuracy philosophy

A guaranteed 100% future prediction is not a technically valid requirement for a stochastic market. The code therefore focuses on **selective precision**:

- raw direction accuracy is measured on chronological holdout data
- the BUY/SELL threshold is selected on holdout data
- low-confidence cases become `NO-TRADE`
- current news can suppress a contradictory signal
- the UI reports actual validation metrics

This is designed to pursue higher precision without hiding low-confidence cases.

## News impact

Current news is not injected into historical training unless time-aligned historical news is available. This prevents look-ahead leakage.

The live news layer scores:

- financial sentiment
- event type
- source quality
- recency

It produces a capped `impact` score in `[-1, 1]` that is used as an overlay/gate rather than pretending the headline can determine an exact future price.

## Scaling to all Indian stocks

The instrument registry comes from the Upstox NSE/BSE instrument master and can therefore represent the live equity universe.

The dashboard uses a two-level architecture:

- **all-universe:** instrument search and full-market quote pulse
- **deep analysis:** expensive candle model training only for a selected/watchlisted stock

This avoids thousands of needless historical/model-training calls every refresh.

## Next phase for a higher-grade research system

To move beyond this baseline, add an event-labelled historical news dataset and train a separate news-impact model using publication timestamps. Then evaluate:

- abnormal return after 1, 5, 15, 30, 60 minutes
- volatility expansion after news
- sector spillover
- gap/open response
- precision by event type and source

That is the route to a genuinely data-driven news impact model rather than a sentiment heuristic.
