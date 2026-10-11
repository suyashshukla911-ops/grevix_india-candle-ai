# 54-Problem Remediation Matrix

Status terminology:
- **FIXED** - implemented in the final build and covered by code/tests where practical.
- **MITIGATED** - the risk remains provider/deployment dependent, but the final product handles it explicitly.
- **DOCUMENTED** - the limitation cannot be removed from a free hosted tier or third-party provider and is surfaced honestly.
- **LEGACY ARCHIVED** - the issue exists only in preserved legacy code that is not used by the final application.

## Problems 1-8: breaking bugs and security basics

| # | Finding | Final status | Remediation |
|---|---|---|---|
| 1 | Precision/coverage/threshold mix-up | FIXED | Named threshold result + explicit holdout gate; field semantics are distinct. |
| 2 | 1d crashes with zero rows | FIXED | Daily frames skip intraday session-last filtering and use a daily warm-up policy. |
| 3 | Weekend/holiday freshness failure | FIXED | NSE session calendar; market-closed states are distinct from stale data. |
| 4 | Synthetic fallback could look real | FIXED | Synthetic fallback is disabled. Recorded last-session replay is real recorded data and explicitly labelled. |
| 5 | Accepted HIGH finding blocks forever | FIXED | Only newly introduced HIGH findings block a model-bound trust decision. |
| 6 | Pandas datetime rounding warning | FIXED | Dataset fingerprint only rounds numeric market columns. |
| 7 | `.env` not scanned | FIXED | Exact `.env` name is included in text scanning. |
| 8 | `DB_PASSWORD` missed | FIXED | Credential scanner includes DB_PASSWORD and related names. |

## Problems 9-14: 90% claim and validation quality

| # | Finding | Final status | Remediation |
|---|---|---|---|
| 9 | Gate passed random-walk noise | FIXED | Minimum 30 intraday signals, 15 daily signals and Wilson lower-bound gate. |
| 10 | Weak gate looked 90% accurate | FIXED | Reported gate is holdout precision + Wilson lower bound; no overall 90% accuracy claim. |
| 11 | Five-signal minimum | FIXED | Production default is 30 intraday / 15 daily. |
| 12 | Threshold selected and reported on same validation set | FIXED | Fit -> calibration -> untouched holdout. |
| 13 | Confidence was heuristic | FIXED | Confidence is calibrated probability; no arbitrary clamping. |
| 14 | Regression metrics absent | FIXED | MAE and R2 for return/high/low/EOD regression outputs. |

## Problems 15-20: backtest realism and action semantics

| # | Finding | Final status | Remediation |
|---|---|---|---|
| 15 | Entry at signal close | FIXED | Backtest enters at next bar/session open. |
| 16 | No trading costs | FIXED | Configured transaction-cost + slippage assumptions are included. |
| 17 | Buy-and-hold gap error | FIXED | Comparator uses first/last validation closes. |
| 18 | No naive baseline/position sizing | FIXED | Naive direction baseline, 1x notional paper sizing and explicit heuristic stop/target note. |
| 19 | Zero-return counted as down | FIXED | Tiny/flat returns are neutral and excluded from the direction target. |
| 20 | SELL not actionable for retail delivery | FIXED | UI defines SELL / EXIT as an exit-oriented paper action, not opening a short position. |

## Problems 21-27: data and feature reliability

| # | Finding | Final status | Remediation |
|---|---|---|---|
| 21 | Yahoo may block hosted/cloud IPs | MITIGATED | Live -> verified cache -> recorded last-session replay -> explicit unavailable state. |
| 22 | Unadjusted prices | FIXED | Yahoo history requests use auto_adjust=True. |
| 23 | Intraday retention limits | MITIGATED | Training windows respect provider limits; interval availability is explicit. |
| 24 | Nifty/BankNifty/VIX fetched but unused | FIXED | Context returns are merged into model features when available. |
| 25 | Unvalidated news wordlist | IMPROVED | Timestamped, age-decayed context; news does not directly create BUY/SELL and is a bounded trust/context check. |
| 26 | Illiquid SME names | FIXED | Configured minimum median value-traded floor; low-liquidity results become HOLD. |
| 27 | Brittle catalogue scraping | MITIGATED | Bundled catalogue snapshot provides deterministic search; runtime exchange refresh is optional. |

