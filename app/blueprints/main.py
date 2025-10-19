import json
import sqlite3
from flask import Blueprint, abort, jsonify, render_template, request
from pydantic import ValidationError

from ..services import sheets as sheet_service
from .. import schemas


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
    except sqlite3.IntegrityError:
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
    except sqlite3.IntegrityError:
        abort(409, description="A sheet with that name already exists")

    return jsonify({"sheets": sheet_service.list_sheets(), "sheetId": sheet_id, "name": name}), 200


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
