# Flask Spreadsheet Architecture Notes

## Current Package Layout
- `app/` – Flask application package.
  - `app/__init__.py` exposes `create_app` and application wiring.
  - `app/blueprints/` contains the HTTP blueprint that serves HTML and JSON routes. `main.py` is the current feature surface.
  - `app/services/` hosts coarse-grained services and integrations.
    - `database.py` centralises SQLModel session handling.
    - `sheets.py` implements the sheet repository/service pair used by the API and views.
  - `app/models.py` defines SQLModel tables for `Sheet` and `SheetCell`.
  - `app/schemas.py` captures request/response validation via Pydantic models.
- `app.py` wires the application factory for CLI usage and ensures Alembic migrations run on start-up.
- `templates/` holds the Jinja templates rendered by the Flask blueprint (`index.html` bootstraps the spreadsheet UI).
- `static/` includes browser assets. `static/js/spreadsheet.js` encapsulates AG Grid orchestration and UI state. `static/css/styles.css` provides layout and theme styles.
- `alembic/` carries schema migration scripts managed by Alembic.
- `tests/` covers API behaviours, schema validation, repository logic, and import/export flows with pytest.

## Planned Architecture Direction
- **Grid component**: Continue standardising on [AG Grid] for the spreadsheet experience. Its virtualised rendering, CSV/XLSX utilities, and rich editing model meet current UX requirements while allowing future formula and validation improvements without re-writing core table plumbing.
- **Service boundaries**: Retain thin view/blueprint functions that delegate to service objects (`SheetService`, `SheetRepository`) for database interactions and business logic. Future additions (import pipelines, background jobs) should follow this pattern.
- **Data flows**:
  - Browser loads `index.html`, which embeds AG Grid, the initial sheet payload, and binds UI controls to `static/js/spreadsheet.js` handlers.
  - The script calls `/api/grid` to load the active sheet, applies edits locally, and issues POSTs back to `/api/grid` for persistence through the sheet service.
  - Sheet management actions (`/api/sheets`) flow through the same service layer so constraint handling and validation stay centralised.
  - Import/export workflows rely on temporary storage within the instance directory and use the sheet service to write normalised values.
- **Scalability targets**: As the feature set grows, background processing (for large imports/exports), caching of frequently accessed sheets, and websocket-style notifications are anticipated. These should integrate through dedicated services (e.g., `tasks/`, `cache/`) that sit alongside existing modules while keeping Flask views declarative.

[AG Grid]: https://www.ag-grid.com/
