"""Document management API routes (upload, metadata, versions)."""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.audit.logger import DatabaseAuditLogger
from docsgraph_server.db.models import DbCollection, DbDocument
from docsgraph_server.db.session import get_session

router = APIRouter(prefix="/documents", tags=["documents"])


class CollectionCreate(BaseModel):
    """Pydantic model for creating a collection."""

    id: UUID | None = None
    name: str


class CollectionResponse(BaseModel):
    """Pydantic model for collection responses."""

    id: UUID
    name: str

    model_config = {"from_attributes": True}


class DocumentCreate(BaseModel):
    """Pydantic model for creating a document."""

    id: UUID | None = None
    title: str
    collection_id: UUID | None = None
    legal_hold: bool = False
    actor_id: UUID


class DocumentResponse(BaseModel):
    """Pydantic model for document responses."""

    id: UUID
    title: str
    collection_id: UUID | None
    created_at: datetime
    legal_hold: bool

    model_config = {"from_attributes": True}


@router.post("/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    col: CollectionCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbCollection:
    """Create a new document collection."""
    col_id = col.id or uuid4()
    db_col = DbCollection(id=col_id, name=col.name)
    db.add(db_col)
    await db.commit()
    await db.refresh(db_col)
    return db_col


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    doc: DocumentCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbDocument:
    """Create a new document and log a creation audit event."""
    doc_id = doc.id or uuid4()
    db_doc = DbDocument(
        id=doc_id,
        title=doc.title,
        collection_id=doc.collection_id,
        legal_hold=doc.legal_hold,
    )
    db.add(db_doc)

    logger = DatabaseAuditLogger(db)
    await logger.record_event(
        actor_id=doc.actor_id,
        action="document.create",
        resource_id=doc_id,
        metadata={
            "title": doc.title,
            "collection_id": str(doc.collection_id) if doc.collection_id else None,
        },
    )
    await db.refresh(db_doc)
    return db_doc


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    actor_id: UUID,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbDocument:
    """Retrieve a document and log a read audit event."""
    result = await db.execute(select(DbDocument).where(DbDocument.id == document_id))
    db_doc = result.scalar_one_or_none()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    logger = DatabaseAuditLogger(db)
    await logger.record_event(
        actor_id=actor_id,
        action="document.read",
        resource_id=document_id,
        metadata={"title": db_doc.title},
    )
    return db_doc


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[DbDocument]:
    """List all documents."""
    result = await db.execute(select(DbDocument))
    return list(result.scalars().all())
