import logging,time
from starlette.middleware.base import (BaseHTTPMiddleware)
from fastapi import Request

logger=logging.getLogger("request-latency")

class LatencyLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request:Request, call_next):
       start=time.perf_counter()
       response=await call_next(request)
       elapsed_ms=(time.perf_counter()-start)*1000
       logger.info(
           "%s %s %s %.2fms",
           request.method,
           request.url.path,
           response.status_code,
           elapsed_ms
       )
       return response
    
