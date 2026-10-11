# AfterCode Challenge Mapping

## Challenge Card 1 - The Missing Update Window

### Required idea
GitHub repositories change after a scan. Old results can become obsolete.

### Product response
India Candle AI stores a cryptographic baseline and compares later manifests against it.

### Demonstration
```text
CURRENT
  -> repository/dependency change
STALE
  -> review + fresh scan
REVALIDATE
  -> accept new baseline
CURRENT
```

### Evidence
- Added / modified / removed file detection.
- Dependency-file detection.
- Component-level fingerprints.
- Change-impact analysis.
- Accepted-baseline history.
- Model-bound repository state affects prediction trust.
- Overnight simulation edits the real model workspace rather than a 6-file demo stub.

## Generic repository scope

The repository monitor is intentionally not stock-specific. Public GitHub repositories can be cloned, fingerprinted, checked, refreshed and audited. External repositories are audit-only until explicitly bound to model trust.

## Challenge Card 2 - Real-World Feedback

The `/feedback/` folder contains the collected user-feedback evidence and the feedback record. The intended product loop is:

```text
Real users
 -> feedback
 -> usability problem
 -> product change
 -> before/after proof
```

## Why the integration is differentiated

The challenge feature is not a separate repository dashboard. Repository freshness is one of the trust inputs for the original market-analysis workflow.

The product therefore answers two questions:

1. What does the model predict?
2. Can the environment and data that produced the result still be trusted?
