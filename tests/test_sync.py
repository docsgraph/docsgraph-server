import uuid
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from docsgraph_server.db.session import get_engine
from docsgraph_server.main import create_app


@pytest.fixture(autouse=True)
async def cleanup_db() -> None:
    """Ensure the sync_operations table is empty before each test run."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM sync_operations"))


@pytest.mark.integration
async def test_sync_push_and_pull() -> None:
    """Verify push and pull endpoints correctly persist and synchronize operations."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Pull on empty server
        pull_response = await client.get("/api/v1/sync/pull?cursor=0")
        assert pull_response.status_code == 200
        pull_data = pull_response.json()
        assert pull_data["ops"] == []
        assert pull_data["cursor"] == 0

        # 2. Push an update operation
        op_id = str(uuid.uuid4())
        entity_id = str(uuid.uuid4())
        push_request = {
            "client_id": str(uuid.uuid4()),
            "cursor": 0,
            "ops": [
                {
                    "op_id": op_id,
                    "entity_type": "document",
                    "entity_id": entity_id,
                    "operation": "update",
                    "payload": {"title": "My Document"},
                    "client_timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }
        push_response = await client.post("/api/v1/sync/push", json=push_request)
        assert push_response.status_code == 200
        push_data = push_response.json()
        assert len(push_data["acks"]) == 1
        assert push_data["acks"][0]["op_id"] == op_id
        assert push_data["cursor"] > 0

        # 3. Pull again to verify both pushed and conflict-simulated operations
        pull_response = await client.get("/api/v1/sync/pull?cursor=0")
        assert pull_response.status_code == 200
        pull_data = pull_response.json()
        assert len(pull_data["ops"]) == 2
        assert pull_data["ops"][0]["op_id"] == op_id
        assert "Server Version Conflict" in pull_data["ops"][1]["payload"]["title"]
        assert pull_data["cursor"] > 0
