from __future__ import annotations
import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

correlation_id_ctx:ContextVar[str|None]=(
    ContextVar(
        "correlation_id",
        default=None
    )

)
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request:Request, call_next):
        correlation_id=(request.headers.get("X-Correlation-ID") or str(uuid.uuid4()))
        token=correlation_id_ctx.set(correlation_id)

        try:
            response=await call_next(request)
            response.headers["X-Correlation-ID"]=correlation_id
            return response
        finally:
            correlation_id_ctx.reset(token)
        