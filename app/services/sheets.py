from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from flask import abort
from sqlmodel import Session, select

from ..models import Sheet, SheetCell
from ..schemas import (
    CellUpdate,
    DataQueryParams,
    DataWriteRequest,
    FilterClause,
    FilterOperator,
    RowPayload,
    SortDirection,
    ValidationError,
)
from .database import get_session


@dataclass(frozen=True)
class ColumnRule:
    type: str
    allow_blank: bool = True


DEFAULT_COLUMN_RULE = ColumnRule(type="text")
COLUMN_RULES: Dict[int, ColumnRule] = {1: ColumnRule(type="number")}


class SheetRepository:
    """Data access layer backed by SQLModel sessions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def commit(self) -> None:
        self.session.commit()

    def list_sheets(self) -> List[Dict[str, Any]]:
        query = select(Sheet).order_by(Sheet.created_at, Sheet.id)
        results = self.session.exec(query).all()
        return [{"id": sheet.id, "name": sheet.name} for sheet in results]

    def get_first_sheet(self) -> Sheet | None:
        query = select(Sheet).order_by(Sheet.id).limit(1)
        return self.session.exec(query).first()

    def get_sheet(self, sheet_id: int) -> Sheet | None:
        return self.session.get(Sheet, sheet_id)

    def add_sheet(self, name: str, row_count: int, col_count: int) -> Sheet:
        sheet = Sheet(name=name, row_count=row_count, col_count=col_count)
        self.session.add(sheet)
        self.session.flush()
        self.session.refresh(sheet)
        return sheet

    def rename_sheet(self, sheet_id: int, name: str) -> Sheet | None:
        sheet = self.session.get(Sheet, sheet_id)
        if sheet is None:
            return None
        sheet.name = name
        sheet.updated_at = datetime.now(UTC)
        self.session.add(sheet)
        self.session.flush()
        self.session.refresh(sheet)
        return sheet

    def update_dimensions(
        self, sheet_id: int, row_count: int | None, col_count: int | None
    ) -> Sheet | None:
        sheet = self.session.get(Sheet, sheet_id)
        if sheet is None:
            return None
        new_row_count = sheet.row_count
        new_col_count = sheet.col_count
        changed = False
        if isinstance(row_count, int) and row_count > 0:
            new_row_count = row_count
            changed = True
        if isinstance(col_count, int) and col_count > 0:
            new_col_count = col_count
            changed = True
        if not changed:
            return sheet
        sheet.row_count = new_row_count
        sheet.col_count = new_col_count
        sheet.updated_at = datetime.now(UTC)
        self.session.add(sheet)
        self.session.flush()
        self.session.refresh(sheet)
        return sheet

    def get_cells(self, sheet_id: int) -> List[SheetCell]:
        query = (
            select(SheetCell)
            .where(SheetCell.sheet_id == sheet_id)
            .order_by(SheetCell.row_index, SheetCell.col_index)
        )
        return list(self.session.exec(query))

    def upsert_cell(self, sheet_id: int, row: int, col: int, value: str | None) -> None:
        key = (sheet_id, row, col)
        existing = self.session.get(SheetCell, key)
        if value is None or value == "":
            if existing is not None:
                self.session.delete(existing)
                self.session.flush()
            return

        if existing is None:
            cell = SheetCell(
                sheet_id=sheet_id,
                row_index=row,
                col_index=col,
                value=value,
            )
            self.session.add(cell)
        else:
            existing.value = value
            self.session.add(existing)
        self.session.flush()

    def has_sheets(self) -> bool:
        query = select(Sheet.id).limit(1)
        return self.session.exec(query).first() is not None


class SheetService:
    def __init__(self, repository: SheetRepository) -> None:
        self.repository = repository

    def list_sheets(self) -> List[Dict[str, Any]]:
        return self.repository.list_sheets()

    def _get_sheet_or_404(self, sheet_id: int | None) -> Sheet:
        sheet = (
            self.repository.get_first_sheet()
            if sheet_id is None
            else self.repository.get_sheet(sheet_id)
        )
        if sheet is None:
            abort(404, description="Sheet not found")
        return sheet

    def fetch_sheet(
        self, sheet_id: int | None = None
    ) -> Tuple[int, str, int, int, List[List[str]]]:
        sheet = self._get_sheet_or_404(sheet_id)
        cells = self.repository.get_cells(sheet.id)
        data = [["" for _ in range(sheet.col_count)] for _ in range(sheet.row_count)]
        for cell in cells:
            if 0 <= cell.row_index < sheet.row_count and 0 <= cell.col_index < sheet.col_count:
                data[cell.row_index][cell.col_index] = cell.value or ""
        return sheet.id, sheet.name, sheet.row_count, sheet.col_count, data

    def ensure_default_sheet(self) -> None:
        if not self.repository.has_sheets():
            self.repository.add_sheet("Sheet 1", 12, 8)
            self.repository.commit()

    def update_dimensions(
        self, sheet_id: int, row_count: int | None, col_count: int | None
    ) -> None:
        sheet = self.repository.update_dimensions(sheet_id, row_count, col_count)
        if sheet is None:
            abort(404, description="Sheet not found")
        self.repository.commit()

    def _normalize_cell_value(self, column_index: int, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            if value.strip() == "":
                return None
            candidate: Any = value
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
        self,
        sheet_id: int,
        updates: Iterable[Dict[str, Any] | CellUpdate],
        *,
        validate: bool = False,
    ) -> None:
        for update in updates:
            if isinstance(update, CellUpdate):
                cell_update = update
            else:
                try:
                    cell_update = CellUpdate.model_validate(update)
                except ValidationError:
                    continue
            row = cell_update.row
            col = cell_update.col
            value = cell_update.value
            normalized = (
                self._normalize_cell_value(col, value) if validate else value
            )
            self.repository.upsert_cell(sheet_id, row, col, normalized)
        self.repository.commit()

    def create_sheet(
        self, name: str, row_count: int, col_count: int, cells: Iterable[Dict[str, Any]]
    ) -> int:
        sheet = self.repository.add_sheet(name, row_count, col_count)
        for cell in cells:
            try:
                row = int(cell.get("row"))
                col = int(cell.get("col"))
            except (TypeError, ValueError):
                continue
            value = cell.get("value")
            if value is None or value == "":
                continue
            self.repository.upsert_cell(sheet.id, row, col, str(value))
        self.repository.commit()
        return sheet.id

    def rename_sheet(self, sheet_id: int, name: str) -> int:
        sheet = self.repository.rename_sheet(sheet_id, name)
        if sheet is None:
            abort(404, description="Sheet not found")
        self.repository.commit()
        return sheet.id

    def query_sheet_data(self, params: DataQueryParams) -> Dict[str, Any]:
        sheet_id, sheet_name, row_count, col_count, data = self.fetch_sheet(
            params.sheet_id
        )
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
            RowPayload(row_index=row_index, values=row_values).model_dump(by_alias=True)
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
            "sheets": self.list_sheets(),
        }

    def write_sheet_data(self, request: DataWriteRequest) -> Dict[str, Any]:
        if self.repository.get_sheet(request.sheet_id) is None:
            abort(404, description="Sheet not found")

        self.repository.update_dimensions(
            request.sheet_id, request.row_count, request.col_count
        )
        self.apply_updates(request.sheet_id, request.updates, validate=True)

        sheet_id, _, row_count, col_count, _ = self.fetch_sheet(request.sheet_id)
        return {
            "sheetId": sheet_id,
            "rowCount": row_count,
            "colCount": col_count,
            "totalRows": row_count,
            "updatedCells": len(request.updates),
        }


def _get_column_rule(column_index: int) -> ColumnRule:
    return COLUMN_RULES.get(column_index, DEFAULT_COLUMN_RULE)


def _format_decimal(value: Decimal) -> str:
    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


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


def list_sheets() -> List[Dict[str, Any]]:
    return SheetService(SheetRepository(get_session())).list_sheets()


def fetch_sheet(sheet_id: int | None = None) -> Tuple[int, str, int, int, List[List[str]]]:
    return SheetService(SheetRepository(get_session())).fetch_sheet(sheet_id)


def apply_updates(
    sheet_id: int,
    updates: Iterable[Dict[str, Any] | CellUpdate],
    *,
    validate: bool = False,
) -> None:
    SheetService(SheetRepository(get_session())).apply_updates(
        sheet_id, updates, validate=validate
    )


def update_dimensions(sheet_id: int, row_count: int | None, col_count: int | None) -> None:
    SheetService(SheetRepository(get_session())).update_dimensions(
        sheet_id, row_count, col_count
    )


def create_sheet(
    name: str, row_count: int, col_count: int, cells: Iterable[Dict[str, Any]]
) -> int:
    return SheetService(SheetRepository(get_session())).create_sheet(
        name, row_count, col_count, cells
    )


def rename_sheet(sheet_id: int, name: str) -> int:
    return SheetService(SheetRepository(get_session())).rename_sheet(sheet_id, name)


def query_sheet_data(params: DataQueryParams) -> Dict[str, Any]:
    return SheetService(SheetRepository(get_session())).query_sheet_data(params)


def write_sheet_data(request: DataWriteRequest) -> Dict[str, Any]:
    return SheetService(SheetRepository(get_session())).write_sheet_data(request)


def ensure_default_sheet() -> None:
    SheetService(SheetRepository(get_session())).ensure_default_sheet()


__all__ = [
    "apply_updates",
    "create_sheet",
    "ensure_default_sheet",
    "fetch_sheet",
    "list_sheets",
    "query_sheet_data",
    "rename_sheet",
    "update_dimensions",
    "write_sheet_data",
]
