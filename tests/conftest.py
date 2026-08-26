"""Configuration for pytest test session."""

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def run_migrations() -> None:
    """Automatically apply migrations before running the integration test suite."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
