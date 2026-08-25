"""Smoke test and health check tests.

Verifies that the app factory builds and serves requests, and checks
the behavior of the /health endpoint under success and failure modes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from docsgraph_server.main import create_app


@pytest.mark.unit
@patch("docsgraph_server.db.session.get_engine")
@patch("redis.asyncio.from_url")
async def test_health_returns_ok(
    mock_redis_from_url: MagicMock, mock_get_engine: MagicMock
) -> None:
    """Verify that /health returns 200 OK when both DB and Redis are connected."""
    mock_conn = AsyncMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn
    mock_get_engine.return_value = mock_engine

    mock_redis_client = AsyncMock()
    mock_redis_from_url.return_value = mock_redis_client

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_conn.execute.assert_called_once()
    mock_redis_client.ping.assert_called_once()
    mock_redis_client.close.assert_called_once()


@pytest.mark.unit
@patch("docsgraph_server.db.session.get_engine")
@patch("redis.asyncio.from_url")
async def test_health_db_failure(
    mock_redis_from_url: MagicMock, mock_get_engine: MagicMock
) -> None:
    """Verify that /health returns 503 when the database check fails."""
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("DB Connection Timeout")
    mock_get_engine.return_value = mock_engine

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database connection failed"}


@pytest.mark.unit
@patch("docsgraph_server.db.session.get_engine")
@patch("redis.asyncio.from_url")
async def test_health_redis_failure(
    mock_redis_from_url: MagicMock, mock_get_engine: MagicMock
) -> None:
    """Verify that /health returns 503 when the Redis check fails."""
    mock_conn = AsyncMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn
    mock_get_engine.return_value = mock_engine

    mock_redis_client = AsyncMock()
    mock_redis_client.ping.side_effect = Exception("Redis Connection Refused")
    mock_redis_from_url.return_value = mock_redis_client

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Redis connection failed"}
