from __future__ import annotations

from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings, PRIORITY_STOCKS, DEFAULT_SYMBOL, DEFAULT_INTERVAL
from app.market.data_store import OfflineMarketStore
from app.market.engine import StockAnalysisEngine
from app.sentinel.service import RepositoryService

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
REPO_ROOT = BASE_DIR / settings.monitored_repo
SEED_ROOT = BASE_DIR / "workspace" / "monitored_repository_seed"
STATE_FILE = BASE_DIR / "data" / "sentinel_state.json"

app = FastAPI(title=settings.app_name, version="3.0.0")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

repository = RepositoryService(REPO_ROOT, STATE_FILE, SEED_ROOT)
market_store = OfflineMarketStore()
engine = StockAnalysisEngine(market_store, repository.status)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "app": settings.app_name,
        "version": "3.0.0",
        "mode": "offline-local",
        "market_data": "seeded-local-dataset",
        "repository_monitor": True,
        "monitored_repository": str(REPO_ROOT.relative_to(BASE_DIR)),
        "default_symbol": DEFAULT_SYMBOL,
        "default_interval": DEFAULT_INTERVAL,
        "precision_gate": settings.min_precision_gate,
        "note": "90% is the minimum validation precision for issuing a trusted BUY/SELL signal; overall direction accuracy is reported separately.",
    }


@app.get("/api/stocks")
def stocks():
    return {"results": market_store.symbols(), "default_symbol": DEFAULT_SYMBOL, "default_interval": DEFAULT_INTERVAL}


@app.get("/api/analyze")
async def analyze(symbol: str = Query(..., min_length=1), interval: int = Query(5), retrain: bool = False):
    started = perf_counter()
    try:
        result = await run_in_threadpool(engine.analyze, symbol, interval, retrain)
        result["latency_ms"] = round((perf_counter() - started) * 1000, 1)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Analysis failed: {exc}")


@app.get("/api/market/overview")
def market_overview():
    rows = []
    for stock in PRIORITY_STOCKS:
        df = market_store.candles(stock["symbol"], 5)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        change = float(last["close"] / prev["close"] - 1) if prev["close"] else 0.0
        rows.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "price": round(float(last["close"]), 2),
            "change_pct": round(change * 100, 2),
        })
    rows.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return {"results": rows}


@app.get("/api/repository/status")
def repository_status():
    return repository.status()


@app.get("/api/repository/history")
def repository_history():
    return {"history": repository.history()}


@app.post("/api/repository/scan")
def repository_scan():
    result = repository.scan()
    engine.invalidate()
    return repository.status() | {"accepted_scan": result}


@app.post("/api/repository/simulate-overnight-update")
def simulate_update():
    repository.simulate_overnight_update()
    return repository.status()


@app.post("/api/repository/reset")
def repository_reset():
    repository.reset_repository()
    engine.invalidate()
    return repository.status()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
