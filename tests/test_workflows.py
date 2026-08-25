import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from docsgraph_server.db.session import get_engine
from docsgraph_server.main import create_app


@pytest.fixture(autouse=True)
async def cleanup_db() -> AsyncGenerator[None, None]:
    """Clean up workflow and document tables before/after each test."""
    get_engine.cache_clear()

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM audit_events"))
        await conn.execute(text("DELETE FROM workflow_instances"))
        await conn.execute(text("DELETE FROM workflow_definitions"))
        await conn.execute(text("DELETE FROM documents"))

    yield

    await engine.dispose()
    get_engine.cache_clear()


@pytest.mark.integration
async def test_workflow_engine_lifecycle_and_audit() -> None:
    """Validate workflow definitions, instance traversal, transitions, and auditing."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a document to attach workflow to
        doc_id = uuid.uuid4()
        doc_response = await client.post(
            "/api/v1/documents",
            json={"id": str(doc_id), "title": "Design Specs V1"},
        )
        assert doc_response.status_code == 201

        # 2. Define the Review/Approval Workflow
        defn_id = uuid.uuid4()
        defn_response = await client.post(
            "/api/v1/workflows/definitions",
            json={
                "id": str(defn_id),
                "name": "document_approval_flow",
                "states": ["draft", "in_review", "approved", "rejected"],
                "transitions": [
                    {
                        "from_state": "draft",
                        "to_state": "in_review",
                        "event": "submit",
                    },
                    {
                        "from_state": "in_review",
                        "to_state": "approved",
                        "event": "approve",
                    },
                    {
                        "from_state": "in_review",
                        "to_state": "rejected",
                        "event": "reject",
                    },
                ],
            },
        )
        assert defn_response.status_code == 201

        # 3. Start/Attach workflow instance to the document
        actor_id = uuid.uuid4()
        inst_id = uuid.uuid4()
        inst_response = await client.post(
            "/api/v1/workflows/instances",
            json={
                "id": str(inst_id),
                "workflow_definition_id": str(defn_id),
                "document_id": str(doc_id),
                "actor_id": str(actor_id),
                "context": {"notes": "Please review soon"},
            },
        )
        assert inst_response.status_code == 201
        inst_data = inst_response.json()
        assert inst_data["current_state"] == "draft"

        # 4. Advance through workflow states via API
        # Event: submit -> state: in_review
        advance1_response = await client.post(
            f"/api/v1/workflows/instances/{inst_data['id']}/advance",
            json={"event": "submit", "actor_id": str(actor_id)},
        )
        assert advance1_response.status_code == 200

        # Check state is updated
        get_inst_response = await client.get(f"/api/v1/workflows/instances/{inst_data['id']}")
        assert get_inst_response.status_code == 200
        assert get_inst_response.json()["current_state"] == "in_review"

        # Event: approve -> state: approved
        advance2_response = await client.post(
            f"/api/v1/workflows/instances/{inst_data['id']}/advance",
            json={"event": "approve", "actor_id": str(actor_id)},
        )
        assert advance2_response.status_code == 200

        # Check state is approved
        get_inst_response = await client.get(f"/api/v1/workflows/instances/{inst_data['id']}")
        assert get_inst_response.json()["current_state"] == "approved"

        # 5. Verify invalid transitions are rejected
        # Trying to reject when state is already approved should fail
        bad_advance_response = await client.post(
            f"/api/v1/workflows/instances/{inst_data['id']}/advance",
            json={"event": "reject", "actor_id": str(actor_id)},
        )
        assert bad_advance_response.status_code == 400

        # 6. Verify audit logs record all actions and state changes
        audit_response = await client.get(f"/api/v1/audit?resource_id={inst_data['id']}")
        assert audit_response.status_code == 200
        audit_events = audit_response.json()

        # Should have 3 events: 1 workflow.started, 2 workflow.state_change
        assert len(audit_events) == 3

        # Event order is descending by occurred_at (newest first)
        # 1. State change from in_review to approved
        assert audit_events[0]["action"] == "workflow.state_change"
        assert audit_events[0]["metadata_json"]["from_state"] == "in_review"
        assert audit_events[0]["metadata_json"]["to_state"] == "approved"
        assert audit_events[0]["metadata_json"]["event"] == "approve"
        assert audit_events[0]["actor_id"] == str(actor_id)

        # 2. State change from draft to in_review
        assert audit_events[1]["action"] == "workflow.state_change"
        assert audit_events[1]["metadata_json"]["from_state"] == "draft"
        assert audit_events[1]["metadata_json"]["to_state"] == "in_review"
        assert audit_events[1]["metadata_json"]["event"] == "submit"
        assert audit_events[1]["actor_id"] == str(actor_id)

        # 3. Started event
        assert audit_events[2]["action"] == "workflow.started"
        assert audit_events[2]["metadata_json"]["initial_state"] == "draft"
        assert audit_events[2]["actor_id"] == str(actor_id)
