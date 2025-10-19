import io
import json
import os
import secrets
from pathlib import Path

import pandas as pd
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
    session,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
from pydantic import ValidationError

from ..services import sheets as sheet_service
from .. import schemas


IMPORT_PREVIEW_KEY = "import_preview_id"
IMPORT_PREVIEW_DIRNAME = "import_previews"
IMPORT_PREVIEW_LIMIT = 20
MAX_IMPORT_ROWS = 10000
MAX_IMPORT_COLUMNS = 200


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    sheet_id, _, row_count, col_count, _ = sheet_service.fetch_sheet()
    sheets = sheet_service.list_sheets()
    return render_template(
        "index.html",
        row_count=row_count,
        col_count=col_count,
        sheet_id=sheet_id,
        sheets=sheets,
    )


@main_bp.route("/api/grid", methods=["GET"])
def get_grid():
    try:
        sheet_id = request.args.get("sheetId", type=int)
    except (TypeError, ValueError):
        sheet_id = None
    sheet_id, sheet_name, row_count, col_count, data = sheet_service.fetch_sheet(sheet_id)
    return jsonify(
        {
            "sheetId": sheet_id,
            "sheetName": sheet_name,
            "rowCount": row_count,
            "colCount": col_count,
            "cells": data,
            "sheets": sheet_service.list_sheets(),
        }
    )


@main_bp.route("/api/grid", methods=["POST"])
def save_grid():
    payload = request.get_json(silent=True) or {}
    try:
        request_model = schemas.DataWriteRequest.model_validate(payload)
    except ValidationError as exc:
        abort(400, description=str(exc))

    result = sheet_service.write_sheet_data(request_model)
    response_model = schemas.DataWriteResponse.model_validate(result)
    return jsonify(response_model.model_dump(by_alias=True)), 200


@main_bp.route("/api/sheets", methods=["GET"])
def get_sheets():
    return jsonify({"sheets": sheet_service.list_sheets()})


@main_bp.route("/api/sheets", methods=["POST"])
def create_sheet():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        abort(400, description="Sheet name is required")
    name = name.strip()
    row_count = payload.get("rowCount", 12)
    col_count = payload.get("colCount", 8)
    try:
        row_count = int(row_count)
        col_count = int(col_count)
    except (TypeError, ValueError):
        abort(400, description="Invalid row or column count")
    if row_count <= 0 or col_count <= 0:
        abort(400, description="Row and column counts must be positive")
    cells = payload.get("cells", [])

    try:
        sheet_id = sheet_service.create_sheet(name, row_count, col_count, cells)
    except IntegrityError:
        abort(409, description="A sheet with that name already exists")

    return (
        jsonify(
            {
                "sheetId": sheet_id,
                "rowCount": row_count,
                "colCount": col_count,
                "sheets": sheet_service.list_sheets(),
            }
        ),
        201,
    )


@main_bp.route("/api/sheets/<int:sheet_id>", methods=["PATCH"])
def rename_sheet(sheet_id: int):
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        abort(400, description="Sheet name is required")
    name = name.strip()

    try:
        sheet_service.rename_sheet(sheet_id, name)
    except IntegrityError:
        abort(409, description="A sheet with that name already exists")

    return jsonify({"sheets": sheet_service.list_sheets(), "sheetId": sheet_id, "name": name}), 200


def _column_label(index: int) -> str:
    if index < 0:
        return ""
    label = ""
    current = index
    while current >= 0:
        label = chr((current % 26) + 65) + label
        current = current // 26 - 1
    return label


def _get_preview_path(preview_id: str, *, ensure_dir: bool = False) -> Path:
    storage_dir = Path(current_app.instance_path) / IMPORT_PREVIEW_DIRNAME
    if ensure_dir:
        storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir / f"{preview_id}.json"


def _remove_preview(preview_id: str | None) -> None:
    if not preview_id:
        return
    try:
        _get_preview_path(preview_id).unlink(missing_ok=True)
    except OSError:
        pass


