"""arq worker configuration and task definitions.

Run locally with: `uv run arq docsgraph_server.jobs.worker.WorkerSettings`
"""

import logging
from collections.abc import Callable
from typing import Any, ClassVar
from uuid import UUID

from arq.connections import RedisSettings
from sqlalchemy import select

from docsgraph_server.core.config import get_settings
from docsgraph_server.db.models import DbDocument
from docsgraph_server.db.session import get_sessionmaker
from docsgraph_server.indexing.engine import DatabaseIndexEngine
from docsgraph_server.ocr.engine import TesseractOcrEngine

logger = logging.getLogger("docsgraph_server.jobs")


async def ping(_ctx: dict[str, Any]) -> str:
    """Placeholder task used to verify the worker can execute jobs."""
    return "pong"


async def process_document(_ctx: dict[str, Any], document_id: UUID) -> None:
    """Background task to run OCR and index an uploaded document."""
    session_factory = get_sessionmaker()

    # 1. Update status to "processing"
    async with session_factory() as session:
        result = await session.execute(select(DbDocument).where(DbDocument.id == document_id))
        db_doc = result.scalar_one_or_none()
        if not db_doc:
            logger.error("Document %s not found for processing", document_id)
            return

        db_doc.status = "processing"
        await session.commit()

    # 2. Extract text and index content (wrapped in try-except to handle failures safely)
    async with session_factory() as session:
        result = await session.execute(select(DbDocument).where(DbDocument.id == document_id))
        db_doc = result.scalar_one()

        try:
            # Check if document requires OCR processing (image types)
            is_image = db_doc.file_type.startswith("image/") or db_doc.file_name.lower().endswith(
                (".png", ".jpg", ".jpeg", ".tiff", ".bmp")
            )

            if is_image:
                ocr = TesseractOcrEngine()
                ocr_result = ocr.extract_text(db_doc.file_content)
                db_doc.extracted_text = ocr_result.text
            else:
                try:
                    db_doc.extracted_text = db_doc.file_content.decode("utf-8")
                except UnicodeDecodeError:
                    db_doc.extracted_text = db_doc.file_content.decode("latin-1", errors="ignore")

            # Index document content
            indexer = DatabaseIndexEngine()
            await indexer.index_document(db_doc.id, db_doc.extracted_text or "")

            db_doc.status = "completed"
            db_doc.error_message = None
        except Exception as e:
            logger.exception("Failed to process document %s", document_id)
            db_doc.status = "failed"
            db_doc.error_message = str(e)

        await session.commit()


async def startup(ctx: dict[str, Any]) -> None:
    """Run once when the worker process starts."""
    pass


async def shutdown(ctx: dict[str, Any]) -> None:
    """Run once when the worker process stops."""
    pass


class WorkerSettings:
    """arq worker configuration, discovered by the `arq` CLI."""

    functions: ClassVar[list[Callable[..., Any]]] = [ping, process_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
