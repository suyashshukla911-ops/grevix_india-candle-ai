from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.config import COMMON_INDIAN_STOCKS, settings
from app.data.news import NewsService
from app.data.yahoo import YahooDataError, YahooProvider
from app.services.db import init_db, recent
from app.services.engine import AnalysisEngine
from app.services.repository import RepositoryMonitor

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
market = YahooProvider()
news = NewsService()
model_repo = RepositoryMonitor("model")
engine = AnalysisEngine(market, news, model_repo)
_repo_cache: dict[str, RepositoryMonitor] = {}

def _session_id(request: Request) -> str:
    sid=request.cookies.get("ica_session")
    if not sid:
        sid=secrets.token_urlsafe(24)
    return sid

def repo_for(request: Request) -> RepositoryMonitor:
    sid=_session_id(request)
    hit=_repo_cache.get(sid)
    if hit: return hit
    monitor=RepositoryMonitor(sid)
    _repo_cache[sid]=monitor
    return monitor

def _auth_file(request: Request) -> Path:
    return repo_for(request).session_dir / "auth.json"

def is_authenticated(request: Request) -> bool:
    if not settings.auth_enabled:
        return True
    p=_auth_file(request)
    try:
        d=json.loads(p.read_text(encoding="utf-8"))
        return bool(d.get("ok")) and float(d.get("expires",0)) > time.time()
    except Exception:
        return False

def require_admin(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Admin sign-in required for repository mutation.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app=FastAPI(title=settings.app_name,version="10.1.0",lifespan=lifespan)
app.mount("/static",StaticFiles(directory=FRONTEND_DIR),name="static")

@app.middleware("http")
async def session_middleware(request: Request, call_next):
    response=await call_next(request)
    if "ica_session" not in request.cookies:
        sid=_session_id(request)
        response.set_cookie("ica_session",sid,httponly=True,samesite="lax",max_age=60*60*24*30,secure=request.url.scheme=="https")
    return response

@app.get("/",include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR/"index.html")

@app.head("/", include_in_schema=False)
def index_head():
    return Response(status_code=200)

@app.get("/api/auth/status")
def auth_status(request: Request):
    return {"enabled":settings.auth_enabled,"authenticated":is_authenticated(request)}

@app.post("/api/auth/login")
async def auth_login(request: Request):
    body=await request.json()
    password=str(body.get("password",""))
    if not hmac.compare_digest(password,settings.admin_password):
        raise HTTPException(401,"Invalid admin password.")
    p=_auth_file(request); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"ok":True,"expires":time.time()+8*3600}),encoding="utf-8")
    return {"ok":True,"expires_in_hours":8}

@app.get("/api/bootstrap")
def bootstrap(request: Request):
    rm=repo_for(request)
    return {
        "app":settings.app_name,"mode":"LIVE MARKET DATA + CACHED/RECORDED LAST SESSION",
        "default_interval":settings.default_interval,"gate":settings.signal_precision_gate,
        "min_signal_count":settings.min_signal_count,"min_wilson_lower":settings.min_wilson_lower,
        "repository":rm.scan(False,record_audit=False),"catalog":market.catalog_status(False),"universe":[],
        "auth":is_authenticated(request),
    }

@app.get("/api/health")
def health():
    # Render calls this during startup; keep it cheap and deterministic.
    return {"ok": True, "service": "india-candle-ai", "status": "ready"}

@app.get("/api/stocks/search")
def search(q:str=Query("",max_length=120),limit:int=Query(30,ge=1,le=100)):
    return {"results":market.search(q,limit)}

@app.get("/api/stocks/catalog")
def catalog(refresh:bool=False,full:bool=False,limit:int=Query(5000,ge=1,le=10000)):
    if full:
        rows=market.catalog.all(force=refresh)
        return {"results":rows[:limit],"count":len(rows)}
    return market.catalog_status(refresh)

@app.get("/api/stocks/availability")
async def stock_availability(symbol:str=Query(...,min_length=1,max_length=120)):
    return await run_in_threadpool(market.availability,symbol,["5m","15m","30m","60m","1d"])

@app.get("/api/quotes")
async def quotes(symbols:str=Query("",max_length=2000),limit:int=Query(24,ge=1,le=24)):
    requested=[x.strip() for x in symbols.split(",") if x.strip()] if symbols else [s for s,_ in COMMON_INDIAN_STOCKS[:limit]]
    return {"results":await run_in_threadpool(market.pulse,requested[:limit])}

@app.get("/api/analyze")
async def analyze(request:Request,symbol:str=Query(...,min_length=1,max_length=120),interval:str=Query(settings.default_interval),retrain:bool=False,refresh_data:bool=False):
    rm=repo_for(request)
    try:
        return await run_in_threadpool(engine.analyze,symbol,interval,retrain,refresh_data,rm)
    except ValueError as e: raise HTTPException(422,str(e))
    except YahooDataError as e: raise HTTPException(503,str(e))
    except Exception as e: raise HTTPException(503,f"Analysis unavailable: {e}")

