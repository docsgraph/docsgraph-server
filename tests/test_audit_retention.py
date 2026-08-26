import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from docsgraph_server.db.models import DbAuditEvent, DbDocument
from docsgraph_server.db.session import get_engine, get_sessionmaker
from docsgraph_server.main import create_app


@pytest.fixture(autouse=True)
async def cleanup_db() -> AsyncGenerator[None, None]:
    """Clean up tables before and after each test."""
    get_engine.cache_clear()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM retention_policies"))
        await conn.execute(text("DELETE FROM audit_events"))
        await conn.execute(text("DELETE FROM documents"))
        await conn.execute(text("DELETE FROM collections"))
    yield
    await engine.dispose()
    get_engine.cache_clear()


@pytest.mark.integration
async def test_audit_logs_and_retention_policies() -> None:
    """Validate audit logging, querying, exporting, and retention policy enforcement."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a collection
        col_id = uuid.uuid4()
        col_res = await client.post(
            "/api/v1/documents/collections",
            json={"id": str(col_id), "name": "Financial Reports"},
        )
        assert col_res.status_code == 201

        # 2. Seed documents with different creation dates and legal hold statuses
        now = datetime.now(UTC).replace(tzinfo=None)

        sessionmaker = get_sessionmaker()

        doc_a_id = uuid.uuid4()  # In collection, 30 days old
        doc_b_id = uuid.uuid4()  # In collection, 30 days old, legal hold
        doc_c_id = uuid.uuid4()  # Out of collection, 15 days old
        doc_d_id = uuid.uuid4()  # Out of collection, 2 days old

        audit_x_id = uuid.uuid4()  # 15 days old audit log
        audit_y_id = uuid.uuid4()  # 2 days old audit log

        actor_id = uuid.uuid4()

        async with sessionmaker() as db:
            db.add(
                DbDocument(
                    id=doc_a_id,
                    title="Expired Doc In Collection",
                    collection_id=col_id,
                    created_at=now - timedelta(days=30),
                    legal_hold=False,
                )
            )
            db.add(
                DbDocument(
                    id=doc_b_id,
                    title="Expired Doc Under Legal Hold",
                    collection_id=col_id,
                    created_at=now - timedelta(days=30),
                    legal_hold=True,
                )
            )
            db.add(
                DbDocument(
                    id=doc_c_id,
                    title="Expired Org Wide Doc",
                    collection_id=None,
                    created_at=now - timedelta(days=15),
                    legal_hold=False,
                )
            )
            db.add(
                DbDocument(
                    id=doc_d_id,
                    title="Active Org Wide Doc",
                    collection_id=None,
                    created_at=now - timedelta(days=2),
                    legal_hold=False,
                )
            )

            db.add(
                DbAuditEvent(
                    id=audit_x_id,
                    actor_id=actor_id,
                    action="document.read",
                    resource_id=doc_c_id,
                    metadata_json={"ip": "127.0.0.1"},
                    occurred_at=now - timedelta(days=15),
                )
            )
            db.add(
                DbAuditEvent(
                    id=audit_y_id,
                    actor_id=actor_id,
                    action="document.write",
                    resource_id=doc_d_id,
                    metadata_json={"changes": "title"},
                    occurred_at=now - timedelta(days=2),
                )
            )
            await db.commit()

        # 3. Query audit logs via API
        audit_res = await client.get("/api/v1/audit")
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert len(events) == 2

        filtered_res = await client.get("/api/v1/audit?action=document.write")
        assert filtered_res.status_code == 200
        filtered_events = filtered_res.json()
        assert len(filtered_events) == 1
        assert filtered_events[0]["id"] == str(audit_y_id)

        # 4. Export audit logs via API
        export_res = await client.get("/api/v1/audit/export")
        assert export_res.status_code == 200
        assert export_res.headers["content-type"] == "text/csv; charset=utf-8"
        csv_content = export_res.text
        assert "id,actor_id,action,resource_id,metadata_json,occurred_at" in csv_content
        assert str(audit_x_id) in csv_content
        assert str(audit_y_id) in csv_content

        # 5. Create and apply a collection-specific document retention policy (10 days retention)
        policy_1_id = uuid.uuid4()
        p1_res = await client.post(
            "/api/v1/retention/policies",
            json={
                "id": str(policy_1_id),
                "collection_id": str(col_id),
                "policy_type": "document",
                "retention_days": 10,
            },
        )
        assert p1_res.status_code == 201

        p1_apply_res = await client.post(f"/api/v1/retention/policies/{policy_1_id}/apply")
        assert p1_apply_res.status_code == 200
        assert p1_apply_res.json()["purged_count"] == 1

        async with sessionmaker() as db:
            docs = (await db.execute(select(DbDocument))).scalars().all()
            doc_ids = {d.id for d in docs}
            assert doc_a_id not in doc_ids
            assert doc_b_id in doc_ids
            assert doc_c_id in doc_ids
            assert doc_d_id in doc_ids

        # 6. Create and apply org-wide document retention policy (10 days retention)
        policy_2_id = uuid.uuid4()
        p2_res = await client.post(
            "/api/v1/retention/policies",
            json={
                "id": str(policy_2_id),
                "collection_id": None,
                "policy_type": "document",
                "retention_days": 10,
            },
        )
        assert p2_res.status_code == 201

        p2_apply_res = await client.post(f"/api/v1/retention/policies/{policy_2_id}/apply")
        assert p2_apply_res.status_code == 200
        assert p2_apply_res.json()["purged_count"] == 1

        async with sessionmaker() as db:
            docs = (await db.execute(select(DbDocument))).scalars().all()
            doc_ids = {d.id for d in docs}
            assert doc_c_id not in doc_ids
            assert doc_d_id in doc_ids

        # 7. Create and apply org-wide audit log retention policy (5 days retention)
        policy_3_id = uuid.uuid4()
        p3_res = await client.post(
            "/api/v1/retention/policies",
            json={
                "id": str(policy_3_id),
                "collection_id": None,
                "policy_type": "audit_log",
                "retention_days": 5,
            },
        )
        assert p3_res.status_code == 201

        p3_apply_res = await client.post(f"/api/v1/retention/policies/{policy_3_id}/apply")
        assert p3_apply_res.status_code == 200
        assert p3_apply_res.json()["purged_count"] == 1

        async with sessionmaker() as db:
            events = (await db.execute(select(DbAuditEvent))).scalars().all()
            event_ids = {e.id for e in events}
            assert audit_x_id not in event_ids
            assert audit_y_id in event_ids
