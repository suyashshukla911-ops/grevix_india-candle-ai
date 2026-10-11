# Architecture

Browser UI → FastAPI → Market Engine + Repository Sentinel

## Market path
LocalMarketStore → feature engineering → ExtraTrees model → prediction + local news overlay → freshness gate

## Freshness path
LocalRepositoryProvider → fingerprint + manifest → security/code-quality scan → accepted baseline → live comparison → CURRENT/STALE

## Key state rule
`live_fingerprint != accepted_fingerprint` means the prior scan is stale.
The old findings are retained for audit but are never presented as current.

## Extension boundary
A future `GitHubRepositoryProvider` can expose the same `root/list/read` semantics used by the local workspace. No dashboard redesign is required.
