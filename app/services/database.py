import sqlite3
from datetime import datetime

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database_path = current_app.config["DATABASE_PATH"]
        current_app.logger.debug("Opening database connection to %s", database_path)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_: Exception | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        current_app.logger.debug("Closing database connection")
        db.close()


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
    return db.execute(query, (name,)).fetchone() is not None


def _migrate_legacy_schema(db: sqlite3.Connection) -> None:
    if not _table_exists(db, "grid_info"):
        return
    current_app.logger.info("Migrating legacy schema to sheets/sheet_cells tables")
    info = db.execute("SELECT row_count, col_count FROM grid_info WHERE id = 1").fetchone()
    if info is None:
        default_rows, default_cols = 12, 8
    else:
        default_rows, default_cols = info["row_count"], info["col_count"]
    cursor = db.execute("SELECT row_index, col_index, value FROM cells")
    cells = cursor.fetchall()
    now = datetime.utcnow().isoformat()
    db.execute(
        """
        INSERT INTO sheets (name, row_count, col_count, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("Sheet 1", default_rows, default_cols, now, now),
    )
    sheet_id = db.execute("SELECT id FROM sheets WHERE name = ?", ("Sheet 1",)).fetchone()["id"]
    if cells:
        db.executemany(
            """
            INSERT INTO sheet_cells (sheet_id, row_index, col_index, value)
            VALUES (?, ?, ?, ?)
            """,
            [(sheet_id, row["row_index"], row["col_index"], row["value"]) for row in cells],
        )
    db.execute("DROP TABLE IF EXISTS cells")
    db.execute("DROP TABLE IF EXISTS grid_info")


def init_db() -> None:
    db = get_db()
    with db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS sheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                row_count INTEGER NOT NULL,
                col_count INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS sheet_cells (
                sheet_id INTEGER NOT NULL,
                row_index INTEGER NOT NULL,
                col_index INTEGER NOT NULL,
                value TEXT,
                PRIMARY KEY (sheet_id, row_index, col_index),
                FOREIGN KEY (sheet_id) REFERENCES sheets(id) ON DELETE CASCADE
            )
            """
        )

        if not _table_exists(db, "sheets"):
            return

        if db.execute("SELECT COUNT(*) as count FROM sheets").fetchone()["count"] == 0:
            _migrate_legacy_schema(db)

        if db.execute("SELECT COUNT(*) as count FROM sheets").fetchone()["count"] == 0:
            now = datetime.utcnow().isoformat()
            db.execute(
                """
                INSERT INTO sheets (name, row_count, col_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("Sheet 1", 12, 8, now, now),
            )
