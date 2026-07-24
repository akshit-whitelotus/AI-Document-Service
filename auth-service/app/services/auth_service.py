from __future__ import annotations
import hashlib,uuid
from datetime import datetime,timedelta,timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import create_access_token,generate_refresh_token,hash_password,verify_password

from app.models.login_history import LoginHistory
from app.models.refresh_token import RefreshToken
from app.models.user import User

class EmailAlreadyRegistered(Exception):
    pass
class InvalidCredentials(Exception):
    """
    Deliberately generic: used both for 'no such user' and 'wrong
    password' so callers can't distinguish the two and enumerate emails.
    """
class InvalidOrExpiredRefreshToken(Exception):
    pass

def _hash_token(raw_token:str)->str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

async def register_user(db:AsyncSession,email:str,password:str) -> User:
    existing=await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise EmailAlreadyRegistered()
    user=User(email=email,hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
async def _record_login_attempt(db:AsyncSession,*,email:str,success:bool,user_id:uuid.UUID|None,ip_address:str | None,user_agent:str | None) -> None :
    db.add(LoginHistory(user_id=user_id,email_attempted=email,success=success,ip_address=ip_address,user_agent=user_agent))
    await db.commit()

async def authenticate_and_issue_tokens(db:AsyncSession,*,email:str,password:str,ip_address:str |None=None,user_agent:str | None=None) -> tuple[str,str,int]:
    user=await db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(password,user.hashed_password):
        await _record_login_attempt(db,email=email,success=False,user_id=user.id if user else None,ip_address=ip_address,user_agent=user_agent)
        raise InvalidCredentials()
    await _record_login_attempt(db,email=email,success=True,user_id=user.id,ip_address=ip_address,user_agent=user_agent) 
    access_token=create_access_token(user_id=str(user.id),email=user.email)
    refresh_token_raw=generate_refresh_token()
    db.add(RefreshToken(user_id=user.id,token_hash=_hash_token(refresh_token_raw),expires_at=datetime.now(timezone.utc)+timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),user_agent=user_agent,ip_address=ip_address))
    await db.commit()
    return access_token,refresh_token_raw,settings.ACCESS_TOKEN_EXPIRE_MINUTES*60

async def rotate_refresh_token(db:AsyncSession,*,raw_refresh_token:str)-> tuple[str,str,int]:
    token_hash=_hash_token(raw_refresh_token)
    token_row=await db.scalar(select(RefreshToken).where(RefreshToken.token_hash==token_hash))
    now=datetime.now(timezone.utc)
    if (token_row is None or token_row.revoked_at is not None or token_row.expires_at.replace(tzinfo=timezone.utc)<now):
        raise InvalidOrExpiredRefreshToken()
    user=await db.get(User,token_row.user_id)
    if user is None or not user.is_active:
        raise InvalidOrExpiredRefreshToken()

    token_row.revoked_at=now
    await db.commit()

    access_token=create_access_token(user_id=str(user.id),email=user.email)
    new_refresh_raw=generate_refresh_token()
    db.add(RefreshToken(user_id=user.id,token_hash=_hash_token(new_refresh_raw),expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)))
    await db.commit()
    return access_token,new_refresh_raw,settings.ACCESS_TOKEN_EXPIRE_MINUTES*60

async def revoke_refresh_token(db:AsyncSession,*,raw_refresh_token:str) -> None:
    token_hash=_hash_token(raw_refresh_token)
    token_row=await db.scalar(select(RefreshToken).where(RefreshToken.token_hash==token_hash))
    if token_row is not None and token_row.revoked_at is None:
        token_row.revoked_at=datetime.now(timezone.utc)
        await db.commit()
