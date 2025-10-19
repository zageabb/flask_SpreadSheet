"""Database helpers using SQLModel sessions."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from alembic import command
from alembic.config import Config
from flask import current_app, g
from sqlmodel import Session


_SESSION_KEY = "sqlmodel_session"
_MIGRATION_FLAG = "_migrations_applied"


def get_engine():
    """Return the SQLModel engine configured on the current app."""

    extension: Dict[str, Any] = current_app.extensions.setdefault("sqlmodel", {})
    engine = extension.get("engine")
    if engine is None:  # pragma: no cover - misconfiguration guard
        raise RuntimeError("SQLModel engine has not been initialised")
    return engine


def get_session() -> Session:
    """Return a scoped SQLModel session for the current request context."""

    if not hasattr(g, _SESSION_KEY):
        extension: Dict[str, Any] = current_app.extensions.get("sqlmodel", {})
        session_factory = extension.get("session_factory")
        if session_factory is None:  # pragma: no cover - misconfiguration guard
            raise RuntimeError("SQLModel session factory has not been initialised")
        setattr(g, _SESSION_KEY, session_factory())
    return getattr(g, _SESSION_KEY)


def close_db(_: Exception | None = None) -> None:
    """Close the active SQLModel session if present."""

    session: Session | None = getattr(g, _SESSION_KEY, None)
    if session is not None:
        session.close()
        delattr(g, _SESSION_KEY)


def run_migrations() -> None:
    """Apply pending Alembic migrations for the current application."""

    if current_app.config.get(_MIGRATION_FLAG):
        return

    config_path = Path(current_app.root_path).parent / "alembic.ini"
    if not config_path.exists():  # pragma: no cover - configuration error
        current_app.logger.warning("Alembic configuration not found at %s", config_path)
        return

    alembic_cfg = Config(str(config_path))
    database_url = current_app.config.get("DATABASE_URL")
    if database_url:
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    current_app.logger.info("Running database migrations")
    command.upgrade(alembic_cfg, "head")
    current_app.config[_MIGRATION_FLAG] = True