def _load_preview_payload(preview_id: str) -> dict:
    preview_path = _get_preview_path(preview_id)
    if not preview_path.exists():
        abort(400, description="Import preview is no longer available")
    try:
        data = json.loads(preview_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        abort(400, description=f"Unable to load preview data: {exc}")
    return data


def _safe_download_name(sheet_name: str, extension: str) -> str:
    base = secure_filename(sheet_name or "sheet")
    if not base:
        base = "sheet"
    return f"{base}.{extension}"


def _safe_excel_sheet_name(name: str) -> str:
    candidate = (name or "Sheet1").strip() or "Sheet1"
    for char in "[]:*?/\\":
        candidate = candidate.replace(char, " ")
    return candidate[:31]


def _sheet_to_dataframe(sheet_id: int | None) -> tuple[int, str, pd.DataFrame]:
    sheet_id, sheet_name, _row_count, col_count, data = sheet_service.fetch_sheet(sheet_id)
    columns = [_column_label(index) for index in range(col_count)]
    dataframe = pd.DataFrame(data, columns=columns)
    return sheet_id, sheet_name, dataframe


@main_bp.route("/import", methods=["POST"])
def import_sheet_data():
    file = request.files.get("file")
    if file is None or not file.filename:
        abort(400, description="A CSV or XLSX file is required")

    raw_sheet_id = request.form.get("sheetId")
    try:
        sheet_id = int(raw_sheet_id)
    except (TypeError, ValueError):
        abort(400, description="A valid sheetId is required")

    include_header_flag = request.form.get("includeHeader", "true")
    include_header = str(include_header_flag).strip().lower() not in {"false", "0", "no", "off"}

    sheet_id, sheet_name, _, _, _ = sheet_service.fetch_sheet(sheet_id)

    extension = os.path.splitext(file.filename)[1].lower()
    header_option = 0 if include_header else None

    try:
        if extension == ".csv":
            dataframe = pd.read_csv(file, header=header_option)
        elif extension == ".xlsx":
            dataframe = pd.read_excel(file, header=header_option, engine="openpyxl")
        else:
            abort(400, description="Unsupported file type. Upload a CSV or XLSX file.")
    except Exception as exc:  # pragma: no cover - pandas raises many subclasses
        abort(400, description=f"Failed to parse file: {exc}")

    normalized = dataframe.where(pd.notna(dataframe), "")
    row_count, col_count = normalized.shape
    if col_count == 0:
        abort(400, description="Imported file does not contain any columns")
    if row_count > MAX_IMPORT_ROWS:
        abort(400, description=f"Import is limited to {MAX_IMPORT_ROWS} rows")
    if col_count > MAX_IMPORT_COLUMNS:
        abort(400, description=f"Import is limited to {MAX_IMPORT_COLUMNS} columns")

    stringified = normalized.astype(str)
    headers = ["" if col is None else str(col) for col in stringified.columns]
    data_rows = [list(row) for row in stringified.itertuples(index=False, name=None)]

    preview_id = secrets.token_urlsafe(8)
    _remove_preview(session.get(IMPORT_PREVIEW_KEY))

    preview_payload = {
        "sheet_id": sheet_id,
        "include_header": include_header,
        "headers": headers,
        "rows": data_rows,
        "row_count": len(data_rows) + (1 if include_header else 0),
        "col_count": col_count,
    }
    preview_path = _get_preview_path(preview_id, ensure_dir=True)
    preview_path.write_text(json.dumps(preview_payload), encoding="utf-8")

    session[IMPORT_PREVIEW_KEY] = preview_id
    session.modified = True

    preview_rows = data_rows[:IMPORT_PREVIEW_LIMIT]
    truncated = len(data_rows) > IMPORT_PREVIEW_LIMIT
    display_headers = headers if include_header else [_column_label(index) for index in range(col_count)]

    source_name = os.path.basename(file.filename)

    return (
        jsonify(
            {
                "sheetId": sheet_id,
                "sheetName": sheet_name,
                "previewId": preview_id,
                "includeHeader": include_header,
                "headerRow": headers if include_header else [],
                "columns": display_headers,
                "previewRows": preview_rows,
                "totalRows": len(data_rows),
                "totalColumns": col_count,
                "truncated": truncated,
                "sourceName": source_name,
            }
        ),
        200,
    )


@main_bp.route("/import/confirm", methods=["POST"])
def confirm_import():
    payload = request.get_json(silent=True) or {}
    preview_id = payload.get("previewId")
    if not isinstance(preview_id, str) or not preview_id:
        abort(400, description="An import preview identifier is required")

    try:
        sheet_id = int(payload.get("sheetId"))
    except (TypeError, ValueError):
        abort(400, description="A valid sheetId is required")

    if session.get(IMPORT_PREVIEW_KEY) != preview_id:
        abort(400, description="Import preview has expired. Please upload the file again.")

    preview_payload = _load_preview_payload(preview_id)
    if int(preview_payload.get("sheet_id", 0)) != sheet_id:
        abort(400, description="Preview does not match the selected sheet")

    headers = preview_payload.get("headers") or []
    rows = preview_payload.get("rows") or []
    include_header = bool(preview_payload.get("include_header"))

    _, _, existing_row_count, existing_col_count, existing_data = sheet_service.fetch_sheet(sheet_id)

    updates: list[dict[str, object]] = []
    for row_index in range(existing_row_count):
        for col_index in range(existing_col_count):
            current_value = existing_data[row_index][col_index]
            if current_value:
                updates.append({"row": row_index, "col": col_index, "value": ""})

    grid_rows: list[list[str]] = []
    if include_header and headers:
        grid_rows.append(["" if value is None else str(value) for value in headers])
    for row in rows:
        str_row = ["" if value is None else str(value) for value in row]
        grid_rows.append(str_row)

    max_columns = max((len(row) for row in grid_rows), default=0)
    target_row_count = max(len(grid_rows), 1)
    target_col_count = max(max_columns, 1)

    for row_index, row in enumerate(grid_rows):
        for col_index, value in enumerate(row):
            if value == "":
                continue
            updates.append({"row": row_index, "col": col_index, "value": value})

    request_payload = {
        "sheetId": sheet_id,
        "updates": updates,
        "rowCount": target_row_count,
        "colCount": target_col_count,
    }

    try:
        request_model = schemas.DataWriteRequest.model_validate(request_payload)
    except ValidationError as exc:
        abort(400, description=str(exc))

    result = sheet_service.write_sheet_data(request_model)
    response_model = schemas.DataWriteResponse.model_validate(result)

    _remove_preview(preview_id)
    session.pop(IMPORT_PREVIEW_KEY, None)
    session.modified = True

    return jsonify(response_model.model_dump(by_alias=True)), 200


def _resolve_sheet_id_arg() -> int | None:
    sheet_param = request.args.get("sheetId")
    if sheet_param in (None, ""):
        return None
    try:
        return int(sheet_param)
    except (TypeError, ValueError):
        abort(400, description="Invalid sheetId")


@main_bp.route("/export.csv", methods=["GET"])
def export_csv():
    sheet_id = _resolve_sheet_id_arg()
    sheet_id, sheet_name, dataframe = _sheet_to_dataframe(sheet_id)

    buffer = io.StringIO()
    dataframe.to_csv(buffer, index=False)
    buffer.seek(0)

    filename = _safe_download_name(sheet_name, "csv")
    response = Response(buffer.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@main_bp.route("/export.xlsx", methods=["GET"])
def export_xlsx():
    sheet_id = _resolve_sheet_id_arg()
    sheet_id, sheet_name, dataframe = _sheet_to_dataframe(sheet_id)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name=_safe_excel_sheet_name(sheet_name))
    output.seek(0)

    filename = _safe_download_name(sheet_name, "xlsx")
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


def _parse_query_filters(raw_filters: str | None):
    if not raw_filters:
        return None
    try:
        parsed = json.loads(raw_filters)
    except json.JSONDecodeError as exc:
        abort(400, description=f"Invalid filters payload: {exc.msg}")
    return parsed


def _handle_data_write(payload: dict[str, object]):
    try:
        request_model = schemas.DataWriteRequest.model_validate(payload)
    except ValidationError as exc:
        abort(400, description=str(exc))

    result = sheet_service.write_sheet_data(request_model)
    response_model = schemas.DataWriteResponse.model_validate(result)
    return jsonify(response_model.model_dump(by_alias=True)), 200


@main_bp.route("/data", methods=["GET"])
def get_data():
    raw_filters = request.args.get("filters")
    filters = _parse_query_filters(raw_filters)
    payload = {
        "sheetId": request.args.get("sheetId"),
        "page": request.args.get("page"),
        "pageSize": request.args.get("pageSize"),
        "sortColumn": request.args.get("sortColumn"),
    }
    sort_dir = request.args.get("sortDir")
    if sort_dir is not None:
        payload["sortDir"] = sort_dir
    if filters is not None:
        payload["filters"] = filters
    try:
        params = schemas.DataQueryParams.model_validate(payload)
    except ValidationError as exc:
        abort(400, description=str(exc))

    result = sheet_service.query_sheet_data(params)
    response_model = schemas.DataResponse.model_validate(result)
    return jsonify(response_model.model_dump(by_alias=True))


@main_bp.route("/data", methods=["POST"])
def post_data():
    payload = request.get_json(silent=True) or {}
    return _handle_data_write(payload)


@main_bp.route("/data", methods=["PATCH"])
def patch_data():
    payload = request.get_json(silent=True) or {}
    return _handle_data_write(payload)
