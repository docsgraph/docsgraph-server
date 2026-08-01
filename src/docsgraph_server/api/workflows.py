"""Workflow/automation API routes.

This is a scaffold: the single endpoint below exists to establish the
route shape. The actual workflow engine lives in
`docsgraph_server.workflows`.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("")
async def list_workflows() -> dict[str, list[str]]:
    """Placeholder listing endpoint; returns an empty result set."""
    return {"workflows": []}
