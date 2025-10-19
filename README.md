# Flask Spreadsheet

Flask Spreadsheet is a lightweight web application that mimics a spreadsheet interface, providing CRUD operations on cells and sheet metadata backed by SQLite while exposing both a browser UI and JSON APIs for interacting with tabular data.

## Quickstart
1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the development server:
   ```bash
   flask --app app:create_app run
   ```

The default configuration uses `instance/spreadsheet.db` as the SQLite backing store. Set `DATABASE_URL` to point at a different SQLAlchemy-compatible database before launching the server to override it.

## Architecture Overview
- **Application package**: `app/` contains the Flask factory, SQLModel models, Pydantic schemas, and a `main` blueprint that serves HTML and JSON routes.
- **Service layer**: `app/services/` holds `SheetService` and `SheetRepository`, which encapsulate business rules and persistence. Blueprints convert HTTP payloads into service calls so validation stays centralised.
- **Presentation**: `templates/index.html` bootstraps the UI and preloads the active sheet. `static/js/spreadsheet.js` mounts an AG Grid instance, synchronises edits with the API, and orchestrates import/export flows.
- **Data access**: Alembic migrations under `alembic/` evolve the schema defined in `app/models.py`. `app/services/database.py` produces sessions scoped to the request lifecycle.
- **Testing**: Pytest suites in `tests/` cover service logic, schema validation, blueprint routes, and import/export behaviours.

Further background, contracts, and lifecycle diagrams live in [`docs/`](docs/README.md).

## API Routes
| Method & Path | Description |
| --- | --- |
| `GET /` | Render the AG Grid powered spreadsheet UI with the default sheet preloaded. |
| `GET /api/grid` | Fetch the active sheet's metadata and cell matrix. Optional `sheetId` query switches sheets. |
| `POST /api/grid` | Persist a batch of cell edits for the active sheet. Accepts a `DataWriteRequest` payload. |
| `GET /api/sheets` | List available sheets for the current tenant/database. |
| `POST /api/sheets` | Create a new sheet with optional seed cells and explicit dimensions. |
| `PATCH /api/sheets/<sheet_id>` | Rename an existing sheet. |
| `POST /api/import` | Upload a CSV/XLSX file, store a preview, and return preview metadata. |
| `POST /api/import/<preview_id>/confirm` | Commit a previously uploaded preview into the selected sheet. |
| `GET /api/export/csv` | Stream the current sheet as CSV. |
| `GET /api/export/xlsx` | Stream the current sheet as XLSX. |

See [`docs/api-contracts.md`](docs/api-contracts.md) for request/response schemas.

## Front-end Behaviour
- Renders an AG Grid `ag-theme-quartz` table sized according to the sheet dimensions supplied at page load.
- Tracks cell edits locally to provide responsive feedback before batching saves via `/api/grid`.
- Supports adding rows/columns, clearing sheets, duplicating sheets, and renaming via toolbar controls mapped to API endpoints.
- Handles CSV/XLSX import by showing a preview modal, validating headers, and posting confirmed selections back to the service layer.
- Provides CSV/XLSX export links that proxy to streaming endpoints without reloading the page.

Accessibility and usability improvements (keyboard navigation, formula helpers, responsive layout) remain active workstreams.

## Operations & Deployment
- Database migrations run automatically at start-up; manual invocations use Alembic (`alembic upgrade head`).
- Keep the [`docs/operations.md`](docs/operations.md) guide updated when introducing background jobs, caching, or other infrastructure changes so deployment instructions stay current.

## Environment Variables
- `FLASK_APP=app:create_app` – required when using the Flask CLI to locate the factory.
- `FLASK_ENV=development` – optional flag to enable development features such as auto-reload.
- `FLASK_RUN_PORT` – optional port override for `flask run` (defaults to `5000`).

## Roadmap
- Improve frontend interactivity with richer spreadsheet behaviours (keyboard navigation, formulas, styling).
- Add authentication and per-user sheet isolation for collaborative scenarios.
- Ship containerization or deployment guides to streamline hosting.
- Introduce background processing and caching layers to support larger datasets and concurrent collaboration.
