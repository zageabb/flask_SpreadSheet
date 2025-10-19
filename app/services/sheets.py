from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from flask import abort

from pydantic import ValidationError

from ..schemas import (
    CellUpdate,
    DataQueryParams,
    DataWriteRequest,
    FilterClause,
    FilterOperator,
    RowPayload,
    SortDirection,
)
from .database import get_db


@dataclass(frozen=True)
class ColumnRule:
    """Represents validation rules for a column."""

    type: str
    allow_blank: bool = True


DEFAULT_COLUMN_RULE = ColumnRule(type="text")

# Basic column configuration used for validation. Columns not listed fall back to
# ``DEFAULT_COLUMN_RULE`` which accepts free-form text.
COLUMN_RULES: Dict[int, ColumnRule] = {
    1: ColumnRule(type="number"),
}


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


def _get_column_rule(column_index: int) -> ColumnRule:
    return COLUMN_RULES.get(column_index, DEFAULT_COLUMN_RULE)


def _format_decimal(value: Decimal) -> str:
    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _normalize_cell_value(column_index: int, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip() == "":
            return None
        candidate = value
    else:
        candidate = value

    rule = _get_column_rule(column_index)
    if candidate is None:
        if rule.allow_blank:
            return None
        abort(400, description=f"Column {column_index} cannot be blank")

    if rule.type == "number":
        try:
            decimal_value = Decimal(str(candidate))
        except (InvalidOperation, ValueError, TypeError):
            abort(400, description=f"Column {column_index} requires a numeric value")
        return _format_decimal(decimal_value)

    if rule.type == "date":
        try:
            dt = datetime.fromisoformat(str(candidate))
        except ValueError:
            abort(400, description=f"Column {column_index} requires an ISO date value")
        return dt.date().isoformat()

    return str(candidate)


def apply_updates(
    sheet_id: int,
    updates: Iterable[Dict[str, Any] | CellUpdate],
    *,
    validate: bool = False,
) -> None:
    db = get_db()
    for update in updates:
        if isinstance(update, CellUpdate):
            cell_update = update
        else:
            try:
                cell_update = CellUpdate.model_validate(update)
            except ValidationError:  # pragma: no cover - ignore malformed updates silently
                continue
        row = cell_update.row
        col = cell_update.col
        value = cell_update.value
        normalized = _normalize_cell_value(col, value) if validate else value
        _update_cell(sheet_id, row, col, normalized)
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


def _parse_filter_value(rule: ColumnRule, value: Any) -> Any:
    if value is None:
        return None
    if rule.type == "number":
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
    if rule.type == "date":
        try:
            return datetime.fromisoformat(str(value)).date()
        except ValueError:
            return None
    return str(value)


def _parse_cell_for_rule(rule: ColumnRule, value: str) -> Any:
    if value == "":
        return None
    if rule.type == "number":
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
    if rule.type == "date":
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return value


def _filter_rows(
    rows: Sequence[Tuple[int, List[str]]],
    filters: Sequence[FilterClause],
    col_count: int,
) -> List[Tuple[int, List[str]]]:
    if not filters:
        return list(rows)

    def row_matches(row_index: int, values: List[str]) -> bool:
        for clause in filters:
            column = clause.column
            if column < 0 or column >= col_count:
                return False
            rule = _get_column_rule(column)
            cell_value = values[column] if column < len(values) else ""
            parsed_cell = _parse_cell_for_rule(rule, cell_value)
            target_value = _parse_filter_value(rule, clause.value)
            operator = clause.operator

            if operator == FilterOperator.CONTAINS:
                haystack = (cell_value or "").lower()
                needle = str(clause.value or "").lower()
                if needle not in haystack:
                    return False
                continue

            if operator == FilterOperator.EQUAL:
                if parsed_cell != target_value:
                    return False
            elif operator == FilterOperator.NOT_EQUAL:
                if parsed_cell == target_value:
                    return False
            elif operator == FilterOperator.LESS_THAN:
                if parsed_cell is None or target_value is None or parsed_cell >= target_value:
                    return False
            elif operator == FilterOperator.LESS_THAN_OR_EQUAL:
                if parsed_cell is None or target_value is None or parsed_cell > target_value:
                    return False
            elif operator == FilterOperator.GREATER_THAN:
                if parsed_cell is None or target_value is None or parsed_cell <= target_value:
                    return False
            elif operator == FilterOperator.GREATER_THAN_OR_EQUAL:
                if parsed_cell is None or target_value is None or parsed_cell < target_value:
                    return False
        return True

    return [row for row in rows if row_matches(*row)]


def _sort_rows(
    rows: Sequence[Tuple[int, List[str]]],
    sort_column: int | None,
    direction: SortDirection,
    col_count: int,
) -> List[Tuple[int, List[str]]]:
    if sort_column is None or sort_column < 0 or sort_column >= col_count:
        return list(rows)

    rule = _get_column_rule(sort_column)
    if rule.type == "number":
        decorated: List[Tuple[Tuple[int, Decimal], Tuple[int, List[str]]]] = []
        for item in rows:
            _, values = item
            cell_value = values[sort_column] if sort_column < len(values) else ""
            try:
                decimal_value = Decimal(str(cell_value))
                score = decimal_value if direction == SortDirection.ASC else -decimal_value
                decorated.append(((0, score), item))
            except (InvalidOperation, ValueError, TypeError):
                decorated.append(((1, Decimal(0)), item))
        decorated.sort(key=lambda pair: pair[0])
        return [item for _, item in decorated]

    if rule.type == "date":
        decorated_dt: List[Tuple[Tuple[int, float], Tuple[int, List[str]]]] = []
        for item in rows:
            _, values = item
            cell_value = values[sort_column] if sort_column < len(values) else ""
            try:
                dt = datetime.fromisoformat(str(cell_value))
                ordinal = (
                    dt.toordinal() * 86400
                    + dt.hour * 3600
                    + dt.minute * 60
                    + dt.second
                    + dt.microsecond / 1_000_000
                )
                score = ordinal if direction == SortDirection.ASC else -ordinal
                decorated_dt.append(((0, score), item))
            except ValueError:
                decorated_dt.append(((1, 0.0), item))
        decorated_dt.sort(key=lambda pair: pair[0])
        return [item for _, item in decorated_dt]

    return sorted(
        rows,
        key=lambda item: (
            (item[1][sort_column] if sort_column < len(item[1]) else "").lower()
        ),
        reverse=direction == SortDirection.DESC,
    )


def query_sheet_data(params: DataQueryParams) -> Dict[str, Any]:
    sheet_id, sheet_name, row_count, col_count, data = fetch_sheet(params.sheet_id)
    rows: List[Tuple[int, List[str]]] = [
        (index, list(row_values)) for index, row_values in enumerate(data)
    ]

    filtered = _filter_rows(rows, params.filters, col_count)
    sorted_rows = _sort_rows(filtered, params.sort_column, params.sort_direction, col_count)

    total_rows = len(sorted_rows)
    if params.page_size == 0:
        page_rows = sorted_rows
        page_size = len(sorted_rows)
    else:
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        page_rows = sorted_rows[start:end]
        page_size = params.page_size

    serialized_rows = [
        RowPayload(rowIndex=row_index, values=row_values).model_dump(by_alias=True)
        for row_index, row_values in page_rows
    ]

    return {
        "sheetId": sheet_id,
        "sheetName": sheet_name,
        "rowCount": row_count,
        "colCount": col_count,
        "page": params.page,
        "pageSize": page_size,
        "totalRows": total_rows,
        "rows": serialized_rows,
        "sheets": list_sheets(),
    }


def write_sheet_data(request: DataWriteRequest) -> Dict[str, Any]:
    db = get_db()
    sheet = db.execute("SELECT id FROM sheets WHERE id = ?", (request.sheet_id,)).fetchone()
    if sheet is None:
        abort(404, description="Sheet not found")

    update_dimensions(request.sheet_id, request.row_count, request.col_count)
    apply_updates(request.sheet_id, request.updates, validate=True)

    sheet_id, _, row_count, col_count, _ = fetch_sheet(request.sheet_id)
    return {
        "sheetId": sheet_id,
        "rowCount": row_count,
        "colCount": col_count,
        "totalRows": row_count,
        "updatedCells": len(request.updates),
    }
