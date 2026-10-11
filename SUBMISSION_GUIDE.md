# Competition submission guide

## 90-second live demonstration

1. Start the app with `python -m uvicorn app.main:app` and open `http://127.0.0.1:8000`.
2. Click **RUN CURRENT SCAN**. Explain that this creates the accepted baseline fingerprint.
3. Click **SIMULATE OVERNIGHT UPDATE**. The live repository changes immediately without accepting a new scan.
4. Point to **RESULTS STALE** and the **What changed?** panel. The dashboard shows the modified application file, a new file, and a dependency-file change.
5. Point to **Live findings**. The simulated update introduces a fake GitHub-style token, `eval`, and a debug print, and those are visible only after the live content changes.
6. Click **RUN CURRENT SCAN** again. The stale state clears because the new content has now been explicitly reviewed.
7. Show **Accepted scan history** to demonstrate that the previous baseline remains auditable rather than being overwritten.

## Challenge-card mapping

| Challenge requirement | Proof of concept implementation |
|---|---|
| Repository can change after a scan | Local overnight simulation modifies files and dependencies |
| Detect updates | SHA-256 manifest + repository fingerprint |
| Prevent obsolete results | Previous accepted scan becomes `STALE` on fingerprint mismatch |
| Keep dashboard clean | One status card + compact change summary + current findings |
| Standard checks still work | Manual scan button remains the normal primary action |
| Concrete overnight proof | One-click simulation demonstrates the state transition |
| No external API dependency | All demo data and checks are local/deterministic |

## Submission positioning

Describe the product as an **update-aware security/code-quality monitor** rather than a full SAST/CVE platform. The differentiator for this challenge is the state model: **live repository state vs. accepted scan state** and the resulting automatic stale-result invalidation.


## Windows / Uvicorn note

Run the competition demo without project-wide `--reload` because the demo intentionally modifies files. For development auto-reload, use:

`python -m uvicorn app.main:app --reload --reload-dir app --reload-dir frontend`
