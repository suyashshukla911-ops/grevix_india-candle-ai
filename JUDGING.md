# Judge Flow

## 1. Show the original product

Search `TCS`, select `5m`, and run **ANALYZE STOCK**.

Point out:

- current price
- next close/high/low estimates
- model gate
- risk
- market regime
- explainability
- validation/backtest

## 2. Show the 90% rule

Explain that the system does not claim 90% overall accuracy. The 90% requirement is a selective signal-precision gate with a minimum signal count and Wilson lower confidence bound.

## 3. Show TrustGraph

Open TrustGraph. Explain:

```text
Market evidence + model evidence + environment evidence
```

## 4. Show the generic repository monitor

Clone any public repository. Accept its baseline. Explain that this repository can be a Python/API/LMS/cybersecurity repository, not only a stock project.

## 5. Demonstrate the Missing Update Window

```text
Accept baseline
   -> CURRENT
   -> simulate overnight update
   -> changed files + dependency change
   -> STALE
   -> prediction trust becomes REVALIDATE
   -> accept new baseline
   -> CURRENT
```

## 6. Explain the real-world value

The application does not pretend an old model result remains trustworthy after its source environment or market-data state changes. It makes that uncertainty explicit and auditable.
