"""Permission/ACL management API routes.

This is a scaffold: the single endpoint below exists to establish the
route shape. The actual permission model lives in
`docsgraph_server.permissions`.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("")
async def list_permissions() -> dict[str, list[str]]:
    """Placeholder listing endpoint; returns an empty result set."""
    return {"permissions": []}
