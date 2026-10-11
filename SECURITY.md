# Security Notes

## Repository scanning

Repository Health is a defensive audit mechanism. It never executes the monitored repository.

The scanner excludes VCS metadata, virtual environments, runtime caches and archived legacy code.

### Blocking semantics

A HIGH finding is blocking only when it is newly introduced relative to the accepted baseline. An accepted baseline is not a security certification; it simply prevents an already-reviewed observation from permanently forcing revalidation.

## Authentication

Repository mutations require the configured admin password session. The public application keeps prediction reads separate from repository-admin actions.

## GitHub webhook

`/api/webhook/github` requires `GITHUB_WEBHOOK_SECRET` and validates `X-Hub-Signature-256`.

## Clones

Public GitHub repositories are cloned shallowly into isolated per-session directories with size and count limits. Old clones are cleaned up automatically.

## Model artifacts

Signed model artifacts require `MODEL_ARTIFACT_KEY`. Unsigned writable runtime artifacts are not loaded from disk.

## Public deployment

This project is a decision-support/paper-analysis prototype. It does not place trades. Public deployment of investment research/signals may trigger regulatory obligations; deploy only after obtaining the appropriate legal/compliance review.