## Problems 28-34: TrustGraph quality and dependency security

| # | Finding | Final status | Remediation |
|---|---|---|---|
| 28 | Monitored repo was a 6-file stub | FIXED | Default model workspace is the real application repository. |
| 29 | Overnight simulation touched only stub | FIXED | Simulation changes real model/config/dependency files. |
| 30 | Scanner false positives | FIXED | AST rules target actual dangerous calls rather than generic model.eval text/comments. |
| 31 | Scanner missed dangerous constructs | FIXED | AST checks cover os.system, pickle.loads, yaml.load, verify=False and SQL f-strings. |
| 32 | Bandit/pip-audit absent | FIXED | Included in dependencies and enabled for deep scans. |
| 33 | Installed versions not tied to model | FIXED | Package versions form part of the prediction-environment fingerprint and model metadata. |
| 34 | Accepted baseline did not change blocking semantics | FIXED | Findings now expose accepted_baseline vs blocking. |

## Problems 35-41: security and abuse controls

| # | Finding | Final status | Remediation |
|---|---|---|---|
| 35 | Mutating POST routes public | FIXED | Admin session authentication protects repository mutations. |
| 36 | Arbitrary source/local path scan | FIXED | Endpoint removed from the public API. |
| 37 | Shared global repository state | FIXED | Browser session IDs isolate repository audit state. |
| 38 | Webhook did not refresh and secret optional | FIXED | HMAC secret required; webhook refreshes the bound GitHub clone. |
| 39 | Clone size/count unbounded | FIXED | Clone size/count caps enforced. |
| 40 | Old clones never deleted | FIXED | Per-session clone cleanup retains only the configured recent count. |
| 41 | Untrusted joblib loading | MITIGATED | Artifacts are only loaded when an HMAC signing key is configured and signature verification succeeds. |

## Problems 42-48: performance, state and packaging

| # | Finding | Final status | Remediation |
|---|---|---|---|
| 42 | Global lock blocked requests | FIXED | Per session/symbol/timeframe locks. |
| 43 | Retrain on every new candle | FIXED | Model refresh cadence plus environment-change invalidation. |
| 44 | Duplicate journal / no settlement | FIXED | Unique journal key and later candle settlement. |
| 45 | Render free disk is ephemeral | DOCUMENTED | Runtime persistence caveat is explicit; production persistence should use persistent storage. |
| 46 | Incomplete packaging | FIXED | Tests, requirements, Dockerfile, render.yaml, .env.example included. |
| 47 | Documentation/test-count drift | FIXED | Single START_HERE and README flow plus explicit test/report documents. |
| 48 | Loose versions / Python mismatch | FIXED | Pinned runtime requirements and Python 3.12.11. |

## Problems 49-50: product presentation and public use

| # | Finding | Final status | Remediation |
|---|---|---|---|
| 49 | Dashboard overwhelmed by terminology | IMPROVED | Market Predictor is the primary workflow; TrustGraph and Repository Health are separate tabs with concise state labels. |
| 50 | BUY/SELL public-use compliance | FIXED | UI/footer clearly states paper analysis, no orders, no guarantees; public investment-research compliance remains a deployment responsibility. |

## Problems 51-54: legacy implementation

| # | Finding | Final status | Remediation |
|---|---|---|---|
| 51 | Fabricated confidence in legacy app | LEGACY ARCHIVED | Legacy code is preserved for reference only and is not used by the final application. |
| 52 | Legacy sentiment distribution-shift bug | LEGACY ARCHIVED | Final news service is timestamped and age-decayed; legacy code is not in the runtime path. |
| 53 | Legacy close-level leakage concern | LEGACY ARCHIVED | Final model predicts returns/ranges from engineered current-state features; legacy implementation is not shipped as runtime logic. |
| 54 | Legacy missing dependencies | FIXED | Final requirements include required runtime packages; legacy code is archived and not imported. |

## Final scope note

The attached audit itself notes that its live Yahoo/PyPI sandbox was blocked and that some findings were read from source rather than exercised over HTTP. The final build therefore distinguishes tested behaviour from provider/deployment limitations and does not claim a result was reproduced when it was not.
