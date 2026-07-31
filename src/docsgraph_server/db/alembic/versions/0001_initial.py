"""initial (empty baseline).

Revision ID: 0001
Revises:
Create Date: 2026-07-31
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op baseline migration; no model tables defined yet."""


def downgrade() -> None:
    """No-op baseline migration; no model tables defined yet."""
