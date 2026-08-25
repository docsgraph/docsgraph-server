# docsgraph-server

Self-hostable backend for organizations — synchronization, document
processing, OCR, indexing, permissions, collaboration, workflows, audit
logs, retention policies, and external integrations.

Organizations self-host `docsgraph-server` to let their team use the
local-first [`docsgraph`](https://github.com/docsgraph/docsgraph) client
(SQLite-backed, offline-capable) while syncing, collaborating, and
running heavier processing (OCR, indexing) centrally.

## Architecture

- **API**: FastAPI (async).
- **Database**: PostgreSQL, accessed via SQLAlchemy's async engine. This
  server is the source of truth for synchronized state.
- **Sync protocol**: clients keep a local SQLite copy and an ordered
  changelog of offline ops. They push batches of ops to
  `POST /api/v1/sync/push`; the server assigns each a global sequence
  number, applies it to Postgres, and acknowledges it. Clients pull ops
  from other clients newer than their last-seen sequence number via
  `GET /api/v1/sync/pull`. See `src/docsgraph_server/sync/` for the
  documented contract (currently scaffolded, not yet implemented).
- **Migrations**: Alembic, wired to the SQLAlchemy metadata in
  `src/docsgraph_server/db/`.
- **Background jobs**: [arq](https://arq-docs.helpmanual.io/) (async,
  Redis-backed) for OCR, indexing, and other deferred work.
- **Auth**: JWT-based.

## Dev setup

Requires [`uv`](https://docs.astral.sh/uv/) and Docker.

```bash
# Bring up Postgres + Redis for local development
docker compose up -d

# Install dependencies (including dev extras)
uv sync --all-extras --locked

# Copy env defaults (matches docker-compose.yml)
cp .env.example .env

# Apply database migrations
uv run alembic upgrade head

# Run the API with auto-reload
uv run uvicorn docsgraph_server.main:app --reload
```

The API will be available at `http://localhost:8000`, with a liveness
check at `GET /health`.

To run the background job worker:

```bash
uv run arq docsgraph_server.jobs.worker.WorkerSettings
```

## Self-hosting

### Minimum Requirements

- **Container Engine**: Docker 20.10+ and Docker Compose 2.0+
- **Hardware**: 1 vCPU, 1 GB RAM (minimum; scale depending on OCR/indexing workloads)
- **Databases**: PostgreSQL 16+ and Redis 7+ (managed within the docker-compose stack or hosted externally)

### Deployment

1. **Configuration**: Copy the template environment file:
   ```bash
   cp .env.example .env
   ```
   For production deployments, ensure you set a secure `JWT_SECRET`, and override default database/Redis credentials if using external services.

2. **Launch**:
   Start the services. This will build the application image, run migrations via Alembic, and start the API and background worker:
   ```bash
   docker compose -f docker-compose.self-host.yml up -d --build
   ```

3. **Verify**:
   Ensure the service is healthy:
   ```bash
   curl -f http://localhost:8000/health
   ```

## Checks

Run these before opening a PR (CI runs the same set on Python 3.12 and 3.13):

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
```

## Project layout

Everything lives under `src/docsgraph_server/`:

| Module | Purpose |
| --- | --- |
| `main.py` | FastAPI app factory (`create_app()`), router mounting, `/health`. |
| `core/` | Cross-cutting concerns: settings (`config.py`), read from env/`.env`. |
| `db/` | Async SQLAlchemy engine/session, declarative base, Alembic migrations. |
| `api/` | HTTP routers, one module per domain area (documents, permissions, workflows, audit). |
| `sync/` | The client/server sync protocol: pydantic models + route stubs. |
| `ocr/` | OCR engine interface; Tesseract is the intended first backend. |
| `indexing/` | Search/embedding indexing interface. |
| `permissions/` | Permission/ACL model interface. |
| `workflows/` | Workflow/automation engine interface. |
| `audit/` | Audit log recording interface. |
| `retention/` | Retention policy enforcement interface. |
| `integrations/` | External integrations (cloud storage, e-signature, SSO, webhooks, ...). |
| `jobs/` | arq worker configuration and background task definitions. |

Most non-`api`/`sync` modules currently expose interfaces only
(`typing.Protocol`) — concrete implementations land as each area is built
out.

## License

MIT, see [LICENSE](./LICENSE).
