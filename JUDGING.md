# 5-minute judging script

### 1. Establish original product
Select a stock and timeframe and click **ANALYZE STOCK**.
Say:
> This is the original India Candle AI problem: convert historical candles into a structured short-horizon market decision.

### 2. Explain the adaptation
Say:
> AfterCode introduced the Missing Update Window. The prediction is now trustworthy only while its data, model and source environment are current.

### 3. Show TrustGraph
Point out:
- market data
- model gate
- repository state
- trust score
- overall state

### 4. Demonstrate the challenge
Repository Health → **SCAN & ACCEPT BASELINE**.
Then → **SIMULATE OVERNIGHT UPDATE**.

Expected result:
- repository STALE
- changed files
- dependency change
- required revalidation

### 5. Prove integration
Return to Market Predictor and analyze.
The prediction remains inspectable, but the trusted signal becomes `REVALIDATE`.

### 6. Recover
Accept the new baseline and analyze again.
The repository is CURRENT.

### Important wording
Do not say:
> The model is 90% accurate.

Say:
> Trusted BUY/SELL signals require at least 90% validation precision. When that cannot be supported, the model abstains.

## Basic judge questions

**Why Yahoo?**
> It keeps the project keyless and preserves the original data-source choice. The adapter uses structured Yahoo data rather than HTML scraping.

**Why repository monitoring for a stock predictor?**
> Because the software environment is part of the prediction pipeline. Feature logic, model logic and dependencies can change even when the underlying price is unchanged.

**What happens after an update?**
> The old state becomes STALE and the trusted signal becomes REVALIDATE until a new baseline is accepted.

**Can you prove it is real?**
> Yes. The monitored repository is a real local folder. I can manually modify a file instead of using the overnight simulation and the same fingerprint comparison detects it.

**Why NO-TRADE?**
> It is an explicit abstention state. The product prefers no signal to unsupported confidence.

**Is the demo fake?**
> The market fallback data is explicitly labeled LOCAL DEMO. The fingerprinting, model training, backtest, scanner and trust transitions are real.
