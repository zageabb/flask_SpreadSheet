# Operations Guide

## Database Migrations
- Alembic configuration lives at `alembic.ini` with migration scripts under `alembic/versions/`.
- The Flask factory runs `alembic upgrade head` on startup via helpers in `app/services/database.py` so the schema stays current.
- To run migrations manually:
  ```bash
  export DATABASE_URL=sqlite:///$(pwd)/instance/spreadsheet.db
  alembic upgrade head
  ```
- Generate new revisions after changing models with:
  ```bash
  alembic revision --autogenerate -m "describe change"
  alembic upgrade head
  ```

Document any non-default migration workflows (e.g., offline migrations, zero-downtime steps) here when the deployment story evolves.

## Background Jobs
- Not implemented yet. When asynchronous workers (Celery, RQ, APScheduler, etc.) are introduced, record:
  - Queue/backing services (Redis, SQS, etc.).
  - Worker startup commands and scaling guidance.
  - Failure/retry handling expectations and observability hooks.

## Caching
- No cache layer is configured today. When one is added, specify:
  - Backend selection (Redis, Memcached, in-process caches) and connection settings.
  - Invalidation strategy and cache key formats.
  - Warm-up or cache priming routines required during deployment.

## Configuration Management
- Environment configuration relies on standard Flask environment variables (`FLASK_APP`, `FLASK_ENV`, `DATABASE_URL`).
- Secrets are sourced from the environment; avoid committing production credentials.

List new environment variables, feature flags, or third-party integrations here as they are introduced.

## Deployment Checklist
1. Apply migrations (`alembic upgrade head`).
2. Ensure the `instance/` directory is writable by the Flask process (used for the SQLite DB and import previews).
3. Configure logging via `logging.conf` or override with deployment-specific handlers.
4. Provision and document background workers, caches, or other infrastructure whenever the application begins relying on them.
5. Update this guide alongside any operational change so operators can trust it as the source of truth.
