from __future__ import annotations

import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

# --- Point the app at an in-memory SQLite DB and a temp key directory
# BEFORE importing anything that reads settings, so tests never touch the
# real Postgres database.
_tmp_keys_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PRIVATE_KEY_PATH"] = os.path.join(_tmp_keys_dir, "private_key.pem")
os.environ["PUBLIC_KEY_PATH"] = os.path.join(_tmp_keys_dir, "public_key.pem")

from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.core.limiter import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
async def client(test_engine, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    import app.db.base as db_base

    TestSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    monkeypatch.setattr(db_base, "SessionLocal", TestSessionLocal)

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[db_base.get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
