# docsgraph-server External Integrations Framework

The integrations framework enables `docsgraph-server` to connect with third-party external services (such as cloud storage, single sign-on, and event notifier channels) without modifying core server logic.

---

## 1. Core Interfaces

All integrations must conform to the `Integration` protocol:

```python
from typing import Any, Protocol


class Integration(Protocol):
    def get_id(self) -> str:
        """Return the unique string identifier for the integration (e.g. 'webhook_notifier')."""
        ...

    def get_name(self) -> str:
        """Return a user-friendly name for configuration UIs."""
        ...

    def configure(self, config: dict[str, Any]) -> None:
        """Apply a dynamic configuration dictionary containing options and credentials."""
        ...

    def is_enabled(self) -> bool:
        """Return whether the integration is configured and active."""
        ...

    async def execute(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Perform the integration execution on a dispatched event."""
        ...
```

---

## 2. Reference Implementation: Webhook Event Notifier

The `WebhookNotifierIntegration` is pre-registered and provides a secure push mechanism for external systems.

### Features
- **HMAC Signatures**: Supports payload authentication. When `secret_key` is supplied, payloads are signed via HMAC-SHA256 and sent in the `X-Docsgraph-Signature` HTTP header.
- **Async Execution**: Non-blocking network I/O powered by `httpx.AsyncClient`.

---

## 3. Configuration & Database Mapping
Integrations are configured at runtime (without changing core code or rebooting the server) via database records in the `integration_configs` table:

- `id` (PK): The unique integration ID matching `get_id()`.
- `enabled`: Global toggle to enable/disable.
- `config_json`: JSON object containing connection parameters, credentials, or URLs.

API routes under `/api/v1/integrations` allow listing, configuring, and testing integrations.

---

## 4. Failure Isolation & Graceful Degradation
To prevent failing external integrations from blocking or breaking core operations, all execution dispatches are isolated. The `IntegrationManager` catches exceptions on execution, logs them, and returns an outcome status without propagation.
