"""Lightweight data models used by the spreadsheet services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _parse_datetime(value: Any) -> datetime:
    """Parse a database timestamp into a :class:`datetime` instance."""

    if isinstance(value, datetime):
        return value
    if value in (None, ""):
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            if fmt is None:
                return datetime.fromisoformat(text)
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Sheet:
    """Representation of a sheet record."""

    id: int
    name: str
    row_count: int
    col_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Any) -> "Sheet":
        return cls(
            id=row["id"],
            name=row["name"],
            row_count=row["row_count"],
            col_count=row["col_count"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )


@dataclass(slots=True)
class SheetCell:
    """Representation of a sheet cell record."""

    sheet_id: int
    row_index: int
    col_index: int
    value: str | None

    @classmethod
    def from_row(cls, row: Any) -> "SheetCell":
        return cls(
            sheet_id=row["sheet_id"],
            row_index=row["row_index"],
            col_index=row["col_index"],
            value=row["value"],
        )


__all__ = ["Sheet", "SheetCell"]
