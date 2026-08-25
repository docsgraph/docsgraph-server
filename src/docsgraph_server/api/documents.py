"""Document management API routes."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbDocument
from docsgraph_server.db.session import get_session

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentCreate(BaseModel):
    """Pydantic model for document creation."""

    id: UUID | None = None
    title: str


class DocumentResponse(BaseModel):
    """Pydantic model for document responses."""

    id: UUID
    title: str

    model_config = {"from_attributes": True}


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    doc: DocumentCreate,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbDocument:
    """Create a new document."""
    doc_id = doc.id or uuid4()
    db_doc = DbDocument(id=doc_id, title=doc.title)
    db.add(db_doc)
    await db.commit()
    await db.refresh(db_doc)
    return db_doc
