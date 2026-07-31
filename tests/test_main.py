"""Smoke test: the app factory builds and the process serves requests.

Placeholder until real endpoints land — deliberately not testing
per-module stub behavior, since there is no real logic yet.
"""

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
