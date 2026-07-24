from __future__ import annotations
import uuid
from fastapi import APIRouter,Depends,HTTPException,Request,status
from jose import JWTError,jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import get_jwks
from app.db.base import get_db
from app.models.user import User
from app.schemas.auth import AccessTokenResponse,GenericMessage,RefreshRequest,TokenPair,UserCreate,UserLogin,UserRead
from app.services.auth_service import EmailAlreadyRegistered,InvalidCredentials,InvalidOrExpiredRefreshToken
from app.services import auth_service
router=APIRouter(prefix="/auth",tags=["auth"])

bearer_scheme_error=HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-AUthenticate":"Bearer"}
)

async def get_current_user(request:Request,db:AsyncSession=Depends(get_db)) -> User:
    auth_header=request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise bearer_scheme_error
    token=auth_header.split(" ",1)[1]
    try:
        payload=jwt.decode(
            token,
            get_jwks(),
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER
        )
    except JWTError:
        raise bearer_scheme_error

    user_id=payload.get("sub")
    if not user_id:
        raise bearer_scheme_error

    try:
        user_id=uuid.UUID(user_id)
    except (ValueError,TypeError):
        raise bearer_scheme_error

    user=await db.get(User,user_id)
    if user is  None or not user.is_active:
        raise bearer_scheme_error
    return user

@router.post("/register",response_model=UserRead,status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def register(request:Request,payload:UserCreate,db:AsyncSession=Depends(get_db)):
    try:
        user=await auth_service.register_user(db,email=payload.email,password=payload.password)
    except EmailAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration failed. If this email is already in use , try logging in instead"

        )
    return user

@router.post("/login",response_model=TokenPair)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(request:Request,payload:UserLogin,db:AsyncSession=Depends(get_db)):
    try:
        access_token,refresh_token,expires_in=await auth_service.authenticate_and_issue_tokens(
            db,
            email=payload.email,
            password=payload.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    return TokenPair(access_token=access_token,refresh_token=refresh_token,expires_in=expires_in)

@router.post("/refresh",response_model=TokenPair)
async def refresh(payload:RefreshRequest,db:AsyncSession=Depends(get_db)):
    try:
        access_token,new_refresh_token,expires_in=await auth_service.rotate_refresh_token(db,raw_refresh_token=payload.refresh_token)
    except InvalidOrExpiredRefreshToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid,expired,or has already been used"
        )
    return TokenPair(access_token=access_token,refresh_token=new_refresh_token,expires_in=expires_in)

@router.post("/logout",response_model=GenericMessage)
async def logout(payload:RefreshRequest , db:AsyncSession=Depends(get_db)):
    await auth_service.revoke_refresh_token(db,raw_refresh_token=payload.refresh_token)
    return GenericMessage(detail="Logged out")

@router.get("/me",response_model=UserRead)
async def me(current_user: User=Depends(get_current_user)):
    return current_user

@router.get("/.well-known/jwks.json",include_in_schema=True)
async def jwks():
    return get_jwks()
