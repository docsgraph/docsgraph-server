"""Document management API routes (upload, metadata, search)."""

import uuid
from datetime import datetime
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.core.config import get_settings
from docsgraph_server.db.models import DbDocument
from docsgraph_server.db.session import get_session
from docsgraph_server.indexing.engine import DatabaseIndexEngine

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    """Pydantic model representing document metadata response."""

    id: UUID
    title: str
    file_name: str
    file_type: str
    status: str
    extracted_text: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    """Pydantic model representing document processing status."""

    id: UUID
    status: str
    error_message: str | None = None

    model_config = {"from_attributes": True}


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    title: str = Form(...),
    file: UploadFile = File(...),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbDocument:
    """Upload a new document and enqueue it for background OCR/indexing."""
    doc_id = uuid.uuid4()
    content = await file.read()

    db_doc = DbDocument(
        id=doc_id,
        title=title,
        file_name=file.filename or "unknown",
        file_type=file.content_type or "application/octet-stream",
        file_content=content,
        status="pending",
    )
    db.add(db_doc)
    await db.commit()

    # Enqueue background processing job via arq Redis queue
    try:
        settings = get_settings()
        redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis_pool.enqueue_job("process_document", doc_id)
        await redis_pool.aclose()
    except Exception as e:
        # Log error, but don't fail upload since raw file is safely persisted (acceptance criteria)
        import logging

        logger = logging.getLogger("docsgraph_server.api")
        logger.error("Failed to enqueue background processing for document %s: %s", doc_id, e)

    await db.refresh(db_doc)
    return db_doc


@router.get("/search", response_model=list[DocumentResponse])
async def search_documents(
    query: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[DbDocument]:
    """Search for documents containing the specified query text."""
    indexer = DatabaseIndexEngine()
    matching_ids = await indexer.search(query, limit=limit)

    if not matching_ids:
        return []

    result = await db.execute(
        select(DbDocument).where(DbDocument.id.in_(matching_ids)).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbDocument:
    """Retrieve metadata of a specific document."""
    result = await db.execute(select(DbDocument).where(DbDocument.id == document_id))
    db_doc = result.scalar_one_or_none()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return db_doc


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: UUID,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbDocument:
    """Query the processing status of a specific document."""
    result = await db.execute(select(DbDocument).where(DbDocument.id == document_id))
    db_doc = result.scalar_one_or_none()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return db_doc
