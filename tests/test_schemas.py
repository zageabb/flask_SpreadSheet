import pytest

from app.schemas import (
    CellUpdate,
    DataQueryParams,
    DataWriteRequest,
    FilterClause,
    FilterOperator,
    SortDirection,
    ValidationError,
)


def test_data_query_params_parses_and_normalizes_inputs():
    params = DataQueryParams.model_validate(
        {
            "sheetId": "5",
            "page": "2",
            "pageSize": "10",
            "sortColumn": "1",
            "sortDir": "DESC",
            "filters": [
                {"columnIndex": 0, "operator": "eq", "value": "Alice"},
                FilterClause(column=1, operator=FilterOperator.GREATER_THAN, value=100),
            ],
        }
    )

    assert params.sheet_id == 5
    assert params.page == 2
    assert params.page_size == 10
    assert params.sort_column == 1
    assert params.sort_direction is SortDirection.DESC
    assert len(params.filters) == 2
    assert params.filters[0].operator is FilterOperator.EQUAL
    assert params.filters[1].operator is FilterOperator.GREATER_THAN


def test_data_query_params_rejects_invalid_values():
    with pytest.raises(ValidationError):
        DataQueryParams.model_validate({"page": 0})

    with pytest.raises(ValidationError):
        DataQueryParams.model_validate({"sheetId": "abc"})

    with pytest.raises(ValidationError):
        DataQueryParams.model_validate({"sortDir": "sideways"})

    with pytest.raises(ValidationError):
        DataQueryParams.model_validate({"filters": "not-a-list"})


def test_data_write_request_converts_updates_to_models():
    request = DataWriteRequest.model_validate(
        {
            "sheetId": 3,
            "rowCount": 15,
            "colCount": 8,
            "updates": [
                {"row": 0, "col": 0, "value": "Hello"},
                CellUpdate(row=1, col=2, value="World"),
            ],
        }
    )

    assert request.sheet_id == 3
    assert request.row_count == 15
    assert request.col_count == 8
    assert len(request.updates) == 2
    assert all(isinstance(item, CellUpdate) for item in request.updates)


def test_data_write_request_requires_valid_dimensions():
    with pytest.raises(ValidationError):
        DataWriteRequest.model_validate({"sheetId": 1, "rowCount": 0, "updates": []})

    with pytest.raises(ValidationError):
        DataWriteRequest.model_validate({"sheetId": 1, "colCount": 0, "updates": []})
