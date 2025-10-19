import io
from pathlib import Path

from app.blueprints.main import IMPORT_PREVIEW_DIRNAME, IMPORT_PREVIEW_KEY


def test_import_preview_and_confirm_flow(client, app):
    with client as test_client:
        sheet_id = test_client.get("/api/grid").get_json()["sheetId"]

        csv_content = b"Alpha,123\nBeta,456\n"
        response = test_client.post(
            "/import",
            data={
                "sheetId": str(sheet_id),
                "includeHeader": "false",
                "file": (io.BytesIO(csv_content), "sample.csv"),
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        preview_payload = response.get_json()
        preview_id = preview_payload["previewId"]
        assert preview_payload["totalRows"] == 2
        assert preview_payload["columns"] == ["A", "B"]

        preview_path = Path(app.instance_path) / IMPORT_PREVIEW_DIRNAME / f"{preview_id}.json"
        assert preview_path.exists()

        confirm_response = test_client.post(
            "/import/confirm",
            json={"sheetId": sheet_id, "previewId": preview_id},
        )

        assert confirm_response.status_code == 200
        confirm_payload = confirm_response.get_json()
        assert confirm_payload["rowCount"] == 2
        assert confirm_payload["updatedCells"] == 4

        grid = test_client.get("/api/grid", query_string={"sheetId": sheet_id}).get_json()
        assert grid["cells"][0][0] == "Alpha"
        assert grid["cells"][0][1] == "123"
        assert grid["cells"][1][0] == "Beta"

        with test_client.session_transaction() as session_state:
            assert IMPORT_PREVIEW_KEY not in session_state

        assert not preview_path.exists()


def test_export_routes_return_expected_payloads(client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]
    client.patch(
        "/data",
        json={
            "sheetId": sheet_id,
            "updates": [
                {"row": 0, "col": 0, "value": "Label"},
                {"row": 0, "col": 1, "value": 10},
                {"row": 1, "col": 0, "value": "Other"},
                {"row": 1, "col": 1, "value": 20},
            ],
        },
    )

    csv_response = client.get("/export.csv", query_string={"sheetId": sheet_id})
    assert csv_response.status_code == 200
    assert csv_response.mimetype == "text/csv"
    assert "attachment; filename=" in csv_response.headers["Content-Disposition"]

    csv_lines = csv_response.data.decode("utf-8").strip().splitlines()
    assert csv_lines[0].startswith("A,")
    assert csv_lines[1].split(",")[0] == "Label"

    xlsx_response = client.get("/export.xlsx", query_string={"sheetId": sheet_id})
    assert xlsx_response.status_code == 200
    assert "attachment; filename=" in xlsx_response.headers["Content-Disposition"]
    assert xlsx_response.data[:2] == b"PK"
    assert len(xlsx_response.data) > 100
