"""External integrations framework and reference implementation.

Defines the contract for external integrations and a manager to dynamically
configure, execute, and gracefully handle integration outcomes.
"""

import hmac
import json
import logging
from hashlib import sha256
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docsgraph_server.db.models import DbIntegrationConfig

logger = logging.getLogger(__name__)


class Integration(Protocol):
    """Protocol defining the contract for all external integrations."""

    def get_id(self) -> str:
        """Return the unique identifier for the integration."""
        ...

    def get_name(self) -> str:
        """Return a human-readable name for the integration."""
        ...

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the integration using a configuration dictionary."""
        ...

    def is_enabled(self) -> bool:
        """Return whether the integration is active and enabled."""
        ...

    async def execute(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute the integration against a dispatched event."""
        ...


class WebhookNotifierIntegration:
    """Reference implementation sending HMAC-signed webhooks to external servers."""

    def __init__(self) -> None:
        """Initialize the integration with default config."""
        self._enabled = False
        self.webhook_url = ""
        self.secret_key = ""

    def get_id(self) -> str:
        """Return unique ID."""
        return "webhook_notifier"

    def get_name(self) -> str:
        """Return friendly name."""
        return "Webhook Event Notifier"

    def configure(self, config: dict[str, Any]) -> None:
        """Configure webhook URL and optional signature secret."""
        self._enabled = bool(config.get("enabled", False))
        self.webhook_url = config.get("webhook_url", "")
        self.secret_key = config.get("secret_key", "")

    def is_enabled(self) -> bool:
        """Return enabled status."""
        return self._enabled and bool(self.webhook_url)

    async def execute(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Post the event payload to the webhook with optional HMAC signature headers."""
        if not self.is_enabled():
            return {"status": "skipped", "reason": "disabled"}

        body = {
            "event_type": event_type,
            "payload": payload,
        }
        headers = {"Content-Type": "application/json"}

        # Compute HMAC signature if secret key is present
        if self.secret_key:
            serialized = json.dumps(body, sort_keys=True).encode("utf-8")
            signature = hmac.new(self.secret_key.encode("utf-8"), serialized, sha256).hexdigest()
            headers["X-Docsgraph-Signature"] = signature

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(self.webhook_url, json=body, headers=headers)
            response.raise_for_status()
            return {
                "status": "success",
                "status_code": response.status_code,
                "response": response.text,
            }


class IntegrationManager:
    """Registry and lifecycle manager for all external integrations."""

    def __init__(self) -> None:
        """Initialize manager and register core integrations."""
        self.registry: dict[str, Integration] = {}
        # Auto-register reference integration
        self.register(WebhookNotifierIntegration())

    def register(self, integration: Integration) -> None:
        """Register an integration instance in the registry."""
        self.registry[integration.get_id()] = integration

    async def load_configurations(self, db: AsyncSession) -> None:
        """Load enabled/disabled state and parameters from database."""
        result = await db.execute(select(DbIntegrationConfig))
        configs = result.scalars().all()

        # Reset all to disabled first, or apply default
        for integration in self.registry.values():
            integration.configure({"enabled": False})

        for cfg in configs:
            if cfg.id in self.registry:
                # Merge DB enabled state into config
                cfg_data = dict(cfg.config_json)
                cfg_data["enabled"] = cfg.enabled
                self.registry[cfg.id].configure(cfg_data)

    async def dispatch(self, event_type: str, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Dispatch an event to all enabled integrations, isolating failures."""
        outcomes = {}
        for integration_id, integration in self.registry.items():
            if not integration.is_enabled():
                continue

            try:
                result = await integration.execute(event_type, payload)
                outcomes[integration_id] = result
            except Exception as e:
                # Graceful degradation: capture failure without throwing up to core caller
                logger.error(
                    "Integration '%s' failed on event '%s': %s",
                    integration_id,
                    event_type,
                    str(e),
                    exc_info=True,
                )
                outcomes[integration_id] = {
                    "status": "failed",
                    "error": str(e),
                }
        return outcomes
