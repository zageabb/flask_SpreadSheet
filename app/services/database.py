"""Database helpers built around SQLModel sessions and Alembic migrations."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from alembic import command
from alembic.config import Config
from flask import Flask, current_app, g
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

_ENGINE_KEY = "sqlmodel_engine"
_SESSION_FACTORY_KEY = "sqlmodel_session_factory"
_SESSION_KEY = "sqlmodel_session"
_MIGRATIONS_FLAG = "_alembic_migrated"


def configure_engine(app: Flask, database_url: str) -> Engine:
    """Create and register the SQLModel engine and session factory on the app."""

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(
        database_url,
        echo=app.config.get("SQLMODEL_ECHO", False),
        connect_args=connect_args,
    )

    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    app.extensions[_ENGINE_KEY] = engine
    app.extensions[_SESSION_FACTORY_KEY] = session_factory
    return engine


def get_engine() -> Engine:
    """Return the configured SQLAlchemy engine."""

    engine = current_app.extensions.get(_ENGINE_KEY)
    if engine is None:
        raise RuntimeError("SQLModel engine has not been configured")
    return engine


def get_session() -> Session:
    """Return a scoped SQLModel session for the active request context."""

    session: Session | None = getattr(g, _SESSION_KEY, None)
    if session is None:
        factory: Callable[[], Session] | None = current_app.extensions.get(
            _SESSION_FACTORY_KEY
        )
        if factory is None:
            raise RuntimeError("SQLModel session factory has not been configured")
        session = factory()
        setattr(g, _SESSION_KEY, session)
    return session


def close_db(_: Exception | None = None) -> None:
    """Close the active SQLModel session if one exists."""

    session: Session | None = getattr(g, _SESSION_KEY, None)
    if session is not None:
        session.close()
        delattr(g, _SESSION_KEY)


def _make_alembic_config() -> Config:
    app_root = Path(current_app.root_path)
    project_root = app_root.parent

    config_path = project_root / "alembic.ini"
    if not config_path.exists():
        raise RuntimeError("Alembic configuration file not found")

    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(project_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", current_app.config["DATABASE_URL"])
    return cfg


def run_migrations() -> None:
    """Apply pending Alembic migrations for the configured database."""

    if current_app.config.get(_MIGRATIONS_FLAG):
        return

    cfg = _make_alembic_config()
    engine = get_engine()
    inspector = sa.inspect(engine)

    alembic_table_exists = inspector.has_table("alembic_version")

    needs_stamp = False
    if not alembic_table_exists:
        from sqlmodel import SQLModel

        existing_tables = set(inspector.get_table_names())
        metadata_tables = {table.name for table in SQLModel.metadata.sorted_tables}
        needs_stamp = bool(existing_tables & metadata_tables)

    if needs_stamp:
        stamp = getattr(command, "stamp", None)
        if stamp is not None:
            stamp(cfg, "head")
        else:  # pragma: no cover - stub fallback for tests
            command.upgrade(cfg, "head")
    else:
        command.upgrade(cfg, "head")

    current_app.config[_MIGRATIONS_FLAG] = True


__all__ = [
    "close_db",
    "configure_engine",
    "get_engine",
    "get_session",
    "run_migrations",
]
