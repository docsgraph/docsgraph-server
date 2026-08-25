"""Search/embedding indexing interface.

Defines the contract used to index document content for full-text search
and semantic (embedding-based) retrieval.
"""

from typing import Protocol
from uuid import UUID

from sqlalchemy import select

from docsgraph_server.db.models import DbDocument
from docsgraph_server.db.session import get_sessionmaker


class IndexEngine(Protocol):
    """Interface implemented by indexing backends."""

    async def index_document(self, document_id: UUID, text: str) -> None:
        """Index or re-index a document's extracted text content."""
        ...

    async def remove_document(self, document_id: UUID) -> None:
        """Remove a document from the index."""
        ...

    async def search(self, query: str, limit: int = 20) -> list[UUID]:
        """Return document IDs matching `query`, best matches first."""
        ...


class DatabaseIndexEngine:
    """SQLAlchemy-backed index engine using Full-Text / ILIKE search."""

    async def index_document(self, document_id: UUID, text: str) -> None:
        """No-op because the document's extracted text is stored directly on the DbDocument."""
        pass

    async def remove_document(self, document_id: UUID) -> None:
        """No-op because deleting the document from the database automatically removes it."""
        pass

    async def search(self, query: str, limit: int = 20) -> list[UUID]:
        """Return document IDs matching `query`."""
        session_factory = get_sessionmaker()
        async with session_factory() as session:
            result = await session.execute(
                select(DbDocument.id)
                .where(DbDocument.extracted_text.ilike(f"%{query}%"))
                .limit(limit)
            )
            return list(result.scalars().all())
