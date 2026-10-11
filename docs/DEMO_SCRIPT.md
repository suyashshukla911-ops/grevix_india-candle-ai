# 5-Minute Judge Demo

### 1. Market Predictor

Start on **Market Predictor** with the default **TCS / 60m** selection.

Say:

> "This is the original India Candle AI product. It predicts the next market move from historical candle features, but it uses a strict 90% validation precision gate for issuing a trusted BUY or SELL signal."

Click **ANALYZE STOCK**.

Point out:

- Next close / high / low / EOD
- BUY / SELL / NO-TRADE
- Walk-forward validation
- 90% precision gate
- Fast repeat analysis after model caching

### 2. Introduce Missing Update Window

Open **Repository Health**.

Click **SCAN & ACCEPT BASELINE**.

Say:

> "This stores the source environment that the product currently trusts."

### 3. Simulate overnight change

Click **SIMULATE OVERNIGHT UPDATE**.

Say:

> "This represents source code and a dependency changing after yesterday's analysis."

Show:

- STALE
- modified files
- dependency changed = YES
- accepted vs live fingerprints

### 4. Connect freshness to prediction

Return to **Market Predictor** and analyze the same stock.

Point to:

**REVALIDATE**

Say:

> "The model calculation is still visible for inspection, but the trusted signal has been invalidated because the environment changed."

### 5. Recover

Return to **Repository Health**.

Click **SCAN & ACCEPT BASELINE**.

Say:

> "The new source state is explicitly accepted as the trusted baseline."

Analyze the stock again.

Finish with:

> "So the product does not only ask what the model predicts. It also asks whether the environment that produced the prediction is still current and whether the validation evidence supports a trusted signal."
