# Operations Guide

## Database Migrations
- Alembic configuration lives at `alembic.ini` with migration scripts under `alembic/versions/`.
- The Flask factory runs `alembic upgrade head` on startup via `app/services/database.py` helpers.
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

## Background Jobs
- Not implemented yet. When asynchronous workers (e.g., Celery, RQ) are introduced, document the queue name, worker startup command, and failure handling here.

## Caching
- No cache layer is configured today. Capture cache backends (Redis, Memcached, etc.), invalidation strategies, and warm-up routines once they exist.

## Configuration Management
- Environment configuration relies on standard Flask environment variables (`FLASK_APP`, `FLASK_ENV`, `DATABASE_URL`).
- Secrets are sourced from the environment; avoid committing production credentials.

## Deployment Checklist
1. Apply migrations (`alembic upgrade head`).
2. Ensure the `instance/` directory is writable by the Flask process (used for the SQLite DB and import previews).
3. Configure logging via `logging.conf` or override with deployment-specific handlers.
4. Update this guide when new operational dependencies (message brokers, cron jobs, object storage) are introduced.
