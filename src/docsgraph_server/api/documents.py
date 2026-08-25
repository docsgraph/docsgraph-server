"""Document management API routes with permission enforcement."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbDocument
from docsgraph_server.db.session import get_session
from docsgraph_server.permissions.checker import Action, DatabasePermissionChecker

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentCreate(BaseModel):
    """Pydantic model for creating a document."""

    id: UUID | None = None
    title: str
    collection_id: UUID | None = None


class DocumentResponse(BaseModel):
    """Pydantic model for document response data."""

    id: UUID
    title: str
    collection_id: UUID | None

    model_config = {"from_attributes": True}


async def get_requesting_user_id(
    x_user_id: UUID | None = Header(None),  # noqa: B008
) -> UUID:
    """FastAPI dependency to extract the requesting user ID from HTTP headers."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )
    return x_user_id


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    doc: DocumentCreate,
    x_user_id: UUID = Depends(get_requesting_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbDocument:
    """Create a new document, checking collection write permissions if applicable."""
    if doc.collection_id:
        checker = DatabasePermissionChecker(db)
        if not await checker.can(x_user_id, Action.WRITE, doc.collection_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot write to collection",
            )

    doc_id = doc.id or uuid4()
    db_doc = DbDocument(id=doc_id, title=doc.title, collection_id=doc.collection_id)
    db.add(db_doc)
    await db.commit()
    await db.refresh(db_doc)
    return db_doc


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    x_user_id: UUID = Depends(get_requesting_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> DbDocument:
    """Retrieve document details, enforcing read permissions."""
    checker = DatabasePermissionChecker(db)
    if not await checker.can(x_user_id, Action.READ, document_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot read document",
        )

    result = await db.execute(select(DbDocument).where(DbDocument.id == document_id))
    db_doc = result.scalar_one_or_none()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return db_doc


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    x_user_id: UUID = Depends(get_requesting_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[DbDocument]:
    """List documents visible to the requesting user."""
    result = await db.execute(select(DbDocument))
    docs = result.scalars().all()

    checker = DatabasePermissionChecker(db)
    allowed_docs = []
    for doc in docs:
        if await checker.can(x_user_id, Action.READ, doc.id):
            allowed_docs.append(doc)
    return allowed_docs
