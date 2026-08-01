"""Search/embedding indexing interface.

Defines the contract used to index document content for full-text search
and semantic (embedding-based) retrieval. No concrete backend is chosen
yet; this module scaffolds the interface only.
"""

from typing import Protocol
from uuid import UUID


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
