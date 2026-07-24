from __future__ import annotations
import time,uuid,httpx
from fastapi import Depends,HTTPException,Query,Request,WebSocket,status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError,jwt
from app.core.config import settings

_jwks_cache:dict | None=None
_jwks_fetched_at:float = 0.0

# Declaring this as a proper FastAPI security scheme (rather than reading
# the Authorization header manually) is what makes Swagger UI show an
# "Authorize" button for endpoints that depend on it, and lets you paste
# a token once and have it attached to every "Try it out" call in /docs.
# auto_error=False so we raise our own consistent 401 below instead of
# FastAPI's default "Not authenticated" (same message either way here,
# but keeps error handling in one place alongside the WS/SSE variants).
bearer_scheme = HTTPBearer(auto_error=False)

async def _get_jwks() -> dict:
    global _jwks_cache,_jwks_fetched_at

    now =time.monotonic()
    if _jwks_cache is not None and (now - _jwks_fetched_at) < settings.AUTH_JWKS_CACHE_TTL_SECONDS:
        return _jwks_cache

    async with httpx.AsyncClient(timeout=5.0) as client:
        response=await client.get(settings.AUTH_JWKS_URL)
        response.raise_for_status()
        _jwks_cache=response.json()
        _jwks_fetched_at=now
        return _jwks_cache

async def _decode_token(token : str) -> dict :
    global _jwks_cache

    jwks=await _get_jwks()
    try:
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.AUTH_AUDIENCE,
            issuer=settings.AUTH_ISSUER
        )
    except JWTError:
        _jwks_cache = None
        jwks= await _get_jwks()
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.AUTH_AUDIENCE,
            issuer=settings.AUTH_ISSUER
        )

_unauthorised=HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate":"Bearer"}
)

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> uuid.UUID:
    if credentials is None or not credentials.credentials:
        raise _unauthorised

    token = credentials.credentials
    try:
        payload=await _decode_token(token)
    except (JWTError,httpx.HTTPError):
        raise _unauthorised
    sub=payload.get("sub")
    if not sub:
        raise _unauthorised
    try:
        return uuid.UUID(sub)
    except(ValueError,TypeError):
        raise _unauthorised

async def get_current_user_id_ws(websocket:WebSocket,token :str=Query(...)) -> uuid.UUID:
    try:
        payload=await _decode_token(token)
    except (JWTError,httpx.HTTPError):
        await websocket.close(code=4401)
        raise _unauthorised
    sub=payload.get("sub")
    if not sub:
        await websocket.close(code=4401)
        raise _unauthorised
    try:
        return uuid.UUID(sub)
    except (ValueError,TypeError):
        await websocket.close(code=4401)
        raise _unauthorised

async def get_current_user_id_sse(request:Request,token:str=Query(...))-> uuid.UUID:
    try:
        payload=await _decode_token(token)
    except (JWTError,httpx.HTTPError):
        raise _unauthorised

    sub=payload.get("sub")
    if not sub:
        raise _unauthorised
    try:
        return uuid.UUID(sub)
    except (ValueError,TypeError):
        raise _unauthorised
