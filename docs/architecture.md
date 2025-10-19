# System Architecture

## High-level Overview
- **Flask application package (`app/`)**: Provides the application factory (`create_app`), configuration, and blueprint registration. Request handling is centralised through `app/blueprints/main.py`.
- **Domain models (`app/models.py`)**: SQLModel tables (`Sheet`, `SheetCell`) map spreadsheet metadata and cell values into relational storage.
- **Schemas (`app/schemas.py`)**: Pydantic models validate inbound/outbound payloads (e.g., `DataWriteRequest`, `SheetMetadata`) and surface user-friendly validation errors.
- **Services (`app/services/`)**:
  - `database.py` exposes `get_session()` which yields SQLModel `Session` instances bound to the configured engine.
  - `sheets.py` composes a `SheetRepository` (SQL queries) and `SheetService` (business rules) that power all sheet operations.
- **Presentation layer**: `templates/index.html` renders the main UI while `static/js/spreadsheet.js` orchestrates client state, AG Grid integration, and API calls. CSS rules live in `static/css/styles.css`.
- **Infrastructure**: Alembic migrations inside `alembic/` keep the database schema aligned with the SQLModel definitions. Logging is configured via `logging.conf`.

## Request Flow
1. Incoming requests are routed through the `main` blueprint.
2. Blueprint functions parse query parameters or JSON bodies and delegate to `SheetService` for domain-specific logic.
3. Services interact with the repository layer to fetch or mutate data using SQLModel sessions obtained from `get_session()`.
4. Responses are serialised through Pydantic schemas where applicable before being returned to the client.

## Client Flow
1. The browser requests `/`, which serves `templates/index.html` including initial sheet context (`sheet_id`, `row_count`, `col_count`, `sheets`).
2. `static/js/spreadsheet.js` mounts AG Grid (Quartz theme) with the provided dimensions and binds toolbar buttons to helper functions.
3. UI events (cell edit, add row/column, clear sheet) mutate local state and batch persistence calls to `/api/grid`.
4. Sheet management actions hit `/api/sheets` endpoints and refresh the drop-down of available sheets.
5. Import/export features use modal workflows backed by `/api/import` and `/api/export/*` endpoints.

## Planned Evolution
- Encapsulate long-running tasks (e.g., large imports, scheduled exports) behind asynchronous workers to keep request latency predictable.
- Introduce caching for frequently accessed sheet metadata and read-heavy endpoints when multi-tenant performance requires it.
- Explore websocket push updates so concurrent editors stay in sync without manual refresh.
- Expand the services layer with explicit modules (e.g., `app/services/imports.py`, `app/services/exports.py`) as the domain grows.

When implementing new packages or integrations, document the updated flow here and link to the relevant module paths so contributors can locate the source quickly.
