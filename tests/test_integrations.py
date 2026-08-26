import hmac
import json
from collections.abc import AsyncGenerator
from hashlib import sha256
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text

from docsgraph_server.db.session import get_engine
from docsgraph_server.main import create_app


@pytest.fixture(autouse=True)
async def cleanup_db() -> AsyncGenerator[None, None]:
    """Clean up tables before and after each test."""
    get_engine.cache_clear()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM integration_configs"))
    yield
    await engine.dispose()
    get_engine.cache_clear()


@pytest.mark.integration
async def test_integrations_framework_lifecycle_and_mock_dispatch() -> None:
    """Verify integration configuration, status listing, dispatch logic, and HMAC signatures."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Initially check integrations list is empty/disabled
        list_res = await client.get("/api/v1/integrations")
        assert list_res.status_code == 200
        integrations = list_res.json()
        assert len(integrations) == 1
        assert integrations[0]["id"] == "webhook_notifier"
        assert integrations[0]["enabled"] is False

        # 2. Configure the webhook notifier integration
        webhook_url = "http://fake-callback.local/webhook"
        secret_key = "super-secret-key"
        config_res = await client.post(
            "/api/v1/integrations/webhook_notifier/configure",
            json={
                "enabled": True,
                "config_json": {
                    "webhook_url": webhook_url,
                    "secret_key": secret_key,
                },
            },
        )
        assert config_res.status_code == 200
        config_data = config_res.json()
        assert config_data["enabled"] is True
        assert config_data["config_json"]["webhook_url"] == webhook_url

        # 3. Test successful dispatch with mocked HTTP POST (and verify HMAC signature)
        mock_response = Response(
            status_code=200,
            text="OK",
            request=httpx.Request("POST", webhook_url),
        )
        captured_calls = []

        original_post = httpx.AsyncClient.post

        async def mock_post_side_effect(
            self_client: httpx.AsyncClient, url: str, *args: Any, **kwargs: Any
        ) -> Response:
            if "fake-callback.local" in str(url):
                captured_calls.append((url, kwargs))
                return mock_response
            return await original_post(self_client, url, *args, **kwargs)

        with patch("httpx.AsyncClient.post", autospec=True) as mock_post:
            mock_post.side_effect = mock_post_side_effect

            dispatch_res = await client.post(
                "/api/v1/integrations/dispatch",
                json={
                    "event_type": "document.created",
                    "payload": {"document_id": "12345", "title": "Test Document"},
                },
            )
            assert dispatch_res.status_code == 200
            outcomes = dispatch_res.json()["outcomes"]

            # Verify outcome details
            assert "webhook_notifier" in outcomes
            assert outcomes["webhook_notifier"]["status"] == "success"
            assert outcomes["webhook_notifier"]["status_code"] == 200

            # Verify mock_post call parameters
            assert len(captured_calls) == 1
            called_url, kwargs = captured_calls[0]
            called_json = kwargs["json"]
            called_headers = kwargs["headers"]

            assert called_url == webhook_url
            assert called_json["event_type"] == "document.created"
            assert called_json["payload"]["title"] == "Test Document"

            # Verify signature matches
            expected_sig_header = called_headers.get("X-Docsgraph-Signature")
            assert expected_sig_header is not None

            # Compute signature ourselves to check correctness
            serialized = json.dumps(called_json, sort_keys=True).encode("utf-8")
            computed = hmac.new(secret_key.encode("utf-8"), serialized, sha256).hexdigest()
            assert expected_sig_header == computed

        # 4. Test failure dispatch (graceful degradation)
        async def mock_post_fail_side_effect(
            self_client: httpx.AsyncClient, url: str, *args: Any, **kwargs: Any
        ) -> Response:
            if "fake-callback.local" in str(url):
                raise Exception("Connection Refused")
            return await original_post(self_client, url, *args, **kwargs)

        with patch("httpx.AsyncClient.post", autospec=True) as mock_post_fail:
            mock_post_fail.side_effect = mock_post_fail_side_effect

            # Dispatch should not raise an error up to the caller
            dispatch_res_fail = await client.post(
                "/api/v1/integrations/dispatch",
                json={
                    "event_type": "document.deleted",
                    "payload": {"document_id": "12345"},
                },
            )
            assert dispatch_res_fail.status_code == 200
            outcomes_fail = dispatch_res_fail.json()["outcomes"]

            # Outcome registers as failed but does not crash the endpoint/core
            assert "webhook_notifier" in outcomes_fail
            assert outcomes_fail["webhook_notifier"]["status"] == "failed"
            assert "Connection Refused" in outcomes_fail["webhook_notifier"]["error"]
