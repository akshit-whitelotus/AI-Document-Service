from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# --- Point the app at an in-memory SQLite DB BEFORE importing anything
# that reads settings, so tests never touch a real Postgres database.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.db.base as db_base  # noqa: E402
import app.services.job_manager as job_manager_module  # noqa: E402
import app.core.auth as auth_module  # noqa: E402
from app.main import app  # noqa: E402


# --- Test RSA keypair, standing in for the auth service's signing key.
# We sign tokens with this directly instead of running a real auth-service
# process, and monkeypatch the JWKS fetch to return its public half — so
# these tests exercise the *real* verification code path in app/core/auth.py
# without needing a live auth-service.
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_private_pem = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()


def _b64url_uint(value: int) -> str:
    import base64

    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _test_jwks() -> dict:
    numbers = _private_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-key-1",
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }


def make_token(user_id: uuid.UUID, *, expired: bool = False) -> str:
    """Mint a token that app/core/auth.py will accept as if it came from the real auth-service."""
    now = datetime.now(timezone.utc)
    exp = now - timedelta(minutes=1) if expired else now + timedelta(minutes=15)
    payload = {
        "sub": str(user_id),
        "email": f"{user_id}@example.com",
        "iss": settings.AUTH_ISSUER,
        "aud": settings.AUTH_AUDIENCE,
        "iat": now,
        "exp": exp,
        "type": "access",
    }
    return jwt.encode(payload, _private_pem, algorithm="RS256", headers={"kid": "test-key-1"})


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch):
    async def _fake_get_jwks():
        return _test_jwks()

    monkeypatch.setattr(auth_module, "_get_jwks", _fake_get_jwks)


@pytest_asyncio.fixture(autouse=True)
async def _test_db(monkeypatch):
    """Fresh in-memory SQLite DB per test, wired into both the FastAPI
    get_db dependency and JobManager's internal SessionLocal usage."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    # job_manager.py does `from app.db.base import SessionLocal`, binding
    # the name into its own module namespace — patching app.db.base.
    # SessionLocal alone would NOT affect that already-bound reference, so
    # we patch job_manager's copy directly too.
    monkeypatch.setattr(db_base, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(job_manager_module, "SessionLocal", TestSessionLocal)

    yield TestSessionLocal

    await engine.dispose()


@pytest.fixture
def test_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def auth_headers(test_user_id):
    return {"Authorization": f"Bearer {make_token(test_user_id)}"}


@pytest_asyncio.fixture
async def client():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
