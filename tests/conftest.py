import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def run_db_migrations() -> None:
    """Run all Alembic migrations at the start of the test session."""
    config = Config("alembic.ini")
    command.upgrade(config, "head")