@app.get("/api/full-analysis")
async def full_analysis(request:Request,symbol:str,interval:str=settings.default_interval):
    try: return await run_in_threadpool(engine.full_analysis,symbol,interval,repo_for(request))
    except Exception as e: raise HTTPException(503,f"Full analysis unavailable: {e}")

@app.get("/api/backtest")
async def backtest(request:Request,symbol:str,interval:str=settings.default_interval):
    try: return await run_in_threadpool(engine.backtest_only,symbol,interval,repo_for(request))
    except Exception as e: raise HTTPException(503,f"Backtest unavailable: {e}")

@app.get("/api/pulse")
async def pulse(symbols:str|None=None,limit:int=Query(12,ge=1,le=24)):
    selected=[x.strip() for x in symbols.split(",") if x.strip()][:24] if symbols else [s for s,_ in COMMON_INDIAN_STOCKS[:limit]]
    return {"results":await run_in_threadpool(market.pulse,selected)}

@app.get("/api/journal")
def journal(limit:int=Query(25,ge=1,le=100)):
    return {"results":recent("signal_journal",limit)}

@app.get("/api/audit")
def audit_events(limit:int=Query(30,ge=1,le=100)):
    return {"results":recent("audit_events",limit)}

@app.post("/api/repository/check")
async def repo_check(request:Request):
    require_admin(request); rm=repo_for(request)
    result=await run_in_threadpool(rm.scan,False)
    engine.invalidate_repository_cache(rm.session_id)
    return result

@app.post("/api/repository/accept")
async def repo_accept(request:Request):
    require_admin(request); rm=repo_for(request)
    result=await run_in_threadpool(rm.scan,True)
    engine.invalidate_repository_cache(rm.session_id)
    return result

@app.post("/api/repository/reset")
async def repo_reset(request:Request):
    require_admin(request); rm=repo_for(request)
    result=await run_in_threadpool(rm.reset)
    engine.invalidate_repository_cache(rm.session_id)
    return result

@app.post("/api/repository/simulate")
async def repo_simulate(request:Request):
    require_admin(request); rm=repo_for(request)
    result=await run_in_threadpool(rm.simulate_overnight)
    engine.invalidate_repository_cache(rm.session_id)
    return result

@app.post("/api/repository/source/github")
async def repo_source_github(request:Request,url:str):
    require_admin(request); rm=repo_for(request)
    try:
        result=await run_in_threadpool(rm.clone_public_github,url)
        engine.invalidate_repository_cache(rm.session_id)
        return result
    except Exception as e: raise HTTPException(422,str(e))

@app.post("/api/repository/bind-model")
async def repo_bind_model(request:Request):
    require_admin(request); rm=repo_for(request)
    try:
        result=await run_in_threadpool(rm.bind_to_model)
        engine.invalidate_repository_cache(rm.session_id)
        return result
    except Exception as e: raise HTTPException(422,str(e))

@app.post("/api/repository/source/github/refresh")
async def repo_source_github_refresh(request:Request):
    require_admin(request); rm=repo_for(request)
    try:
        result=await run_in_threadpool(rm.refresh_public_github)
        engine.invalidate_repository_cache(rm.session_id)
        return result
    except Exception as e: raise HTTPException(422,str(e))

@app.post("/api/webhook/github")
async def github_webhook(request:Request):
    secret=settings.github_webhook_secret
    if not secret: raise HTTPException(503,"GitHub webhook is disabled until GITHUB_WEBHOOK_SECRET is configured.")
    body=await request.body()
    signature=request.headers.get("X-Hub-Signature-256","")
    digest="sha256="+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,digest): raise HTTPException(401,"Invalid webhook signature.")
    event=request.headers.get("X-GitHub-Event","push")
    rm=repo_for(request)
    if rm.source().get("type")!="github-public":
        raise HTTPException(409,"No public GitHub repository is bound to this session.")
    result=await run_in_threadpool(rm.refresh_public_github)
    engine.invalidate_repository_cache(rm.session_id)
    return {"ok":True,"event":event,"repository_state":result["state"],"impact":result["impact"],"repository":rm.source().get("url")}

@app.get("/api/trust")
async def trust(request:Request,symbol:str="TCS",interval:str=settings.default_interval):
    data=await run_in_threadpool(engine.analyze,symbol,interval,False,False,repo_for(request))
    return data["prediction"]["trust"]

if __name__=="__main__":
    import uvicorn
    uvicorn.run("app.main:app",host="0.0.0.0",port=int(os.getenv("PORT","8000")),reload=False)
