# Testing Strategy

## Tooling
- [pytest](https://pytest.org) drives the test suite.
- [coverage.py](https://coverage.readthedocs.io/) can be enabled via `pytest --cov=app --cov=tests` when tracking coverage locally.

## Test Suites
- **`tests/test_app.py`**: Exercises the Flask app factory, ensuring blueprints register and default sheets bootstrap correctly.
- **`tests/test_repository.py`**: Validates repository/service behaviours (listing sheets, CRUD operations, validation failures).
- **`tests/test_schemas.py`**: Confirms Pydantic schemas enforce typing and validation rules for API payloads.
- **`tests/test_import_export.py`**: Covers import preview parsing, confirmation workflows, and export endpoints.

## Running Tests
```bash
pytest
```

Use `pytest -k <pattern>` to focus on specific behaviours during development.

## Future Coverage
- Add end-to-end browser tests once the UI stabilises (e.g., Playwright) to cover AG Grid interactions.
- Capture regression scenarios for formula evaluation, background jobs, and caching as those features are introduced.

Update this document whenever new suites are added or the tooling stack changes.
