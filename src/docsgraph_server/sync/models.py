"""Pydantic models for the sync push/pull protocol.

See `docsgraph_server.sync` module docstring for the full contract.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SyncOperationType(StrEnum):
    """The kind of change a sync op represents."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class SyncOp(BaseModel):
    """A single change made by a client, pushed to or pulled from the server."""

    op_id: UUID = Field(description="Client-generated idempotency key for this op.")
    entity_type: str = Field(description="Domain entity the op applies to, e.g. 'document'.")
    entity_id: UUID = Field(description="Identifier of the affected entity.")
    operation: SyncOperationType
    payload: dict[str, Any] = Field(default_factory=dict, description="Entity fields changed.")
    client_timestamp: datetime = Field(description="When the client recorded this op locally.")
    seq: int | None = Field(
        default=None,
        description="Global sequence number assigned by the server. Absent on push.",
    )


class SyncPushRequest(BaseModel):
    """A client's request to push a batch of local ops since its last cursor."""

    client_id: UUID = Field(description="Identifier of the pushing client/device.")
    cursor: int = Field(ge=0, description="Highest sequence number this client has already seen.")
    ops: list[SyncOp] = Field(default_factory=list, description="Ordered ops to apply.")


class SyncPushAck(BaseModel):
    """Server acknowledgement of a single pushed op."""

    op_id: UUID
    seq: int


class SyncPushResponse(BaseModel):
    """Server response to a push: per-op acks plus the client's new cursor."""

    acks: list[SyncPushAck] = Field(default_factory=list)
    cursor: int = Field(ge=0, description="New cursor value the client should persist.")


class SyncPullResponse(BaseModel):
    """Server response to a pull: ops newer than the client's cursor."""

    ops: list[SyncOp] = Field(default_factory=list)
    cursor: int = Field(ge=0, description="New cursor value the client should persist.")
