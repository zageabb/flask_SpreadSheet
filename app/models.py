"""SQLModel definitions for the spreadsheet domain objects."""
from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Return the current UTC time with timezone information."""

    return datetime.now(UTC)


class Sheet(SQLModel, table=True):
    """ORM model representing a spreadsheet sheet."""

    __tablename__ = "sheets"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    row_count: int
    col_count: int
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
    )


class SheetCell(SQLModel, table=True):
    """ORM model representing a single cell within a sheet."""

    __tablename__ = "sheet_cells"

    sheet_id: int = Field(foreign_key="sheets.id", primary_key=True)
    row_index: int = Field(primary_key=True)
    col_index: int = Field(primary_key=True)
    value: str | None = Field(
        default=None,
        sa_column=sa.Column(sa.Text(), nullable=True),
    )


__all__ = ["Sheet", "SheetCell"]
