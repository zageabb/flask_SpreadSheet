import json


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
            "rowCount": 3,
            "colCount": 3,
            "updates": [
                {"row": 0, "col": 0, "value": "Alice"},
                {"row": 0, "col": 1, "value": 100},
                {"row": 1, "col": 0, "value": "Bob"},
                {"row": 1, "col": 1, "value": 250},
                {"row": 2, "col": 0, "value": "Charlie"},
                {"row": 2, "col": 1, "value": 175},
            ],
        },
    )

    assert patch_response.status_code == 200

    page_one = client.get(
        "/data",
        query_string={
            "sheetId": sheet_id,
            "page": 1,
            "pageSize": 2,
            "sortColumn": 1,
            "sortDir": "desc",
        },
    ).get_json()

    assert page_one["totalRows"] == 3
    assert len(page_one["rows"]) == 2
    assert page_one["rows"][0]["rowIndex"] == 1
    assert page_one["rows"][0]["values"][0] == "Bob"
    assert page_one["rows"][1]["rowIndex"] == 2

    page_two = client.get(
        "/data",
        query_string={
            "sheetId": sheet_id,
            "page": 2,
            "pageSize": 2,
            "sortColumn": 1,
            "sortDir": "desc",
        },
    ).get_json()

    assert page_two["totalRows"] == 3
    assert len(page_two["rows"]) == 1
    assert page_two["rows"][0]["rowIndex"] == 0

    filters = json.dumps([{ "column": 1, "operator": "gt", "value": 200 }])
    filtered = client.get(
        "/data",
        query_string={"sheetId": sheet_id, "page": 1, "pageSize": 0, "filters": filters},
    ).get_json()

    assert filtered["totalRows"] == 1
    assert filtered["rows"][0]["rowIndex"] == 1


def test_data_endpoint_returns_validation_errors(client):
    response = client.get(
        "/data",
        query_string={"page": 0},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "bad_request"
    assert "page" in payload["message"]

    filters_response = client.get(
        "/data",
        query_string={"filters": "not-json"},
        headers={"Accept": "application/json"},
    )

    assert filters_response.status_code == 400
    filters_payload = filters_response.get_json()
    assert "filters" in filters_payload["message"].lower()


def test_formula_cells_roundtrip_via_grid_and_data(client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]

    patch_response = client.patch(
        "/data",
        json={
            "sheetId": sheet_id,
            "updates": [
                {"row": 0, "col": 0, "value": "=B1+C1"},
                {"row": 0, "col": 1, "value": 5},
                {"row": 0, "col": 2, "value": 7},
            ],
        },
    )

    assert patch_response.status_code == 200

    grid = client.get("/api/grid", query_string={"sheetId": sheet_id}).get_json()
    assert grid["cells"][0][0] == "=B1+C1"
    assert grid["cells"][0][1] == "5"
    assert grid["cells"][0][2] == "7"

    data_page = client.get(
        "/data",
        query_string={"sheetId": sheet_id, "page": 1, "pageSize": 1},
    ).get_json()

    assert data_page["rows"][0]["values"][0] == "=B1+C1"
    assert data_page["rows"][0]["values"][1] == "5"


def test_numeric_validation_enforced(client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]

    invalid = client.patch(
        "/data",
        json={"sheetId": sheet_id, "updates": [{"row": 0, "col": 1, "value": "not-a-number"}]},
    )

    assert invalid.status_code == 400
