import hmac
import os
import secrets
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, render_template, request, g, abort


def create_app():
    app = Flask(__name__)
    app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret-key"))
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("PREFERRED_URL_SCHEME", "https") == "https",
    )

    CSRF_COOKIE_NAME = "spreadsheet_csrftoken"
    CSRF_HEADER_NAME = "X-CSRFToken"
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

    db_path = os.path.join(app.instance_path, "spreadsheet.db")
    os.makedirs(app.instance_path, exist_ok=True)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
        return g.db

    def close_db(e=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def table_exists(db, name):
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        return db.execute(query, (name,)).fetchone() is not None

    def migrate_legacy_schema(db):
        if not table_exists(db, "grid_info"):
            return
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

    def init_db():
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

            if not table_exists(db, "sheets"):
                return

            if db.execute("SELECT COUNT(*) as count FROM sheets").fetchone()["count"] == 0:
                migrate_legacy_schema(db)

            if db.execute("SELECT COUNT(*) as count FROM sheets").fetchone()["count"] == 0:
                now = datetime.utcnow().isoformat()
                db.execute(
                    """
                    INSERT INTO sheets (name, row_count, col_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("Sheet 1", 12, 8, now, now),
                )

    def _ensure_csrf_token():
        token = request.cookies.get(CSRF_COOKIE_NAME)
        if not token:
            token = secrets.token_urlsafe(32)
        g.csrf_token = token
        return token

    @app.before_request
    def before_request():
        init_db()
        token = _ensure_csrf_token()
        if request.method not in SAFE_METHODS:
            header_token = request.headers.get(CSRF_HEADER_NAME)
            if not header_token or not hmac.compare_digest(token, header_token):
                abort(400, description="Invalid CSRF token")

    @app.teardown_appcontext
    def teardown_db(exception):
        close_db()

    @app.after_request
    def after_request(response):
        token = getattr(g, "csrf_token", None)
        if token:
            response.set_cookie(
                CSRF_COOKIE_NAME,
                token,
                secure=app.config.get("SESSION_COOKIE_SECURE", False),
                samesite="Lax",
                httponly=False,
            )
        return response

    def fetch_sheet(sheet_id=None):
        db = get_db()
        if sheet_id is None:
            sheet = db.execute(
                "SELECT id, name, row_count, col_count FROM sheets ORDER BY id LIMIT 1"
            ).fetchone()
        else:
            sheet = db.execute(
                "SELECT id, name, row_count, col_count FROM sheets WHERE id = ?",
                (sheet_id,),
            ).fetchone()
        if sheet is None:
            abort(404, description="Sheet not found")
        row_count = sheet["row_count"]
        col_count = sheet["col_count"]
        cursor = db.execute(
            "SELECT row_index, col_index, value FROM sheet_cells WHERE sheet_id = ?",
            (sheet["id"],),
        )
        cells = {(row, col): value for row, col, value in cursor.fetchall()}
        data = [["" for _ in range(col_count)] for _ in range(row_count)]
        for (row, col), value in cells.items():
            if 0 <= row < row_count and 0 <= col < col_count:
                data[row][col] = value
        return sheet["id"], sheet["name"], row_count, col_count, data

    def list_sheets():
        db = get_db()
        rows = db.execute(
            "SELECT id, name FROM sheets ORDER BY created_at, id"
        ).fetchall()
        return [dict(row) for row in rows]

    @app.route("/")
    def index():
        sheet_id, _, row_count, col_count, _ = fetch_sheet()
        sheets = list_sheets()
        return render_template(
            "index.html",
            row_count=row_count,
            col_count=col_count,
            sheet_id=sheet_id,
            sheets=sheets,
        )

    @app.route("/api/grid", methods=["GET"])
    def get_grid():
        try:
            sheet_id = request.args.get("sheetId", type=int)
        except (TypeError, ValueError):
            sheet_id = None
        sheet_id, sheet_name, row_count, col_count, data = fetch_sheet(sheet_id)
        return jsonify(
            {
                "sheetId": sheet_id,
                "sheetName": sheet_name,
                "rowCount": row_count,
                "colCount": col_count,
                "cells": data,
                "sheets": list_sheets(),
            }
        )

    def update_cell(sheet_id, row, col, value):
        db = get_db()
        if value is None or value == "":
            db.execute(
                "DELETE FROM sheet_cells WHERE sheet_id = ? AND row_index = ? AND col_index = ?",
                (sheet_id, row, col),
            )
        else:
            db.execute(
                """
                INSERT INTO sheet_cells (sheet_id, row_index, col_index, value)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sheet_id, row_index, col_index) DO UPDATE SET value=excluded.value
                """,
                (sheet_id, row, col, value),
            )

    @app.route("/api/grid", methods=["POST"])
    def save_grid():
        payload = request.get_json(silent=True) or {}
        updates = payload.get("updates", [])
        new_row_count = payload.get("rowCount")
        new_col_count = payload.get("colCount")
        sheet_id = payload.get("sheetId")
        if not isinstance(sheet_id, int):
            abort(400, description="sheetId is required")

        db = get_db()
        with db:
            sheet = db.execute("SELECT id FROM sheets WHERE id = ?", (sheet_id,)).fetchone()
            if sheet is None:
                abort(404, description="Sheet not found")
            if isinstance(new_row_count, int) and new_row_count > 0:
                db.execute(
                    "UPDATE sheets SET row_count = ?, updated_at = ? WHERE id = ?",
                    (new_row_count, datetime.utcnow().isoformat(), sheet_id),
                )
            if isinstance(new_col_count, int) and new_col_count > 0:
                db.execute(
                    "UPDATE sheets SET col_count = ?, updated_at = ? WHERE id = ?",
                    (new_col_count, datetime.utcnow().isoformat(), sheet_id),
                )
            for update in updates:
                try:
                    row = int(update.get("row"))
                    col = int(update.get("col"))
                except (TypeError, ValueError):
                    continue
                value = update.get("value")
                update_cell(sheet_id, row, col, value)

        sheet_id, _, row_count, col_count, _ = fetch_sheet(sheet_id)
        return (
            jsonify({"sheetId": sheet_id, "rowCount": row_count, "colCount": col_count}),
            200,
        )

    @app.route("/api/sheets", methods=["GET"])
    def get_sheets():
        return jsonify({"sheets": list_sheets()})

    @app.route("/api/sheets", methods=["POST"])
    def create_sheet():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            abort(400, description="Sheet name is required")
        name = name.strip()
        row_count = payload.get("rowCount", 12)
        col_count = payload.get("colCount", 8)
        try:
            row_count = int(row_count)
            col_count = int(col_count)
        except (TypeError, ValueError):
            abort(400, description="Invalid row or column count")
        if row_count <= 0 or col_count <= 0:
            abort(400, description="Row and column counts must be positive")
        cells = payload.get("cells", [])
        now = datetime.utcnow().isoformat()
        db = get_db()
        with db:
            try:
                cursor = db.execute(
                    """
                    INSERT INTO sheets (name, row_count, col_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, row_count, col_count, now, now),
                )
            except sqlite3.IntegrityError:
                abort(409, description="A sheet with that name already exists")
            sheet_id = cursor.lastrowid
            if cells:
                normalized = []
                for cell in cells:
                    try:
                        row = int(cell.get("row"))
                        col = int(cell.get("col"))
                    except (TypeError, ValueError):
                        continue
                    value = cell.get("value")
                    if value is None or value == "":
                        continue
                    normalized.append((sheet_id, row, col, str(value)))
                if normalized:
                    db.executemany(
                        """
                        INSERT INTO sheet_cells (sheet_id, row_index, col_index, value)
                        VALUES (?, ?, ?, ?)
                        """,
                        normalized,
                    )
        return (
            jsonify(
                {
                    "sheetId": sheet_id,
                    "rowCount": row_count,
                    "colCount": col_count,
                    "sheets": list_sheets(),
                }
            ),
            201,
        )

    @app.route("/api/sheets/<int:sheet_id>", methods=["PATCH"])
    def rename_sheet(sheet_id):
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            abort(400, description="Sheet name is required")
        name = name.strip()
        db = get_db()
        with db:
            try:
                result = db.execute(
                    "UPDATE sheets SET name = ?, updated_at = ? WHERE id = ?",
                    (name, datetime.utcnow().isoformat(), sheet_id),
                )
            except sqlite3.IntegrityError:
                abort(409, description="A sheet with that name already exists")
            if result.rowcount == 0:
                abort(404, description="Sheet not found")
        return jsonify({"sheets": list_sheets(), "sheetId": sheet_id, "name": name}), 200

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
