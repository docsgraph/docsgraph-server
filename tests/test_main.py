"""Tests for the FastAPI app factory and the /health endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from docsgraph_server.main import create_app


@pytest.mark.unit
async def test_health_returns_ok() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
async def test_domain_routers_are_mounted() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/documents")

    assert response.status_code == 200
    assert response.json() == {"documents": []}
