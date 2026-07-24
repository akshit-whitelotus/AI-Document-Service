from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request

from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.routes_auth import router as auth_router
from app.core.limiter import limiter
from app.core.security import ensure_keypair_exists
from app.db.base import engine

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger("auth-service")

@asynccontextmanager
async def lifespan(app:FastAPI):
    ensure_keypair_exists()
    logger.info("auth-service starting up")
    yield
    await engine.dispose()
    logger.info("auth-service shut down")

app=FastAPI(title="Auth Service",version="1.0.0",lifespan=lifespan)

app.state.limiter=limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request:Request,exc:RateLimitExceeded):
    return JSONResponse(status_code=429,content={"detail":"Too many requests, slow down"})

app.include_router(auth_router)

@app.get("/healthz")
async def healthz():
    return {"status":"ok"}