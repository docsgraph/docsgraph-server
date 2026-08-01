"""Audit log query API routes.

This is a scaffold: the single endpoint below exists to establish the
route shape. Event recording lives in `docsgraph_server.audit`.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit_events() -> dict[str, list[str]]:
    """Placeholder listing endpoint; returns an empty result set."""
    return {"events": []}
