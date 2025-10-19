from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from flask import abort

from .database import get_db


def list_sheets() -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute("SELECT id, name FROM sheets ORDER BY created_at, id").fetchall()
    return [dict(row) for row in rows]


def fetch_sheet(sheet_id: int | None = None) -> Tuple[int, str, int, int, List[List[str]]]:
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


def _update_cell(sheet_id: int, row: int, col: int, value: str | None) -> None:
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


def apply_updates(sheet_id: int, updates: Iterable[Dict[str, Any]]) -> None:
    db = get_db()
    for update in updates:
        try:
            row = int(update.get("row"))
            col = int(update.get("col"))
        except (TypeError, ValueError):
            continue
        value = update.get("value")
        _update_cell(sheet_id, row, col, value)
    db.commit()


def update_dimensions(sheet_id: int, row_count: int | None, col_count: int | None) -> None:
    db = get_db()
    now = datetime.utcnow().isoformat()
    if isinstance(row_count, int) and row_count > 0:
        db.execute(
            "UPDATE sheets SET row_count = ?, updated_at = ? WHERE id = ?",
            (row_count, now, sheet_id),
        )
    if isinstance(col_count, int) and col_count > 0:
        db.execute(
            "UPDATE sheets SET col_count = ?, updated_at = ? WHERE id = ?",
            (col_count, now, sheet_id),
        )


def create_sheet(name: str, row_count: int, col_count: int, cells: Iterable[Dict[str, Any]]) -> int:
    db = get_db()
    now = datetime.utcnow().isoformat()
    cursor = db.execute(
        """
        INSERT INTO sheets (name, row_count, col_count, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, row_count, col_count, now, now),
    )
    sheet_id = cursor.lastrowid
    normalized: List[Tuple[int, int, int, str]] = []
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
    db.commit()
    return sheet_id


def rename_sheet(sheet_id: int, name: str) -> int:
    db = get_db()
    now = datetime.utcnow().isoformat()
    result = db.execute(
        "UPDATE sheets SET name = ?, updated_at = ? WHERE id = ?",
        (name, now, sheet_id),
    )
    if result.rowcount == 0:
        abort(404, description="Sheet not found")
    db.commit()
    return sheet_id
