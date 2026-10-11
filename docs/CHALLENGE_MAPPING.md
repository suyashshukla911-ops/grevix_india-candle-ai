# AfterCode Challenge Mapping — Missing Update Window

| Challenge requirement | Final implementation |
|---|---|
| Repositories change after a scan | Live SHA-256 fingerprint is recomputed from tracked source/config/dependency files. |
| Old security/code-quality results become obsolete | The accepted baseline enters **STALE** as soon as the live fingerprint differs. Old findings remain visible but are never labelled current. |
| Detect repository updates | Added, modified and removed files are listed. Dependency files are tracked separately. |
| Security + code-quality checks | Scanner covers credential-like strings, private keys, `eval`, `exec`, `shell=True`, broad `except`, debug prints and TODO/FIXME markers. |
| Clean dashboard | Two focused views: Market Predictor and Repository Health. |
| Existing operations remain usable | Stock analysis, recalibration, pulse refresh, repository scan, update check, reset and overnight simulation remain one-click. |
| Concrete update simulation | `SIMULATE OVERNIGHT UPDATE` modifies a real monitored source file and a real dependency file. |
| Up-to-date result handling | After a repository change, stock analysis remains inspectable but the trusted signal becomes **REVALIDATE** until a new baseline is accepted. |
| Fresh baseline after update | `SCAN & ACCEPT BASELINE` stores a new fingerprint, findings and audit record and clears the model cache. |
| Offline/no API requirement | Local market CSVs and a local monitored repository are used for the competition build. |

## What changed from the original product

The original product predicts the next market move. The adaptation does not replace that product; it adds a freshness gate around it. A market signal is only treated as **trusted** when both conditions hold:

1. The repository is **CURRENT** against the accepted fingerprint.
2. The selected stock/timeframe model has a validated **90% minimum signal-precision gate**.

The product therefore has three meaningful trust outcomes:

- **BUY / SELL** — repository current and the selected signal passes the 90% validation precision gate.
- **NO-TRADE** — repository current, but the validation window cannot support a 90% precision signal for that stock/timeframe.
- **REVALIDATE** — repository changed after the accepted scan, so the previous environment is stale.

This is intentionally stricter than displaying a model probability and calling it 90% accuracy.
