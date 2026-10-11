# Challenge mapping

| Challenge requirement | Implementation |
|---|---|
| Repository continuously changes | Live fingerprint is recomputed from the monitored workspace. |
| Previous results become obsolete | CURRENT/STALE state machine; stale results remain labeled stale. |
| Detect updates | Added/modified/removed files + dependency changes. |
| Security and code quality | Local scanner rules for secrets, eval/exec, shell=True, broad except, debug prints, TODO/FIXME. |
| Clean dashboard | Two focused workspaces: Market Predictor and Repository Health. |
| Standard operations remain | Analyze, retrain, repository scan, update check all remain one-click. |
| Concrete update simulation | Simulate Overnight Update modifies source + dependency data. |
| Updated results | Fresh scan accepts new fingerprint and creates history. |
| No API keys for submission | Local market and repository providers. |
