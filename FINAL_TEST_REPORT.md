# Final Test Report

## Scope

This report covers the final India Candle AI / TrustGraph remediation build after the supplied 54-problem audit and test-finding documents were reviewed.

## Source audit basis

The supplied audit reported 8 reproduced runtime failures and 54 total findings. The audit also stated that Yahoo/PyPI access was blocked in its sandbox, so live NSE data and FastAPI/pytest were not exercised there. Some findings were therefore source-inspection findings rather than HTTP-run findings.

The final build explicitly separates:

- provider-dependent behaviour
- recorded last-session reproducibility
- model validation
- repository-trust behaviour

It does not claim live provider success when the provider is unavailable.

## Automated regression suite

The project contains **27 pytest tests** covering:

- daily timeframe preparation
- context-feature merging
- weekend/market-closed freshness
- broad Indian-security catalogue search
- recorded-session quotes
- accepted HIGH finding semantics
- Wilson lower bound
- buy-and-hold calculation
- watchlist quote isolation
- interval availability contract
- CURRENT -> STALE -> CURRENT repository lifecycle
- AST security finding detection
- `.git` exclusion
- model simulation restrictions
- BSE catalogue parsing
- Yahoo unavailable-symbol isolation
- prediction environment fingerprinting
- external-repository isolation
- feature numeric integrity
- regime classification
- bootstrap/catalog API contracts
- model training/prediction and explicit gate semantics

A full 27/27 run was completed during the V3 hardening cycle before the final documentation/package cleanup. The final hardening changes are syntax-compiled below; because the current build sandbox contains a Windows virtual environment and has no outbound PyPI access, the final 27-test suite is not re-executed in this Linux sandbox. The Windows run command is provided for the submitter.

## Post-hardening static verification

Passed:

- `python -m py_compile` across `app/` and `tests/`
- `node --check frontend/app.js`
- packaging excludes `.venv`, `.git`, `.pytest_cache` and runtime state from the final release archive

## Required Windows final verification before judging

```powershell
python -m pip install -r requirements-dev.txt
pytest -q
node --check frontend/app.js
```

Expected automated suite size: **27 tests**.

## Manual HTTP smoke flow

```text
GET /api/health                 -> 200
GET /api/bootstrap              -> 200
GET /api/stocks/search          -> 200
GET /api/stocks/catalog         -> 200
GET /api/stocks/availability    -> 200
GET /api/quotes                 -> 200
GET /api/analyze                -> 200 or explicit 503 when provider has no series
GET /api/journal                -> 200
GET /api/audit                  -> 200
```

The application is intentionally designed to return a specific `503` explanation for a symbol/timeframe with no usable data rather than fabricating a price or silently switching timeframes.

## Challenge Card 1 verification

```text
Accept baseline
      |
      v
CURRENT
      |
      v
Real model/config/dependency change
      |
      v
STALE
      |
      v
Impact + security + dependency review
      |
      v
REVALIDATE
      |
      v
Accept new baseline
      |
      v
CURRENT
```

## Security verification

Repository scanning uses AST checks for dangerous Python constructs and optional Bandit/pip-audit deep scans. New HIGH findings block model-bound trust. Findings already accepted in a baseline are recorded as accepted observations instead of forcing permanent revalidation.

## Model correctness safeguards

The final model policy avoids the earlier weak-90%-gate problem by using:

- chronological fit/calibration/holdout separation
- threshold selection on the calibration window
- untouched holdout reporting
- minimum signal count
- Wilson lower confidence bound
- calibrated probabilities
- no synthetic fallback for the competition build
- explicit NO-TRADE when evidence is insufficient

## Data-provider behaviour

The primary provider remains Yahoo Finance. The platform also uses verified caches and a recorded last-session dataset to remain inspectable when the provider is unavailable. Recorded data is explicitly labelled and never promoted to trusted live data when the freshness gate fails.

## Deployment verification

`render.yaml`, `Dockerfile`, `.python-version`, pinned runtime requirements and `healthCheckPath=/api/health` are included.

The public Render deployment uses the same FastAPI backend as the local application.
