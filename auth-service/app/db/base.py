from __future__ import annotations
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker,create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

class Base(DeclarativeBase):
    pass

engine=create_async_engine(settings.DATABASE_URL,pool_pre_ping=True)
SessionLocal=async_sessionmaker(bind=engine , expire_on_commit=False,class_=AsyncSession)

async def get_db() -> AsyncGenerator[AsyncSession,None]:
    async with SessionLocal() as session:
        yield session
        