"""SQLAlchemy ORM models for external integrations configuration."""

from typing import Any

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from docsgraph_server.db.base import Base


class DbIntegrationConfig(Base):
    """SQLAlchemy model for storing external integration configurations."""

    __tablename__ = "integration_configs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
