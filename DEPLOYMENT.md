# Deployment

## Render

This project is a FastAPI web service. Deploy it as a Render **Web Service**, not as a static-only site.

`render.yaml` is included with the production start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Required Render settings

- Python: 3.12.11 (`.python-version` / `PYTHON_VERSION`)
- `ALLOW_FALLBACK=false`
- `REPLAY_ENABLED=true`
- `AUTH_ENABLED=true`
- Set `ADMIN_PASSWORD` in the Render dashboard.
- Set `GITHUB_WEBHOOK_SECRET` only if GitHub webhook monitoring is enabled.
- Set `MODEL_ARTIFACT_KEY` for signed model-artifact caching.

### Persistence

The free Render filesystem is ephemeral. SQLite audit state, cached models and runtime files can disappear after a restart or redeploy. For a production system, use a persistent disk or managed database and move model artifacts to durable storage. The competition build remains intentionally self-contained and reproducible.

## GitHub Pages

GitHub Pages can host only the static frontend. This application requires the FastAPI backend for market data, model inference and repository scanning, so the complete application should be deployed as a backend web service.
