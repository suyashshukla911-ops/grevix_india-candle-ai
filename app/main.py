
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import PRIORITY_STOCKS, settings
from app.data.news import NewsService
from app.data.upstox import UpstoxClient, UpstoxError
from app.services.engine import AnalysisEngine


BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title=settings.app_name, version="1.0.0")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

upstox = UpstoxClient(settings.upstox_access_token, cache_dir=str(BASE_DIR / "data_cache"))
news = NewsService(settings.news_max_records)
engine = AnalysisEngine(upstox, news)

oauth_states: set[str] = set()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "upstox_connected": bool(upstox.access_token),
        "news_provider": settings.news_provider,
        "default_interval": settings.default_interval,
    }


@app.get("/api/priority")
def priority():
    return {"stocks": PRIORITY_STOCKS}


@app.get("/api/stocks")
def stocks(q: str = Query("", max_length=80), limit: int = Query(25, ge=1, le=50)):
    if not q.strip():
        # Return the user's priority universe first without hardcoding instrument keys.
        out = []
        for item in PRIORITY_STOCKS:
            try:
                ins = upstox.resolve_symbol(item["symbol"])
            except Exception:
                continue
            out.append({
                "name": ins.name,
                "symbol": ins.trading_symbol,
                "exchange": ins.exchange,
                "instrument_key": ins.instrument_key,
            })
        return {"results": out}

    try:
        matches = upstox.search_instruments(q, limit=limit)
    except UpstoxError as exc:
        raise HTTPException(503, str(exc))
    return {
        "results": [
            {
                "name": x.name,
                "short_name": x.short_name,
                "symbol": x.trading_symbol,
                "exchange": x.exchange,
                "segment": x.segment,
                "instrument_key": x.instrument_key,
            }
            for x in matches
        ]
    }




@app.get("/api/universe")
def universe():
    try:
        items = upstox.load_instruments()
        nse = sum(x.exchange == "NSE" for x in items)
        bse = sum(x.exchange == "BSE" for x in items)
        return {"total_equities": len(items), "nse": nse, "bse": bse}
    except Exception as exc:
        raise HTTPException(503, str(exc))


@app.get("/api/market-pulse")
def market_pulse(limit: int = Query(50, ge=10, le=200)):
    try:
        items = upstox.load_instruments()
        keys = [x.instrument_key for x in items]
        quotes = upstox.get_quote_batch(keys)
    except UpstoxError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))

    rows = []
    by_key = {x.instrument_key: x for x in items}
    for key, q in quotes.items():
        ins = by_key.get(key)
        if not ins:
            continue
        ohlc = q.get("ohlc") or {}
        last = q.get("last_price")
        if last is None:
            last = ohlc.get("close")
        prev = q.get("prev_close_price")
        net = q.get("net_change")
        if net is None and last is not None and prev:
            net = last - prev
        change_pct = (net / prev * 100) if (net is not None and prev) else None
        rows.append({
            "symbol": ins.trading_symbol,
            "name": ins.name,
            "exchange": ins.exchange,
            "instrument_key": ins.instrument_key,
            "price": last,
            "change": net,
            "change_pct": change_pct,
            "volume": q.get("volume") or ohlc.get("volume"),
            "year_high": q.get("year_high"),
            "year_low": q.get("year_low"),
        })
    rows = [r for r in rows if r["price"] is not None and r["change_pct"] is not None]
    rows.sort(key=lambda r: abs(r["change_pct"]), reverse=True)
    return {"count": len(rows), "results": rows[:limit]}


@app.get("/api/analyze")
def analyze(
    symbol: str = Query(..., min_length=1, max_length=100),
    interval: int = Query(settings.default_interval, ge=1, le=300),
    retrain: bool = False,
):
    try:
        instrument = upstox.resolve_symbol(symbol)
        return engine.analyze(instrument, interval=interval, force_retrain=retrain)
    except UpstoxError as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Analysis failed: {exc}")


@app.get("/auth/upstox/start")
def upstox_start():
    if not settings.upstox_client_id or not settings.upstox_redirect_uri:
        raise HTTPException(503, "Set UPSTOX_CLIENT_ID and UPSTOX_REDIRECT_URI in .env first.")
    state = secrets.token_urlsafe(24)
    oauth_states.add(state)
    url = upstox.authorization_url(settings.upstox_client_id, settings.upstox_redirect_uri, state)
    return RedirectResponse(url)


@app.get("/auth/upstox/callback")
def upstox_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error:
        return RedirectResponse(f"/?auth_error={quote(error)}")
    if not code or state not in oauth_states:
        raise HTTPException(400, "Invalid OAuth callback.")
    oauth_states.discard(state)
    try:
        token = upstox.exchange_code(
            code=code,
            client_id=settings.upstox_client_id,
            client_secret=settings.upstox_client_secret,
            redirect_uri=settings.upstox_redirect_uri,
        )
    except Exception as exc:
        return RedirectResponse(f"/?auth_error={quote(str(exc))}")
    # Token is held in server memory for this process. For production, use a secrets store/database.
    return RedirectResponse("/?connected=1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
