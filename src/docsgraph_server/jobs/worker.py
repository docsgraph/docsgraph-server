"""arq worker configuration and task definitions.

Run locally with: `uv run arq docsgraph_server.jobs.worker.WorkerSettings`

Real background tasks (OCR extraction, indexing, retention sweeps, ...)
will be registered in `WorkerSettings.functions` as those modules are
implemented. `ping` exists only to verify the worker wiring end-to-end.
"""

from collections.abc import Callable
from typing import Any, ClassVar

from arq.connections import RedisSettings

from docsgraph_server.core.config import get_settings


async def ping(_ctx: dict[str, Any]) -> str:
    """Placeholder task used to verify the worker can execute jobs."""
    return "pong"


async def startup(ctx: dict[str, Any]) -> None:
    """Run once when the worker process starts."""


async def shutdown(ctx: dict[str, Any]) -> None:
    """Run once when the worker process stops."""


class WorkerSettings:
    """arq worker configuration, discovered by the `arq` CLI."""

    functions: ClassVar[list[Callable[..., Any]]] = [ping]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
