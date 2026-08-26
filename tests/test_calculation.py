from sqlmodel import select

from app.models import SheetCell
from app.services.calculation import FormulaEngine
from app.services.database import get_session


def test_formula_engine_supports_references_ranges_and_functions():
    values = {"A1": 2, "A2": 3, "B1": 4}
    engine = FormulaEngine()
    assert engine.evaluate("=A1+B1*2", values.get) == 10
    assert engine.evaluate("=SUM(A1:A2)", values.get) == 5
    assert engine.evaluate('=IF(A1, "yes", "no")', values.get) == "yes"


def test_grid_write_recalculates_dependent_formulas(client, app):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]
    response = client.post("/api/grid", json={"sheetId": sheet_id, "updates": [
        {"row": 0, "col": 0, "value": "10"},
        {"row": 0, "col": 1, "value": "=A1*2"},
        {"row": 0, "col": 2, "value": "=B1+5"},
    ]})
    assert response.status_code == 200
    with app.app_context():
        cells = get_session().exec(select(SheetCell).where(SheetCell.sheet_id == sheet_id)).all()
        indexed = {(cell.row_index, cell.col_index): cell for cell in cells}
        assert indexed[(0, 1)].calculated_value == "20"
        assert indexed[(0, 2)].calculated_value == "25"


def test_calculation_reports_cycles(client, app):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]
    response = client.post("/api/grid", json={"sheetId": sheet_id, "updates": [
        {"row": 0, "col": 0, "value": "=B1"}, {"row": 0, "col": 1, "value": "=A1"},
    ]})
    assert response.status_code == 200
    result = client.post(f"/api/sheets/{sheet_id}/calculate").get_json()
    assert "#CYCLE!" in result["errors"].values()
