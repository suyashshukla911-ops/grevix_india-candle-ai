# Repository Sentinel architecture

```text
Browser
  |
  +--> FastAPI API
          |
          +--> Local Repository Provider (demo_repos/)
          |
          +--> Scanner
          |      +-- file manifest + SHA-256 fingerprint
          |      +-- security rules
          |      +-- quality rules
          |      +-- dependency-file tracking
          |
          +--> State Store
                 +-- last accepted scan
                 +-- current live scan
                 +-- audit history
                 +-- stale comparison
```

## Core invariant

`accepted_scan.fingerprint == live_scan.fingerprint` means the accepted result is current.

Any mismatch means `STALE`. The system never silently overwrites the accepted result just because the repository changed.
