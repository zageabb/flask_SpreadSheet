"""Lightweight validation helpers replacing the former pydantic models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional


class ValidationError(ValueError):
    """Raised when incoming payloads fail validation."""


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"

    @classmethod
    def parse(cls, value: Any) -> "SortDirection":
        if isinstance(value, SortDirection):
            return value
        if isinstance(value, str):
            candidate = value.lower()
            for member in cls:
                if member.value == candidate:
                    return member
        raise ValidationError(f"Invalid sort direction: {value!r}")


class FilterOperator(str, Enum):
    EQUAL = "eq"
    NOT_EQUAL = "ne"
    CONTAINS = "contains"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"

    @classmethod
    def parse(cls, value: Any) -> "FilterOperator":
        if isinstance(value, FilterOperator):
            return value
        if isinstance(value, str):
            candidate = value.lower()
            for member in cls:
                if member.value == candidate:
                    return member
        raise ValidationError(f"Invalid filter operator: {value!r}")


def _require_int(value: Any, field: str, *, minimum: Optional[int] = None, allow_none: bool = False) -> Optional[int]:
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"Field '{field}' is required")
    if isinstance(value, bool):
        raise ValidationError(f"Field '{field}' must be an integer")
    try:
        integer = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Field '{field}' must be an integer") from None
    if minimum is not None and integer < minimum:
        raise ValidationError(f"Field '{field}' must be >= {minimum}")
    return integer


def _require_list(value: Any, field: str) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise ValidationError(f"Field '{field}' must be a list")


@dataclass(slots=True)
class FilterClause:
    column: int
    operator: FilterOperator
    value: Any = None

    @classmethod
    def model_validate(cls, payload: Mapping[str, Any]) -> "FilterClause":
        if not isinstance(payload, Mapping):
            raise ValidationError("Filter clause must be a mapping")
        column = _require_int(payload.get("column") or payload.get("columnIndex"), "column", minimum=0)
        operator = FilterOperator.parse(payload.get("operator"))
        value = payload.get("value")
        return cls(column=column, operator=operator, value=value)

    def model_dump(self, *, by_alias: bool = False) -> Dict[str, Any]:
        key = "column" if not by_alias else "column"
        return {key: self.column, "operator": self.operator.value, "value": self.value}


@dataclass(slots=True)
class DataQueryParams:
    sheet_id: Optional[int] = None
    page: int = 1
    page_size: int = 100
    sort_column: Optional[int] = None
    sort_direction: SortDirection = SortDirection.ASC
    filters: List[FilterClause] = field(default_factory=list)

    @classmethod
    def model_validate(cls, payload: Mapping[str, Any]) -> "DataQueryParams":
        if not isinstance(payload, Mapping):
            raise ValidationError("Query parameters must be a mapping")
        data: MutableMapping[str, Any] = dict(payload)
        sheet_id = payload.get("sheetId")
        parsed_sheet_id = _require_int(sheet_id, "sheetId", minimum=1, allow_none=True)
        page = _require_int(payload.get("page", 1), "page", minimum=1) or 1
        page_size = _require_int(payload.get("pageSize", 100), "pageSize", minimum=0) or 0
        sort_column_raw = payload.get("sortColumn")
        sort_column = _require_int(sort_column_raw, "sortColumn", minimum=0, allow_none=True)
        sort_direction = payload.get("sortDir", SortDirection.ASC)
        parsed_direction = SortDirection.parse(sort_direction)
        filters_payload = _require_list(payload.get("filters"), "filters")
        filters = []
        for item in filters_payload:
            if isinstance(item, FilterClause):
                filters.append(item)
            else:
                filters.append(FilterClause.model_validate(item))
        return cls(
            sheet_id=parsed_sheet_id,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_direction=parsed_direction,
            filters=filters,
        )

    def model_dump(self, *, by_alias: bool = False) -> Dict[str, Any]:
        data = {
            "sheetId": self.sheet_id,
            "page": self.page,
            "pageSize": self.page_size,
            "sortColumn": self.sort_column,
            "sortDir": self.sort_direction.value,
            "filters": [clause.model_dump(by_alias=by_alias) for clause in self.filters],
        }
        return data


@dataclass(slots=True)
class CellUpdate:
    row: int
    col: int
    value: Any = None

    @classmethod
    def model_validate(cls, payload: Mapping[str, Any]) -> "CellUpdate":
        if not isinstance(payload, Mapping):
            raise ValidationError("Cell update must be a mapping")
        row = _require_int(payload.get("row"), "row", minimum=0)
        col = _require_int(payload.get("col"), "col", minimum=0)
        value = payload.get("value")
        return cls(row=row, col=col, value=value)

    def model_dump(self, *, by_alias: bool = False) -> Dict[str, Any]:
        return {"row": self.row, "col": self.col, "value": self.value}


@dataclass(slots=True)
class DataWriteRequest:
    sheet_id: int
    updates: List[CellUpdate] = field(default_factory=list)
    row_count: Optional[int] = None
    col_count: Optional[int] = None

    @classmethod
    def model_validate(cls, payload: Mapping[str, Any]) -> "DataWriteRequest":
        if not isinstance(payload, Mapping):
            raise ValidationError("Request body must be a mapping")
        sheet_id = _require_int(payload.get("sheetId"), "sheetId", minimum=1)
        updates_payload = _require_list(payload.get("updates"), "updates")
        updates: List[CellUpdate] = []
        for item in updates_payload:
            if isinstance(item, CellUpdate):
                updates.append(item)
            elif isinstance(item, Mapping):
                updates.append(CellUpdate.model_validate(item))
        row_count = _require_int(payload.get("rowCount"), "rowCount", minimum=1, allow_none=True)
        col_count = _require_int(payload.get("colCount"), "colCount", minimum=1, allow_none=True)
        return cls(sheet_id=sheet_id, updates=updates, row_count=row_count, col_count=col_count)

    def model_dump(self, *, by_alias: bool = False) -> Dict[str, Any]:
        return {
            "sheetId": self.sheet_id,
            "updates": [update.model_dump(by_alias=by_alias) for update in self.updates],
            "rowCount": self.row_count,
            "colCount": self.col_count,
        }


@dataclass(slots=True)
class RowPayload:
    row_index: int
    values: List[str] = field(default_factory=list)

    def model_dump(self, *, by_alias: bool = False) -> Dict[str, Any]:
        key = "rowIndex" if by_alias else "row_index"
        return {key: self.row_index, "values": list(self.values)}


@dataclass(slots=True)
class DataResponse:
    sheet_id: int
    sheet_name: str
    row_count: int
    col_count: int
    page: int
    page_size: int
    total_rows: int
    rows: List[RowPayload] = field(default_factory=list)
    sheets: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def model_validate(cls, payload: Mapping[str, Any]) -> "DataResponse":
        if not isinstance(payload, Mapping):
            raise ValidationError("Response payload must be a mapping")
        sheet_id = _require_int(payload.get("sheetId"), "sheetId", minimum=1)
        sheet_name = payload.get("sheetName")
        if not isinstance(sheet_name, str):
            raise ValidationError("Field 'sheetName' must be a string")
        row_count = _require_int(payload.get("rowCount"), "rowCount", minimum=0)
        col_count = _require_int(payload.get("colCount"), "colCount", minimum=0)
        page = _require_int(payload.get("page"), "page", minimum=1)
        page_size = _require_int(payload.get("pageSize"), "pageSize", minimum=0)
        total_rows = _require_int(payload.get("totalRows"), "totalRows", minimum=0)
        rows_payload = _require_list(payload.get("rows"), "rows")
        rows = []
        for row in rows_payload:
            if isinstance(row, RowPayload):
                rows.append(row)
            elif isinstance(row, Mapping):
                row_index = _require_int(row.get("rowIndex"), "rowIndex", minimum=0)
                values = row.get("values", [])
                if not isinstance(values, Iterable):
                    raise ValidationError("Row values must be a list")
                rows.append(RowPayload(row_index=row_index, values=list(values)))
        sheets_payload = _require_list(payload.get("sheets"), "sheets")
        sheets: List[Dict[str, Any]] = []
        for sheet in sheets_payload:
            if isinstance(sheet, Mapping):
                sheets.append(dict(sheet))
        return cls(
            sheet_id=sheet_id,
            sheet_name=sheet_name,
            row_count=row_count,
            col_count=col_count,
            page=page,
            page_size=page_size,
            total_rows=total_rows,
            rows=rows,
            sheets=sheets,
        )

    def model_dump(self, *, by_alias: bool = False) -> Dict[str, Any]:
        data = {
            "sheetId": self.sheet_id,
            "sheetName": self.sheet_name,
            "rowCount": self.row_count,
            "colCount": self.col_count,
            "page": self.page,
            "pageSize": self.page_size,
            "totalRows": self.total_rows,
            "rows": [row.model_dump(by_alias=by_alias) for row in self.rows],
            "sheets": [dict(sheet) for sheet in self.sheets],
        }
        return data


@dataclass(slots=True)
class DataWriteResponse:
    sheet_id: int
    row_count: int
    col_count: int
    total_rows: int
    updated_cells: int

    @classmethod
    def model_validate(cls, payload: Mapping[str, Any]) -> "DataWriteResponse":
        if not isinstance(payload, Mapping):
            raise ValidationError("Response payload must be a mapping")
        sheet_id = _require_int(payload.get("sheetId"), "sheetId", minimum=1)
        row_count = _require_int(payload.get("rowCount"), "rowCount", minimum=0)
        col_count = _require_int(payload.get("colCount"), "colCount", minimum=0)
        total_rows = _require_int(payload.get("totalRows"), "totalRows", minimum=0)
        updated_cells = _require_int(payload.get("updatedCells"), "updatedCells", minimum=0)
        return cls(
            sheet_id=sheet_id,
            row_count=row_count,
            col_count=col_count,
            total_rows=total_rows,
            updated_cells=updated_cells,
        )

    def model_dump(self, *, by_alias: bool = False) -> Dict[str, Any]:
        return {
            "sheetId": self.sheet_id,
            "rowCount": self.row_count,
            "colCount": self.col_count,
            "totalRows": self.total_rows,
            "updatedCells": self.updated_cells,
        }


__all__ = [
    "CellUpdate",
    "DataQueryParams",
    "DataResponse",
    "DataWriteRequest",
    "DataWriteResponse",
    "FilterClause",
    "FilterOperator",
    "RowPayload",
    "SortDirection",
    "ValidationError",
]
