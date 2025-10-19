import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:  # pragma: no cover - guard for optional dependency
    import dotenv  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    sys.modules["dotenv"] = SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)

from app import create_app


@pytest.fixture()
def app(monkeypatch):
    database_name = f"test_{uuid4().hex}.db"
    monkeypatch.setenv("DATABASE_NAME", database_name)
    monkeypatch.setenv("LOGGING_CONFIG", "")

    app = create_app("development")
    app.config.update(TESTING=True)

    templates_path = PROJECT_ROOT / "templates"
    if app.jinja_loader and str(templates_path) not in app.jinja_loader.searchpath:
        app.jinja_loader.searchpath.insert(0, str(templates_path))

    yield app

    db_path = Path(app.config["DATABASE_PATH"])
    if db_path.exists():
        db_path.unlink()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_index_page_renders_initial_sheet(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Flask Spreadsheet" in response.data
    assert b"Sheet 1" in response.data


def test_create_sheet_and_fetch_grid(client):
    create_response = client.post(
        "/api/sheets",
        json={"name": "Budget", "rowCount": 5, "colCount": 4},
    )

    assert create_response.status_code == 201
    payload = create_response.get_json()
    new_sheet_id = payload["sheetId"]

    grid_response = client.get("/api/grid", query_string={"sheetId": new_sheet_id})

    assert grid_response.status_code == 200
    grid = grid_response.get_json()
    assert grid["sheetId"] == new_sheet_id
    assert grid["rowCount"] == 5
    assert grid["colCount"] == 4


def test_update_grid_applies_changes(client):
    initial_grid = client.get("/api/grid").get_json()
    sheet_id = initial_grid["sheetId"]

    update_response = client.post(
        "/api/grid",
        json={
            "sheetId": sheet_id,
            "rowCount": 6,
            "colCount": 3,
            "updates": [
                {"row": 0, "col": 0, "value": "Hello"},
                {"row": 2, "col": 1, "value": "42"},
            ],
        },
    )

    assert update_response.status_code == 200
    updated = update_response.get_json()
    assert updated["rowCount"] == 6
    assert updated["colCount"] == 3

    refreshed = client.get("/api/grid", query_string={"sheetId": sheet_id}).get_json()
    assert refreshed["rowCount"] == 6
    assert refreshed["colCount"] == 3

    assert initial_grid["cells"][0][0] == ""
    assert refreshed["cells"][0][0] == "Hello"
    assert refreshed["cells"][2][1] == "42"


def test_data_endpoint_supports_paging_and_filters(client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]

    patch_response = client.patch(
        "/data",
        json={
            "sheetId": sheet_id,
            "updates": [
                {"row": 0, "col": 0, "value": "Alice"},
                {"row": 0, "col": 1, "value": 100},
                {"row": 1, "col": 0, "value": "Bob"},
                {"row": 1, "col": 1, "value": 250},
            ],
        },
    )

    assert patch_response.status_code == 200

    page_one = client.get(
        "/data",
        query_string={"sheetId": sheet_id, "page": 1, "pageSize": 1, "sortColumn": 1, "sortDir": "desc"},
    ).get_json()

    assert page_one["totalRows"] >= 2
    assert len(page_one["rows"]) == 1
    assert page_one["rows"][0]["rowIndex"] == 1

    filters = json.dumps([{ "column": 1, "operator": "gt", "value": 150 }])
    filtered = client.get(
        "/data",
        query_string={"sheetId": sheet_id, "page": 1, "pageSize": 0, "filters": filters},
    ).get_json()

    assert filtered["totalRows"] == 1
    assert filtered["rows"][0]["rowIndex"] == 1


def test_numeric_validation_enforced(client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]

    invalid = client.patch(
        "/data",
        json={"sheetId": sheet_id, "updates": [{"row": 0, "col": 1, "value": "not-a-number"}]},
    )

    assert invalid.status_code == 400
