"""Database models for the spreadsheet application."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, String, func
from sqlmodel import Field, SQLModel


class Sheet(SQLModel, table=True):
    """Represents a spreadsheet document."""

    __tablename__ = "sheets"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String, unique=True, nullable=False))
    row_count: int = Field(nullable=False)
    col_count: int = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


class SheetCell(SQLModel, table=True):
    """Represents a single cell value within a sheet."""

    __tablename__ = "sheet_cells"

    sheet_id: int = Field(foreign_key="sheets.id", primary_key=True)
    row_index: int = Field(primary_key=True)
    col_index: int = Field(primary_key=True)
    value: Optional[str] = Field(default=None, nullable=True)

