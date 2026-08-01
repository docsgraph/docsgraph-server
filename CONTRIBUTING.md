# Contributing

Thanks for contributing to `docsgraph-server`. For shared conventions
across all docsgraph repos (code of conduct, general PR expectations,
etc.), see [docsgraph/.github](https://github.com/docsgraph/.github).

## Dev environment

Requires [`uv`](https://docs.astral.sh/uv/) and Docker.

```bash
docker compose up -d
uv sync --all-extras --locked
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn docsgraph_server.main:app --reload
```

Optionally install the git hooks so checks run automatically on commit:

```bash
uv run pre-commit install
```

## Before opening a PR

Run the full check suite locally and make sure it's clean:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
```

Keep changes scoped, add tests for new behavior, and update `README.md`
if you add or move a module under `src/docsgraph_server/`.
