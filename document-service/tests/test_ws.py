"""
WebSocket progress tests.
"""

import uuid
from datetime import datetime, UTC

import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.job import JobProgress

from tests.conftest import make_token


@pytest.mark.asyncio
async def test_websocket_message_flow(test_user_id):
    token = make_token(test_user_id)

    with TestClient(app) as client:
        job_manager = app.state.job_manager

        job_id = str(uuid.uuid4())
        await job_manager.create_job(job_id, test_user_id, "storage/uploads/does-not-matter.txt")

        with client.websocket_connect(f"/ws/jobs/{job_id}?token={token}") as websocket:
            await job_manager.publish(
                JobProgress(
                    job_id=job_id,
                    status="processing",
                    progress=50,
                    timestamp=datetime.now(UTC),
                )
            )

            message = websocket.receive_json()
            assert message["job_id"] == job_id
            assert message["status"] == "processing"
            assert message["progress"] == 50

            websocket.close()


def test_websocket_requires_token():
    with TestClient(app) as client:
        # No token query param at all -> FastAPI rejects the connection
        # during dependency resolution (missing required query parameter).
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/jobs/{uuid.uuid4()}"):
                pass


@pytest.mark.asyncio
async def test_websocket_rejects_non_owner(test_user_id):
    with TestClient(app) as client:
        job_manager = app.state.job_manager

        job_id = str(uuid.uuid4())
        await job_manager.create_job(job_id, test_user_id, "storage/uploads/does-not-matter.txt")

        other_user_token = make_token(uuid.uuid4())

        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/jobs/{job_id}?token={other_user_token}"):
                pass


def test_websocket_rejects_unknown_job(test_user_id):
    token = make_token(test_user_id)

    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/jobs/{uuid.uuid4()}?token={token}"):
                pass
