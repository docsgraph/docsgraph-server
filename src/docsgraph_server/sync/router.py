"""FastAPI routes implementing the sync protocol contract.

See `docsgraph_server.sync` module docstring for the full push/pull
contract. Both routes below are stubs: they establish the request/response
shape but raise `NotImplementedError` until sequence allocation and
persistence are built.
"""

from fastapi import APIRouter

from docsgraph_server.sync.models import SyncPullResponse, SyncPushRequest, SyncPushResponse

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/push", response_model=SyncPushResponse)
async def push(request: SyncPushRequest) -> SyncPushResponse:
    """Apply a client's pushed ops and return per-op sequence acknowledgements.

    Intended behavior: within a single transaction, allocate the next
    global sequence number for each op in `request.ops` (in order), apply
    it to the corresponding Postgres row(s), and return one `SyncPushAck`
    per op plus the resulting cursor.
    """
    raise NotImplementedError("sync push is not yet implemented")


@router.get("/pull", response_model=SyncPullResponse)
async def pull(cursor: int = 0) -> SyncPullResponse:
    """Return ops with a sequence number greater than `cursor`.

    Intended behavior: query all ops (from any client) with `seq > cursor`,
    ordered by `seq`, and return them along with the new cursor (the
    highest `seq` included in the response, or `cursor` unchanged if empty).
    """
    raise NotImplementedError("sync pull is not yet implemented")
