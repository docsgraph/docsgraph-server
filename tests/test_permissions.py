import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from docsgraph_server.db.session import get_engine
from docsgraph_server.main import create_app
from docsgraph_server.sync import router as sync_router


@pytest.fixture(autouse=True)
async def cleanup_db() -> AsyncGenerator[None, None]:
    """Clean up permissions and documents tables and reset sync globals."""
    get_engine.cache_clear()
    # Reset in-memory sync operations
    sync_router._GLOBAL_OPS.clear()
    sync_router._NEXT_SEQ = 1

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM acls"))
        await conn.execute(text("DELETE FROM group_memberships"))
        await conn.execute(text("DELETE FROM documents"))
        await conn.execute(text("DELETE FROM users"))
        await conn.execute(text("DELETE FROM groups"))
        await conn.execute(text("DELETE FROM collections"))

    yield

    await engine.dispose()
    get_engine.cache_clear()


@pytest.mark.integration
async def test_permissions_model_enforcement() -> None:
    """End-to-end verification of the permissions model."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Define users (admin, user1, user2)
        admin_id = uuid.uuid4()
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()

        await client.post(
            "/api/v1/permissions/users",
            json={"id": str(admin_id), "username": "admin_user", "role": "admin"},
        )
        await client.post(
            "/api/v1/permissions/users",
            json={"id": str(user1_id), "username": "user_one", "role": "user"},
        )
        await client.post(
            "/api/v1/permissions/users",
            json={"id": str(user2_id), "username": "user_two", "role": "user"},
        )

        # 2. Define groups (group1) and add user1 to it
        group1_id = uuid.uuid4()
        await client.post(
            "/api/v1/permissions/groups",
            json={"id": str(group1_id), "name": "finance_team"},
        )
        await client.post(
            f"/api/v1/permissions/groups/{group1_id}/members",
            json={"user_id": str(user1_id)},
        )

        # 3. Create a collection (collection1) and assign group1 write access to it
        collection1_id = uuid.uuid4()
        await client.post(
            "/api/v1/permissions/collections",
            json={"id": str(collection1_id), "name": "Finance Docs"},
        )
        await client.post(
            "/api/v1/permissions/acls",
            json={
                "subject_id": str(group1_id),
                "resource_id": str(collection1_id),
                "resource_type": "collection",
                "action": "write",
            },
        )
        # Also give group1 read access to collection1
        await client.post(
            "/api/v1/permissions/acls",
            json={
                "subject_id": str(group1_id),
                "resource_id": str(collection1_id),
                "resource_type": "collection",
                "action": "read",
            },
        )

        # 4. Enforce Document creation access check (POST /documents)
        # user1 (via group1 write access on collection1) should be allowed to
        # create a document in collection1.
        doc_id = uuid.uuid4()
        response = await client.post(
            "/api/v1/documents",
            headers={"X-User-Id": str(user1_id)},
            json={
                "id": str(doc_id),
                "title": "Q3 Report",
                "collection_id": str(collection1_id),
            },
        )
        assert response.status_code == 201

        # user2 (who does not have write access on collection1) should get 403 Forbidden
        other_doc_id = uuid.uuid4()
        response = await client.post(
            "/api/v1/documents",
            headers={"X-User-Id": str(user2_id)},
            json={
                "id": str(other_doc_id),
                "title": "Secret Hack",
                "collection_id": str(collection1_id),
            },
        )
        assert response.status_code == 403

        # 5. Enforce Document read access check (GET /documents/{id})
        # user1 should be allowed to read Q3 Report because of collection-level read access
        response = await client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"X-User-Id": str(user1_id)},
        )
        assert response.status_code == 200

        # user2 should be forbidden from reading Q3 Report since they have no access
        response = await client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"X-User-Id": str(user2_id)},
        )
        assert response.status_code == 403

        # Define a document-level read ACL for user2 on Q3 Report
        await client.post(
            "/api/v1/permissions/acls",
            json={
                "subject_id": str(user2_id),
                "resource_id": str(doc_id),
                "resource_type": "document",
                "action": "read",
            },
        )
        # Now user2 should be allowed to read Q3 Report
        response = await client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"X-User-Id": str(user2_id)},
        )
        assert response.status_code == 200

        # 6. Verify listing documents filters out forbidden items
        # Let's create another document outside of collection1 that user1 cannot read
        doc2_id = uuid.uuid4()
        # Admin can bypass and create it
        response = await client.post(
            "/api/v1/documents",
            headers={"X-User-Id": str(admin_id)},
            json={
                "id": str(doc2_id),
                "title": "Admin Confidential",
            },
        )
        assert response.status_code == 201

        # user1 lists documents - should only see Q3 Report (doc_id),
        # NOT Admin Confidential (doc2_id).
        response = await client.get(
            "/api/v1/documents",
            headers={"X-User-Id": str(user1_id)},
        )
        assert response.status_code == 200
        docs_list = response.json()
        assert len(docs_list) == 1
        assert docs_list[0]["id"] == str(doc_id)

        # 7. Enforce permissions on sync operations (push/pull)
        # user2 tries to push a write/update op to doc2 (Admin Confidential) -> 403 Forbidden
        response = await client.post(
            "/api/v1/sync/push",
            headers={"X-User-Id": str(user2_id)},
            json={
                "client_id": str(uuid.uuid4()),
                "cursor": 0,
                "ops": [
                    {
                        "op_id": str(uuid.uuid4()),
                        "entity_type": "document",
                        "entity_id": str(doc2_id),
                        "operation": "update",
                        "payload": {"title": "Hacked Title"},
                        "client_timestamp": "2026-08-25T12:00:00Z",
                    }
                ],
            },
        )
        assert response.status_code == 403

        # Give user1 write ACL on doc_id (Q3 Report)
        await client.post(
            "/api/v1/permissions/acls",
            json={
                "subject_id": str(user1_id),
                "resource_id": str(doc_id),
                "resource_type": "document",
                "action": "write",
            },
        )

        # user1 pushes a write/update op to doc_id (Q3 Report) -> 200 OK
        op1_id = uuid.uuid4()
        response = await client.post(
            "/api/v1/sync/push",
            headers={"X-User-Id": str(user1_id)},
            json={
                "client_id": str(uuid.uuid4()),
                "cursor": 0,
                "ops": [
                    {
                        "op_id": str(op1_id),
                        "entity_type": "document",
                        "entity_id": str(doc_id),
                        "operation": "update",
                        "payload": {"title": "Q3 Report Final"},
                        "client_timestamp": "2026-08-25T12:00:00Z",
                    }
                ],
            },
        )
        assert response.status_code == 200

        # Admin pushes a write/update op to doc2_id (Admin Confidential) -> 200 OK
        op2_id = uuid.uuid4()
        response = await client.post(
            "/api/v1/sync/push",
            headers={"X-User-Id": str(admin_id)},
            json={
                "client_id": str(uuid.uuid4()),
                "cursor": 0,
                "ops": [
                    {
                        "op_id": str(op2_id),
                        "entity_type": "document",
                        "entity_id": str(doc2_id),
                        "operation": "update",
                        "payload": {"title": "Admin Confidential V2"},
                        "client_timestamp": "2026-08-25T12:05:00Z",
                    }
                ],
            },
        )
        assert response.status_code == 200

        # 8. Sync pull delivers only changes the requesting user is permitted to see
        # user1 pulls -> should see op1_id on doc_id (they have read access to collection1),
        # but NOT see op2_id on doc2_id (no read access to doc2_id)
        response = await client.get(
            "/api/v1/sync/pull?cursor=0",
            headers={"X-User-Id": str(user1_id)},
        )
        assert response.status_code == 200
        pull_ops = response.json()["ops"]
        # Filters to only include doc_id operations
        entity_ids = [op["entity_id"] for op in pull_ops]
        assert str(doc_id) in entity_ids
        assert str(doc2_id) not in entity_ids

        # Admin pulls -> should see both
        response = await client.get(
            "/api/v1/sync/pull?cursor=0",
            headers={"X-User-Id": str(admin_id)},
        )
        assert response.status_code == 200
        admin_pull_ops = response.json()["ops"]
        admin_entity_ids = [op["entity_id"] for op in admin_pull_ops]
        assert str(doc_id) in admin_entity_ids
        assert str(doc2_id) in admin_entity_ids
