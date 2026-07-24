from __future__ import annotations
from fastapi import FastAPI
from app.api.v1.routes_documents import router as document_router
from app.api.v1.routes_sse import router as sse_router
from app.api.v1.routes_ws import router as ws_router

from app.core.config import settings
from app.core .lifespan import lifespan
from app.core.logging import setup_logging

from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.latency_logging import LatencyLoggingMiddleware

setup_logging()

app=FastAPI(title=settings.APP_NAME,version="1.0.0",description="""
Async AI Document Processing Service.

Features:

- Streaming uploads
- Background AI processing
- WebSocket progress updates
- Server Sent Events
- Streaming downloads
- Correlation IDs
- Request latency logging
""",
lifespan=lifespan)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(LatencyLoggingMiddleware)

app.include_router(document_router)
app.include_router(sse_router)
app.include_router(ws_router)

@app.get("/",tags=["Health"],summary="Health Check")
async def health():
    return {
        "service":settings.APP_NAME,
        "status":"Healthy"
    }
