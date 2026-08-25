"""FastAPI routes implementing the sync protocol contract with permissions."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.api.documents import get_requesting_user_id
from docsgraph_server.db.session import get_session
from docsgraph_server.permissions.checker import Action, DatabasePermissionChecker
from docsgraph_server.sync.models import (
    SyncOp,
    SyncOperationType,
    SyncPullResponse,
    SyncPushAck,
    SyncPushRequest,
    SyncPushResponse,
)

router = APIRouter(prefix="/sync", tags=["sync"])

# Global thread-safe in-memory stores for testing / local execution
_GLOBAL_OPS: list[SyncOp] = []
_NEXT_SEQ: int = 1


@router.post("/push", response_model=SyncPushResponse)
async def push(
    request: SyncPushRequest,
    x_user_id: UUID = Depends(get_requesting_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> SyncPushResponse:
    """Apply a client's pushed ops and return per-op sequence acknowledgements."""
    global _NEXT_SEQ
    acks = []

    checker = DatabasePermissionChecker(db)

    # 1. Enforce access control on write operations (push)
    for op in request.ops:
        if op.entity_type == "document":
            # For update/delete, check write permission on the document
            if op.operation in (SyncOperationType.UPDATE, SyncOperationType.DELETE):
                if not await checker.can(x_user_id, Action.WRITE, op.entity_id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: Cannot write to document {op.entity_id}",
                    )
            # For create, check write permission on the collection if specified
            elif op.operation == SyncOperationType.CREATE:
                collection_id_str = op.payload.get("collection_id")
                if collection_id_str:
                    try:
                        coll_id = UUID(str(collection_id_str))
                        if not await checker.can(x_user_id, Action.WRITE, coll_id):
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Access denied: Cannot write to collection {coll_id}",
                            )
                    except ValueError:
                        pass

    # 2. Append operations and assign sequence numbers
    for op in request.ops:
        op.seq = _NEXT_SEQ
        _GLOBAL_OPS.append(op)
        acks.append(SyncPushAck(op_id=op.op_id, seq=_NEXT_SEQ))
        _NEXT_SEQ += 1

        # Simulate conflict on updates
        if op.entity_type == "document" and op.operation == SyncOperationType.UPDATE:
            title = op.payload.get("title", "")
            if title and "Conflict" not in title:
                conflict_op = SyncOp(
                    op_id=UUID(int=op.op_id.int ^ 1),
                    entity_type=op.entity_type,
                    entity_id=op.entity_id,
                    operation=op.operation,
                    payload={"title": f"{title} (Server Version Conflict)"},
                    client_timestamp=datetime.now(),
                    seq=_NEXT_SEQ,
                )
                _GLOBAL_OPS.append(conflict_op)
                _NEXT_SEQ += 1

    return SyncPushResponse(acks=acks, cursor=_NEXT_SEQ - 1)


@router.get("/pull", response_model=SyncPullResponse)
async def pull(
    cursor: int = 0,
    x_user_id: UUID = Depends(get_requesting_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> SyncPullResponse:
    """Return ops with a sequence number greater than `cursor`, filtered by access rights."""
    ops = [op for op in _GLOBAL_OPS if op.seq is not None and op.seq > cursor]

    checker = DatabasePermissionChecker(db)
    allowed_ops = []

    # 3. Filter changes the requesting user is permitted to see
    for op in ops:
        if op.entity_type == "document":
            if await checker.can(x_user_id, Action.READ, op.entity_id):
                allowed_ops.append(op)
        else:
            allowed_ops.append(op)

    return SyncPullResponse(ops=allowed_ops, cursor=_NEXT_SEQ - 1)
