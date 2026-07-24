"""
Middleware behaviour tests.
"""

import pytest

from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_correlation_id_header():

    transport = ASGITransport(
        app=app
    )


    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        response = await client.get(
            "/",
            headers={
                "X-Correlation-ID":
                    "test-request-id"
            },
        )


    assert response.status_code == 200

    assert (
        response.headers[
            "X-Correlation-ID"
        ]
        ==
        "test-request-id"
    )



@pytest.mark.asyncio
async def test_generated_correlation_id():

    transport = ASGITransport(
        app=app
    )


    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        response = await client.get("/")


    assert (
        "X-Correlation-ID"
        in response.headers
    )