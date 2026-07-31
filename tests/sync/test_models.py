"""Tests for the sync protocol pydantic models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from docsgraph_server.sync.models import (
    SyncOp,
    SyncOperationType,
    SyncPullResponse,
    SyncPushRequest,
)


def _make_op() -> SyncOp:
    return SyncOp(
        op_id=uuid4(),
        entity_type="document",
        entity_id=uuid4(),
        operation=SyncOperationType.CREATE,
        payload={"title": "Example"},
        client_timestamp=datetime.now(UTC),
    )


class TestSyncOp:
    @pytest.mark.unit
    def test_valid_op_round_trips(self) -> None:
        op = _make_op()
        assert op.seq is None
        assert op.operation is SyncOperationType.CREATE

    @pytest.mark.unit
    def test_invalid_operation_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            SyncOp(
                op_id=uuid4(),
                entity_type="document",
                entity_id=uuid4(),
                operation="not-a-real-op",  # type: ignore[arg-type]
                payload={},
                client_timestamp=datetime.now(UTC),
            )


class TestSyncPushRequest:
    @pytest.mark.unit
    def test_accepts_ops_and_cursor(self) -> None:
        request = SyncPushRequest(client_id=uuid4(), cursor=5, ops=[_make_op()])
        assert request.cursor == 5
        assert len(request.ops) == 1

    @pytest.mark.unit
    def test_negative_cursor_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SyncPushRequest(client_id=uuid4(), cursor=-1, ops=[])


class TestSyncPullResponse:
    @pytest.mark.unit
    def test_defaults_to_empty_ops(self) -> None:
        response = SyncPullResponse(cursor=0)
        assert response.ops == []
