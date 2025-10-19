"""SQLite helpers for the spreadsheet application."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

from flask import current_app, g


_CONNECTION_KEY = "sqlite_connection"
_SCHEMA_VERSION_KEY = "_schema_initialized"


def _get_database_path() -> Path:
    database_path = current_app.config.get("DATABASE_PATH")
    if not database_path:
        raise RuntimeError("DATABASE_PATH is not configured")
    return Path(database_path)


def get_connection() -> sqlite3.Connection:
    """Return a connection scoped to the current application context."""

    connection: sqlite3.Connection | None = getattr(g, _CONNECTION_KEY, None)
    if connection is None:
        database_path = _get_database_path()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        setattr(g, _CONNECTION_KEY, connection)
    return connection


def close_db(_: Exception | None = None) -> None:
    """Close the active database connection if one exists."""

    connection: sqlite3.Connection | None = getattr(g, _CONNECTION_KEY, None)
    if connection is not None:
        connection.close()
        delattr(g, _CONNECTION_KEY)


def run_migrations() -> None:
    """Create database tables if they do not already exist."""

    if current_app.config.get(_SCHEMA_VERSION_KEY):
        return

    def execute(sql: str, *, on: sqlite3.Connection) -> None:
        on.executescript(sql)

    ensure_schema(execute)
    current_app.config[_SCHEMA_VERSION_KEY] = True


def ensure_schema(executor: Callable[[str, sqlite3.Connection], None] | None = None) -> None:
    """Ensure that all required tables are present in the database."""

    sql = """
    CREATE TABLE IF NOT EXISTS sheets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        row_count INTEGER NOT NULL,
        col_count INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    );

    CREATE TABLE IF NOT EXISTS sheet_cells (
        sheet_id INTEGER NOT NULL,
        row_index INTEGER NOT NULL,
        col_index INTEGER NOT NULL,
        value TEXT,
        PRIMARY KEY (sheet_id, row_index, col_index),
        FOREIGN KEY (sheet_id) REFERENCES sheets(id) ON DELETE CASCADE
    );
    """

    connection = get_connection()
    runner = executor or (lambda statement, *, on: on.executescript(statement))
    runner(sql, on=connection)
    connection.commit()


__all__ = ["close_db", "ensure_schema", "get_connection", "run_migrations"]
