"""Workflow/automation engine interface.

Defines the contract used to trigger and advance multi-step document
workflows (approvals, reviews, automated processing pipelines). No
concrete workflow model is chosen yet; this scaffolds the interface only.
"""

from typing import Any, Protocol
from uuid import UUID


class WorkflowEngine(Protocol):
    """Interface implemented by the workflow engine."""

    async def start_workflow(self, workflow_key: str, context: dict[str, Any]) -> UUID:
        """Start a new workflow run and return its instance ID."""
        ...

    async def advance(self, instance_id: UUID, event: str) -> None:
        """Advance a running workflow instance in response to `event`."""
        ...
