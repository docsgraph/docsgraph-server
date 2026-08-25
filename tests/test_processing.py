import uuid
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from docsgraph_server.db.models import DbDocument
from docsgraph_server.db.session import get_engine, get_sessionmaker
from docsgraph_server.jobs.worker import process_document
from docsgraph_server.main import create_app


@pytest.fixture(autouse=True)
async def cleanup_db() -> AsyncGenerator[None, None]:
    """Ensure the documents table is empty before each test run and reset the engine."""
    get_engine.cache_clear()

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM documents"))

    yield

    await engine.dispose()
    get_engine.cache_clear()


@pytest.mark.integration
async def test_upload_and_process_text_document() -> None:
    """Verify that uploading a text document processes and indexes it successfully."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Upload the text document
        file_data = b"Hello world! This is a test document with unique keywords like antigravity."
        response = await client.post(
            "/api/v1/documents",
            data={"title": "Test Text Doc"},
            files={"file": ("test.txt", file_data, "text/plain")},
        )
        assert response.status_code == 201
        doc_data = response.json()
        doc_id = uuid.UUID(doc_data["id"])
        assert doc_data["status"] == "pending"

        # 2. Trigger the background process task directly
        await process_document({}, doc_id)

        # 3. Query the document status
        status_response = await client.get(f"/api/v1/documents/{doc_id}/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "completed"
        assert status_data["error_message"] is None

        # 4. Search for the document
        search_response = await client.get("/api/v1/documents/search?query=antigravity")
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert len(search_data) == 1
        assert search_data[0]["id"] == str(doc_id)
        assert "antigravity" in search_data[0]["extracted_text"]


@pytest.mark.integration
async def test_upload_and_process_image_document() -> None:
    """Verify that uploading an image runs OCR and extracts text."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Upload the image document
        image_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        response = await client.post(
            "/api/v1/documents",
            data={"title": "Scanned Invoice"},
            files={"file": ("invoice.png", image_data, "image/png")},
        )
        assert response.status_code == 201
        doc_data = response.json()
        doc_id = uuid.UUID(doc_data["id"])

        # 2. Process
        await process_document({}, doc_id)

        # 3. Verify detail status and text
        detail_response = await client.get(f"/api/v1/documents/{doc_id}")
        assert detail_response.status_code == 200
        detail_data = detail_response.json()
        assert detail_data["status"] == "completed"
        assert "Simulated Tesseract OCR Text" in detail_data["extracted_text"]


@pytest.mark.integration
async def test_processing_failure_handling() -> None:
    """Verify that failures during processing do not lose the source document."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Upload a document
        file_data = b"Testing error fallback."
        response = await client.post(
            "/api/v1/documents",
            data={"title": "Error Doc"},
            files={"file": ("error.txt", file_data, "text/plain")},
        )
        assert response.status_code == 201
        doc_id = uuid.UUID(response.json()["id"])

        # 2. Mock indexer to throw an error during process
        with patch(
            "docsgraph_server.indexing.engine.DatabaseIndexEngine.index_document",
            side_effect=Exception("Database Indexing Timeout"),
        ):
            await process_document({}, doc_id)

        # 3. Check status is failed and error message is populated
        status_response = await client.get(f"/api/v1/documents/{doc_id}/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "failed"
        assert "Database Indexing Timeout" in status_data["error_message"]

        # 4. Check the source document content is still preserved in the database
        session_factory = get_sessionmaker()
        async with session_factory() as session:
            result = await session.execute(select(DbDocument).where(DbDocument.id == doc_id))
            db_doc = result.scalar_one()
            assert db_doc.file_content == file_data


@pytest.mark.integration
async def test_document_not_found() -> None:
    """Verify detail and status endpoints return 404 for missing documents."""
    app = create_app()
    transport = ASGITransport(app=app)
    missing_id = uuid.uuid4()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Detail endpoint
        response = await client.get(f"/api/v1/documents/{missing_id}")
        assert response.status_code == 404

        # Status endpoint
        response = await client.get(f"/api/v1/documents/{missing_id}/status")
        assert response.status_code == 404
