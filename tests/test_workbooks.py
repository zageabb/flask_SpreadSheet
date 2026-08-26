from sqlmodel import select

from app.models import Sheet, SheetCell, Workbook
from app.services.database import get_session


def test_default_workbook_contains_initial_sheet(app):
    with app.app_context():
        session = get_session()
        workbook = session.exec(select(Workbook)).first()
        assert workbook is not None
        assert workbook.name == "My workbook"
        sheet = session.exec(select(Sheet).where(Sheet.workbook_id == workbook.id)).first()
        assert sheet is not None
        assert sheet.name == "Sheet 1"


def test_workbook_api_creates_workbook_with_sheet(client):
    response = client.post("/api/workbooks", json={"name": "Supplier analysis", "description": "Quotes"})
    assert response.status_code == 201
    workbook_id = response.get_json()["workbookId"]
    listing = client.get("/api/workbooks").get_json()["workbooks"]
    assert any(item["id"] == workbook_id and item["name"] == "Supplier analysis" for item in listing)


def test_cell_storage_identifies_formula_and_number(client, app):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]
    response = client.post(
        "/api/grid",
        json={"sheetId": sheet_id, "updates": [{"row": 0, "col": 0, "value": "12"}, {"row": 0, "col": 2, "value": "=A1*2"}]},
    )
    assert response.status_code == 200
    with app.app_context():
        session = get_session()
        number = session.get(SheetCell, (sheet_id, 0, 0))
        formula = session.get(SheetCell, (sheet_id, 0, 2))
        assert number.value_type == "number"
        assert formula.value_type == "formula"
        assert formula.formula == "=A1*2"
