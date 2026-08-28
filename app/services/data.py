"""Safe refreshable connectors and repeatable table transformations."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, BinaryIO

from sqlmodel import Session, select

from ..models import DataSource
from .calculation import CalculationService
from .sheets import SheetRepository, SheetService


class DataServiceError(ValueError): pass


class DataSourceService:
    def __init__(self, session: Session, root: Path) -> None:
        self.session = session; self.root = root.resolve(); self.root.mkdir(parents=True, exist_ok=True)

    def register_upload(self, sheet_id: int, name: str, kind: str, stream: BinaryIO, options: dict[str, Any] | None = None) -> DataSource:
        if kind not in {"csv", "sqlite"}: raise DataServiceError("Only CSV and SQLite sources are supported")
        if SheetRepository(self.session).get_sheet(sheet_id) is None: raise DataServiceError("Sheet not found")
        source = DataSource(sheet_id=sheet_id, name=name, kind=kind, stored_path="", options_json=json.dumps(options or {}))
        suffix = ".csv" if kind == "csv" else ".sqlite"
        target = self.root / f"{source.id}{suffix}"
        with target.open("wb") as handle:
            while chunk := stream.read(1024 * 1024): handle.write(chunk)
        source.stored_path = str(target); self.session.add(source); self.session.commit(); self.session.refresh(source)
        return source

    def list(self, sheet_id: int | None = None) -> list[DataSource]:
        query = select(DataSource)
        if sheet_id is not None: query = query.where(DataSource.sheet_id == sheet_id)
        return list(self.session.exec(query.order_by(DataSource.created_at.desc())))

    def refresh(self, source_id: str) -> int:
        source = self.session.get(DataSource, source_id)
        if source is None: raise LookupError("Data source not found")
        path = Path(source.stored_path).resolve()
        if self.root not in path.parents or not path.is_file(): raise DataServiceError("Data source file is unavailable")
        options = json.loads(source.options_json or "{}")
        rows = _load_csv(path, options) if source.kind == "csv" else _load_sqlite(path, options)
        service = SheetService(SheetRepository(self.session))
        _, _, old_rows, old_cols, existing = service.fetch_sheet(source.sheet_id)
        updates = [{"row": r, "col": c, "value": ""} for r in range(old_rows) for c in range(old_cols) if existing[r][c]]
        if rows:
            headers = list(rows[0]); matrix = [headers] + [[row.get(header) for header in headers] for row in rows]
        else: matrix = [[]]
        for r, row in enumerate(matrix):
            for c, value in enumerate(row):
                if value not in (None, ""): updates.append({"row": r, "col": c, "value": str(value)})
        service.update_dimensions(source.sheet_id, max(1, len(matrix)), max(1, max((len(row) for row in matrix), default=1)))
        service.apply_updates(source.sheet_id, updates, validate=False); CalculationService(self.session).recalculate_sheet(source.sheet_id)
        source.last_refreshed_at = datetime.now(timezone.utc); self.session.add(source); self.session.commit()
        return len(rows)


class TransformationService:
    def apply(self, rows: list[dict[str, Any]], operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = [dict(row) for row in rows]
        for operation in operations:
            kind = operation.get("type")
            if kind == "filter":
                column, value = operation.get("column"), operation.get("value")
                result = [row for row in result if row.get(column) == value]
            elif kind == "sort":
                column = operation.get("column"); result.sort(key=lambda row: (row.get(column) is None, row.get(column)), reverse=bool(operation.get("descending")))
            elif kind == "fill_null":
                column, value = operation.get("column"), operation.get("value"); result = [{**row, column: value if row.get(column) in (None, "") else row.get(column)} for row in result]
            elif kind == "rename":
                before, after = operation.get("column"), operation.get("name"); result = [{(after if key == before else key): value for key, value in row.items()} for row in result]
            elif kind == "deduplicate":
                columns = operation.get("columns") or []; seen = set(); unique = []
                for row in result:
                    key = tuple(row.get(column) for column in columns)
                    if key not in seen: seen.add(key); unique.append(row)
                result = unique
            elif kind == "select":
                columns = operation.get("columns") or []; result = [{column: row.get(column) for column in columns} for row in result]
            else: raise DataServiceError(f"Unsupported transformation: {kind}")
        return result


def _load_csv(path: Path, options: dict[str, Any]) -> list[dict[str, Any]]:
    with path.open("r", encoding=options.get("encoding", "utf-8-sig"), newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter=options.get("delimiter", ","))]


def _load_sqlite(path: Path, options: dict[str, Any]) -> list[dict[str, Any]]:
    table = str(options.get("table", ""))
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table): raise DataServiceError("A safe SQLite table name is required")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True); connection.row_factory = sqlite3.Row
    try: return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}" LIMIT 100000').fetchall()]
    finally: connection.close()


def serialize_source(source: DataSource) -> dict[str, Any]:
    return {"id": source.id, "sheetId": source.sheet_id, "name": source.name, "kind": source.kind, "options": json.loads(source.options_json), "lastRefreshedAt": source.last_refreshed_at.isoformat() if source.last_refreshed_at else None}
