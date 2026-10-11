# Decisions

## Offline by default
The competition proof of concept deliberately avoids external APIs. This makes the challenge behavior deterministic and demonstrable in a clean laptop environment.

## Content fingerprint, not timestamps
Filesystem timestamps can be noisy or unavailable across copies. The accepted scan is keyed to a SHA-256 manifest built from file paths, file sizes, and file hashes.

## Explicit rescan
A changed repository produces a stale state. A new scan is an explicit user action, creating a new accepted baseline and audit event.

## Explainable checks
The demo uses deterministic local rules for secrets and common code-quality anti-patterns. A later production connector can add GitHub/webhook/SAST/CVE providers without changing the stale-state mechanism.
