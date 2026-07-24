import asyncio
import itertools
import uuid
from datetime import datetime, timezone

import pytest
import httpx

from app.main import app
from app.schemas.job import JobProgress

from tests.conftest import make_token

_port_counter = itertools.count(8010)


async def _run_server(port: int):
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    await server.serve()


async def _stop_server(server_task: asyncio.Task) -> None:
    server_task.cancel()
    try:
        await server_task
    except (asyncio.CancelledError, SystemExit):
        pass


@pytest.mark.asyncio
async def test_sse_owner_receives_progress_event(test_user_id):
    job_manager = app.state.job_manager
    job_id = str(uuid.uuid4())
    await job_manager.create_job(job_id, test_user_id, "storage/uploads/does-not-matter.txt")
    token = make_token(test_user_id)

    port = next(_port_counter)
    server_task = asyncio.create_task(_run_server(port))
    await asyncio.sleep(1)

    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=None
        ) as client:

            async def consume():
                async with client.stream(
                    "GET", f"/sse/jobs/{job_id}", params={"token": token}
                ) as response:
                    assert response.status_code == 200
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            return line

            consumer = asyncio.create_task(consume())
            await asyncio.sleep(0.5)

            await app.state.job_manager.publish(
                JobProgress(
                    job_id=job_id,
                    status="processing",
                    progress=50,
                    timestamp=datetime.now(timezone.utc),
                )
            )

            result = await asyncio.wait_for(consumer, timeout=5)
            assert job_id in result
    finally:
        await _stop_server(server_task)


@pytest.mark.asyncio
async def test_sse_rejects_non_owner(test_user_id):
    job_manager = app.state.job_manager
    job_id = str(uuid.uuid4())
    await job_manager.create_job(job_id, test_user_id, "storage/uploads/does-not-matter.txt")
    other_user_token = make_token(uuid.uuid4())

    port = next(_port_counter)
    server_task = asyncio.create_task(_run_server(port))
    await asyncio.sleep(1)

    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=None
        ) as client:
            response = await client.get(
                f"/sse/jobs/{job_id}", params={"token": other_user_token}
            )
            assert response.status_code == 404
    finally:
        await _stop_server(server_task)


@pytest.mark.asyncio
async def test_sse_requires_token(test_user_id):
    job_manager = app.state.job_manager
    job_id = str(uuid.uuid4())
    await job_manager.create_job(job_id, test_user_id, "storage/uploads/does-not-matter.txt")

    port = next(_port_counter)
    server_task = asyncio.create_task(_run_server(port))
    await asyncio.sleep(1)

    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=None
        ) as client:
            response = await client.get(f"/sse/jobs/{job_id}")
            assert response.status_code == 422  # missing required query param
    finally:
        await _stop_server(server_task)
