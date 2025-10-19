"""Pydantic schemas for spreadsheet API interactions."""
from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SortDirection(str, Enum):
    """Sort direction for sheet data."""

    ASC = "asc"
    DESC = "desc"


class FilterOperator(str, Enum):
    """Operators supported by data filters."""

    EQUAL = "eq"
    NOT_EQUAL = "ne"
    CONTAINS = "contains"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"


class FilterClause(BaseModel):
    """Individual filter applied to a column."""

    column: int = Field(alias="column", ge=0)
    operator: FilterOperator = Field(default=FilterOperator.EQUAL, alias="operator")
    value: Any = Field(default=None, alias="value")

    model_config = {
        "populate_by_name": True,
        "use_enum_values": True,
    }


class DataQueryParams(BaseModel):
    """Query parameters accepted by the data API."""

    sheet_id: Optional[int] = Field(default=None, alias="sheetId")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, alias="pageSize", ge=0)
    sort_column: Optional[int] = Field(default=None, alias="sortColumn", ge=0)
    sort_direction: SortDirection = Field(
        default=SortDirection.ASC, alias="sortDir"
    )
    filters: List[FilterClause] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "use_enum_values": True}


class CellUpdate(BaseModel):
    """Represents a single cell modification."""

    row: int = Field(ge=0)
    col: int = Field(ge=0)
    value: Any = Field(default=None)

    model_config = {"populate_by_name": True}


class DataWriteRequest(BaseModel):
    """Payload accepted by the data write endpoints."""

    sheet_id: int = Field(alias="sheetId", ge=1)
    updates: List[CellUpdate] = Field(default_factory=list)
    row_count: Optional[int] = Field(default=None, alias="rowCount", ge=1)
    col_count: Optional[int] = Field(default=None, alias="colCount", ge=1)

    model_config = {"populate_by_name": True}


class RowPayload(BaseModel):
    """Serialized representation of a row of data."""

    row_index: int = Field(alias="rowIndex", ge=0)
    values: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class DataResponse(BaseModel):
    """Response returned from the data read endpoint."""

    sheet_id: int = Field(alias="sheetId")
    sheet_name: str = Field(alias="sheetName")
    row_count: int = Field(alias="rowCount")
    col_count: int = Field(alias="colCount")
    page: int
    page_size: int = Field(alias="pageSize")
    total_rows: int = Field(alias="totalRows")
    rows: List[RowPayload] = Field(default_factory=list)
    sheets: List[dict] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class DataWriteResponse(BaseModel):
    """Response emitted after processing a data mutation."""

    sheet_id: int = Field(alias="sheetId")
    row_count: int = Field(alias="rowCount")
    col_count: int = Field(alias="colCount")
    total_rows: int = Field(alias="totalRows")
    updated_cells: int = Field(alias="updatedCells")

    model_config = {"populate_by_name": True}


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
]
