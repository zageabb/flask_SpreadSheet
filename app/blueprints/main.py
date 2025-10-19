import sqlite3
from flask import Blueprint, abort, jsonify, render_template, request

from ..services.database import get_db
from ..services import sheets as sheet_service


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
    updates = payload.get("updates", [])
    new_row_count = payload.get("rowCount")
    new_col_count = payload.get("colCount")
    sheet_id = payload.get("sheetId")
    if not isinstance(sheet_id, int):
        abort(400, description="sheetId is required")

    db = get_db()
    sheet = db.execute("SELECT id FROM sheets WHERE id = ?", (sheet_id,)).fetchone()
    if sheet is None:
        abort(404, description="Sheet not found")
    sheet_service.update_dimensions(sheet_id, new_row_count, new_col_count)
    sheet_service.apply_updates(sheet_id, updates)

    sheet_id, _, row_count, col_count, _ = sheet_service.fetch_sheet(sheet_id)
    return jsonify({"sheetId": sheet_id, "rowCount": row_count, "colCount": col_count}), 200


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
