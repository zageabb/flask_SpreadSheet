# Flask Spreadsheet

Flask Spreadsheet is a lightweight web application that mimics a spreadsheet interface. It provides CRUD operations on cells and sheet metadata backed by SQLModel/SQLite, exposes a browser UI powered by AG Grid, and offers JSON APIs for integrating the grid with other systems.

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

The default configuration stores data in `instance/spreadsheet.db`. Override with `DATABASE_URL` to use another SQLAlchemy-compatible database before launching the server.

## Architecture Summary
- **Application package (`app/`)** – Hosts the Flask factory, default configuration, and the `main` blueprint. Core modules include:
  - `models.py` for SQLModel table definitions and Alembic migration sources.
  - `schemas.py` for Pydantic request/response validation shared by blueprints and tests.
  - `services/database.py` for engine/session helpers and Alembic bootstrap logic.
  - `services/sheets.py` for the `SheetService`/`SheetRepository` pair handling CRUD, imports, exports, and validation rules.
- **Presentation layer** – `templates/index.html` seeds the UI with the active sheet; `static/js/spreadsheet.js` mounts AG Grid, wires toolbar actions, and synchronises edits back to the API; `static/css/styles.css` styles the layout.
- **Persistence** – Alembic migration scripts under `alembic/` evolve the schema; SQLModel sessions are scoped per request using helpers from `services/database.py`.
- **Testing** – Pytest suites in `tests/` cover the factory, services, schemas, and import/export workflows.
- **Documentation** – `/docs/` contains detailed references on architecture, API contracts, data lifecycle, testing, and operations.

Future enhancements (background jobs, caching, collaborative editing) should introduce dedicated service modules and be captured in `/docs/operations.md` so operational expectations stay in sync with the codebase.

## API Surface
| Method & Path | Description |
| --- | --- |
| `GET /` | Render the spreadsheet UI with the default sheet preloaded. |
| `GET /api/grid` | Fetch the active sheet metadata and cell matrix (optional `sheetId` query parameter). |
| `POST /api/grid` | Persist a batch of cell edits via a `DataWriteRequest`. |
| `GET /api/sheets` | List available sheets for selection menus. |
| `POST /api/sheets` | Create a new sheet with optional seed cells and explicit dimensions. |
| `PATCH /api/sheets/<sheet_id>` | Rename an existing sheet. |
| `POST /api/import` | Upload CSV/XLSX files and return preview metadata. |
| `POST /api/import/<preview_id>/confirm` | Commit a previously uploaded preview into a sheet. |
| `GET /api/export/csv` | Stream the current sheet as CSV. |
| `GET /api/export/xlsx` | Stream the current sheet as XLSX. |

Detailed request/response schemas live in [`docs/api-contracts.md`](docs/api-contracts.md).

## Front-end Behaviour
- Renders an AG Grid `ag-theme-quartz` table sized to the sheet dimensions embedded during initial render.
- Tracks cell edits locally for responsive UX before batching saves via `/api/grid`.
- Supports adding/removing rows and columns, clearing sheets, duplicating sheets, and renaming through toolbar controls wired to API endpoints.
- Handles CSV/XLSX import by presenting a preview modal, validating headers, and posting confirmed selections back through the service layer.
- Provides CSV/XLSX export links that stream files without a full page reload.
- Enables formula editing via the formula bar with support for arithmetic and comparison operators, cell ranges, and a curated set of spreadsheet functions.

Accessibility, richer keyboard interactions, and collaborative features remain active roadmap items.

## Documentation Index
Authoritative references live under [`docs/`](docs/README.md):
- [`architecture.md`](docs/architecture.md) – deeper dive on module boundaries and planned evolution.
- [`api-contracts.md`](docs/api-contracts.md) – endpoint payloads, validation rules, and response shapes.
- [`data-lifecycle.md`](docs/data-lifecycle.md) – creation/editing/import/export flows and observability notes.
- [`testing-strategy.md`](docs/testing-strategy.md) – suites, tooling, and future coverage goals.
- [`operations.md`](docs/operations.md) – migrations, background jobs, caching, and deployment checklists.
- [`formula-reference.md`](docs/formula-reference.md) – operators, functions, and usage tips for the formula engine.

Keep these documents updated whenever new capabilities or operational requirements land so stakeholders have a single source of truth.

## Operations & Deployment
- Database migrations run automatically at start-up; manual invocations use Alembic (`alembic upgrade head`).
- Document new background workers, caches, or scheduled jobs in [`docs/operations.md`](docs/operations.md) alongside the required environment variables and run commands.
- Ensure the `instance/` directory is writable for SQLite storage and import previews.

## Environment Variables
- `FLASK_APP=app:create_app` – used by the Flask CLI to locate the factory.
- `FLASK_ENV=development` – optional; enables auto-reload and debug tooling.
- `FLASK_RUN_PORT` – optional port override for `flask run` (defaults to `5000`).
- `DATABASE_URL` – optional SQLAlchemy connection string when not using the default SQLite database.

## Testing
Run the full suite with:
```bash
pytest
```
Use `pytest -k <pattern>` to focus on specific behaviours and add coverage for new modules as they are introduced.

## Roadmap
- Improve frontend interactivity with richer spreadsheet behaviours (keyboard navigation, formulas, styling).
- Add authentication and per-user sheet isolation for collaborative scenarios.
- Ship containerisation or deployment guides to streamline hosting.
- Introduce background processing and caching layers to support larger datasets and concurrent collaboration.
