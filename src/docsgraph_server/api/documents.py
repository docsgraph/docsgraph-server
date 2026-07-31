"""Document management API routes (upload, metadata, versions).

This is a scaffold: the single endpoint below exists to establish the
route shape. Real document storage, versioning, and processing hooks
land in follow-up work.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents() -> dict[str, list[str]]:
    """Placeholder listing endpoint; returns an empty result set."""
    return {"documents": []}
