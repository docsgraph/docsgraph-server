"""Declarative base for all ORM models.

Every SQLAlchemy model in the application should inherit from `Base` so
that Alembic's autogenerate can discover it via `Base.metadata`.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base class for ORM models."""
