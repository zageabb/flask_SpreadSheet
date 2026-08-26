import io

from app.services.data import TransformationService


def test_csv_data_source_can_refresh_sheet(client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]
    created = client.post(
        "/api/data-sources",
        data={"sheetId": str(sheet_id), "kind": "csv", "options": "{}", "file": (io.BytesIO(b"Supplier,Price\nAlpha,10\nBeta,20\n"), "quotes.csv")},
        content_type="multipart/form-data",
    )
    assert created.status_code == 201
    source_id = created.get_json()["id"]
    refreshed = client.post(f"/api/data-sources/{source_id}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.get_json()["refreshedRows"] == 2
    grid = client.get(f"/api/grid?sheetId={sheet_id}").get_json()["cells"]
    assert grid[:3] == [["Supplier", "Price"], ["Alpha", "10"], ["Beta", "20"]]


def test_repeatable_transformations():
    rows = [{"Supplier": "Alpha", "Price": 10}, {"Supplier": "Beta", "Price": None}, {"Supplier": "Alpha", "Price": 10}]
    result = TransformationService().apply(rows, [
        {"type": "fill_null", "column": "Price", "value": 0},
        {"type": "deduplicate", "columns": ["Supplier", "Price"]},
        {"type": "sort", "column": "Price", "descending": True},
    ])
    assert result == [{"Supplier": "Alpha", "Price": 10}, {"Supplier": "Beta", "Price": 0}]


def test_transform_endpoint_previews_without_applying(client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]
    client.post("/api/grid", json={"sheetId": sheet_id, "updates": [
        {"row": 0, "col": 0, "value": "Name"},
        {"row": 1, "col": 0, "value": "A"},
        {"row": 2, "col": 0, "value": "B"},
    ]})
    response = client.post(f"/api/sheets/{sheet_id}/transform", json={"operations": [{"type": "filter", "column": "Name", "value": "A"}]})
    assert response.status_code == 200
    assert response.get_json()["preview"][0]["Name"] == "A"
    assert response.get_json()["applied"] is False
