from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.models import SheetCell
from app.schemas import DataQueryParams, FilterClause, FilterOperator, SortDirection
from app.services.sheets import SheetRepository, SheetService


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture()
def repository(session):
    return SheetRepository(session)


def _populate_sheet(repository: SheetRepository):
    sheet = repository.add_sheet("Analysis", 3, 4)
    repository.upsert_cell(sheet.id, 0, 0, "Alice")
    repository.upsert_cell(sheet.id, 0, 1, "100")
    repository.upsert_cell(sheet.id, 1, 0, "Bob")
    repository.upsert_cell(sheet.id, 1, 1, "50")
    repository.upsert_cell(sheet.id, 2, 0, "Charlie")
    repository.upsert_cell(sheet.id, 2, 1, "200")
    repository.commit()
    return sheet


def test_upsert_cell_creates_updates_and_deletes(repository):
    sheet = repository.add_sheet("Sample", 4, 4)
    repository.commit()

    repository.upsert_cell(sheet.id, 0, 0, "42")
    stored = repository.session.get(SheetCell, (sheet.id, 0, 0))
    assert stored is not None
    assert stored.value == "42"

    repository.upsert_cell(sheet.id, 0, 0, "45")
    updated = repository.session.get(SheetCell, (sheet.id, 0, 0))
    assert updated.value == "45"

    repository.upsert_cell(sheet.id, 0, 0, "")
    assert repository.session.get(SheetCell, (sheet.id, 0, 0)) is None


def test_query_sheet_data_applies_sorting_and_pagination(repository):
    sheet = _populate_sheet(repository)
    service = SheetService(repository)

    params = DataQueryParams(
        sheet_id=sheet.id,
        page=1,
        page_size=2,
        sort_column=1,
        sort_direction=SortDirection.DESC,
        filters=[],
    )

    result = service.query_sheet_data(params)

    assert result["totalRows"] == 3
    assert [row["rowIndex"] for row in result["rows"]] == [2, 0]

    params_second_page = DataQueryParams(
        sheet_id=sheet.id,
        page=2,
        page_size=2,
        sort_column=1,
        sort_direction=SortDirection.DESC,
        filters=[],
    )

    second_page = service.query_sheet_data(params_second_page)

    assert second_page["totalRows"] == 3
    assert [row["rowIndex"] for row in second_page["rows"]] == [1]


def test_query_sheet_data_filters_numeric_columns(repository):
    sheet = _populate_sheet(repository)
    service = SheetService(repository)

    params = DataQueryParams(
        sheet_id=sheet.id,
        page=1,
        page_size=0,
        sort_column=None,
        sort_direction=SortDirection.ASC,
        filters=[FilterClause(column=1, operator=FilterOperator.GREATER_THAN, value=Decimal("150"))],
    )

    result = service.query_sheet_data(params)

    assert result["totalRows"] == 1
    assert result["rows"][0]["values"][0] == "Charlie"
