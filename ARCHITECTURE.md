# Architecture — TrustGraph

```text
                        INDIA CANDLE AI
                              |
                 +------------+-------------+
                 |                          |
           MARKET ENGINE              REPOSITORY ENGINE
                 |                          |
      Yahoo -> cache -> fallback     fingerprints
                 |                   component hashes
      feature engineering            change impact
                 |                   security scanner
      regime detection                     |
                 |                          |
      model selection                      |
      threshold optimizer                  |
      confidence engine                    |
                 |                          |
                 +------------+-------------+
                              |
                         TRUST ENGINE
                              |
                 +------------+-------------+
                 |            |              |
              TRUSTED      NO-TRADE      REVALIDATE
```

## Runtime flow
1. Browser calls one FastAPI client with timeout/retry semantics.
2. Market provider resolves arbitrary Yahoo tickers as `.NS` then `.BO`.
3. Yahoo data is cached on disk; if Yahoo is unavailable, a prior cache is used; otherwise a deterministic local demo series is generated.
4. Feature engineering builds temporal, technical and regime features.
5. The model selects a direction classifier and trains four lightweight regressors.
6. Threshold optimization seeks >=90% selective-signal precision while maximizing coverage.
7. Repository state is checked.
8. Data freshness and model gate are checked.
9. TrustGraph returns the final signal state.
10. Every signal and important repository event is stored in SQLite.
