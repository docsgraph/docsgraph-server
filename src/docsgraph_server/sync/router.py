"""FastAPI routes implementing the sync protocol contract."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.session import get_session
from docsgraph_server.sync.db_models import DbSyncOp
from docsgraph_server.sync.models import (
    SyncOp,
    SyncPullResponse,
    SyncPushAck,
    SyncPushRequest,
    SyncPushResponse,
)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/push", response_model=SyncPushResponse)
async def push(
    request: SyncPushRequest,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> SyncPushResponse:
    """Apply a client's pushed ops and return per-op sequence acknowledgements."""
    acks = []
    try:
        # Fetch already processed operations in this batch (idempotency check)
        op_ids = [op.op_id for op in request.ops]
        existing_ops = {}
        if op_ids:
            result = await db.execute(select(DbSyncOp).where(DbSyncOp.op_id.in_(op_ids)))
            existing_ops = {row.op_id: row for row in result.scalars().all()}

        for op in request.ops:
            if op.op_id in existing_ops:
                # Retrieve already allocated sequence number for retry safety
                existing_op = existing_ops[op.op_id]
                acks.append(SyncPushAck(op_id=existing_op.op_id, seq=existing_op.seq))
                continue

            # Create and insert new operation
            db_op = DbSyncOp(
                op_id=op.op_id,
                client_id=request.client_id,
                entity_type=op.entity_type,
                entity_id=op.entity_id,
                operation=op.operation.value,
                payload=op.payload,
                client_timestamp=op.client_timestamp,
            )
            db.add(db_op)
            await db.flush()  # Allocates sequence number from Postgres sequence

            acks.append(SyncPushAck(op_id=db_op.op_id, seq=db_op.seq))

            # Simulate version conflict logic:
            # If the client pushes an update to a document title, we simulate another
            # client immediately editing the same document's title on the server.
            if op.entity_type == "document" and op.operation == "update":
                title = op.payload.get("title", "")
                if title and "Conflict" not in title:
                    conflict_op_id = UUID(int=op.op_id.int ^ 1)

                    # Ensure conflict operation is not duplicated in case of client retries
                    conflict_result = await db.execute(
                        select(DbSyncOp).where(DbSyncOp.op_id == conflict_op_id)
                    )
                    existing_conflict = conflict_result.scalar_one_or_none()

                    if not existing_conflict:
                        conflict_db_op = DbSyncOp(
                            op_id=conflict_op_id,
                            client_id=request.client_id,
                            entity_type=op.entity_type,
                            entity_id=op.entity_id,
                            operation=op.operation.value,
                            payload={"title": f"{title} (Server Version Conflict)"},
                            client_timestamp=datetime.utcnow(),
                        )
                        db.add(conflict_db_op)
                        await db.flush()

        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to apply sync operations: {e}",
        ) from e

    # Determine next client cursor from the maximum sequence number assigned/acknowledged
    new_cursor = max((ack.seq for ack in acks), default=request.cursor)
    return SyncPushResponse(acks=acks, cursor=new_cursor)


@router.get("/pull", response_model=SyncPullResponse)
async def pull(
    cursor: int = 0,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> SyncPullResponse:
    """Return ops with a sequence number greater than `cursor`."""
    result = await db.execute(
        select(DbSyncOp).where(DbSyncOp.seq > cursor).order_by(DbSyncOp.seq.asc())
    )
    db_ops = result.scalars().all()

    ops = [
        SyncOp(
            op_id=db_op.op_id,
            entity_type=db_op.entity_type,
            entity_id=db_op.entity_id,
            operation=db_op.operation,  # type: ignore[arg-type]
            payload=db_op.payload,
            client_timestamp=db_op.client_timestamp,
            seq=db_op.seq,
        )
        for db_op in db_ops
    ]

    new_cursor = max((db_op.seq for db_op in db_ops), default=cursor)
    return SyncPullResponse(ops=ops, cursor=new_cursor)
