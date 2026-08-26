"""SQLModel definitions for the spreadsheet domain objects."""
from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Return the current UTC time with timezone information."""

    return datetime.now(UTC)


class Workbook(SQLModel, table=True):
    """Top-level spreadsheet document containing one or more sheets."""

    __tablename__ = "workbooks"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str | None = Field(default=None, sa_column=sa.Column(sa.Text(), nullable=True))
    is_archived: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    updated_at: datetime = Field(default_factory=_utcnow, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), server_onupdate=sa.func.now()))


class Sheet(SQLModel, table=True):
    """ORM model representing a spreadsheet sheet."""

    __tablename__ = "sheets"
    __table_args__ = (sa.UniqueConstraint("workbook_id", "name", name="uq_sheets_workbook_name"),)

    id: int | None = Field(default=None, primary_key=True)
    workbook_id: int = Field(foreign_key="workbooks.id", index=True)
    name: str = Field(index=True)
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
    formula: str | None = Field(default=None, sa_column=sa.Column(sa.Text(), nullable=True))
    calculated_value: str | None = Field(default=None, sa_column=sa.Column(sa.Text(), nullable=True))
    value_type: str = Field(default="text", sa_column=sa.Column(sa.String(24), nullable=False, server_default="text"))
    number_format: str | None = Field(default=None, sa_column=sa.Column(sa.String(120), nullable=True))
    style_json: str = Field(default="{}", sa_column=sa.Column(sa.Text(), nullable=False, server_default="{}"))
    error: str | None = Field(default=None, sa_column=sa.Column(sa.String(32), nullable=True))
    updated_at: datetime = Field(default_factory=_utcnow, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), server_onupdate=sa.func.now()))


__all__ = ["Workbook", "Sheet", "SheetCell"]
