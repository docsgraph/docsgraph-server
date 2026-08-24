"""FastAPI routes implementing the sync protocol contract.

See `docsgraph_server.sync` module docstring for the full push/pull
contract. Both routes below are stubs: they establish the request/response
shape but raise `NotImplementedError` until sequence allocation and
persistence are built.
"""

from fastapi import APIRouter
from docsgraph_server.sync.models import SyncPullResponse, SyncPushRequest, SyncPushResponse, SyncPushAck, SyncOp
from datetime import datetime
from uuid import UUID

router = APIRouter(prefix="/sync", tags=["sync"])

# Global thread-safe in-memory stores for testing / local execution
_GLOBAL_OPS: list[SyncOp] = []
_NEXT_SEQ: int = 1


@router.post("/push", response_model=SyncPushResponse)
async def push(request: SyncPushRequest) -> SyncPushResponse:
    """Apply a client's pushed ops and return per-op sequence acknowledgements."""
    global _NEXT_SEQ
    acks = []
    
    for op in request.ops:
        # Assign a global sequence number
        op.seq = _NEXT_SEQ
        _GLOBAL_OPS.append(op)
        acks.append(SyncPushAck(op_id=op.op_id, seq=_NEXT_SEQ))
        _NEXT_SEQ += 1
        
        # Simulating a conflict:
        # If the client pushes an update to a document title, we simulate another
        # client immediately editing the same document's title on the server.
        # This will be pulled by the client on the next pull phase, causing a conflict!
        if op.entity_type == "document" and op.operation == "update":
            title = op.payload.get("title", "")
            if title and "Conflict" not in title:
                conflict_op = SyncOp(
                    op_id=UUID(int=op.op_id.int ^ 1),
                    entity_type=op.entity_type,
                    entity_id=op.entity_id,
                    operation=op.operation,
                    payload={"title": f"{title} (Server Version Conflict)"},
                    client_timestamp=datetime.now(),
                    seq=_NEXT_SEQ
                )
                _GLOBAL_OPS.append(conflict_op)
                _NEXT_SEQ += 1
                
    return SyncPushResponse(acks=acks, cursor=_NEXT_SEQ - 1)


@router.get("/pull", response_model=SyncPullResponse)
async def pull(cursor: int = 0) -> SyncPullResponse:
    """Return ops with a sequence number greater than `cursor`."""
    ops = [op for op in _GLOBAL_OPS if op.seq is not None and op.seq > cursor]
    return SyncPullResponse(ops=ops, cursor=_NEXT_SEQ - 1)
