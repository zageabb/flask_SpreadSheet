# Flask Spreadsheet Design Digest

## Package Layout
- `app/` – Flask application package and configuration.
  - `__init__.py` – application factory that wires blueprints, config, and database session lifecycle.
  - `config.py` – default settings and environment overrides.
  - `blueprints/` – HTTP entrypoints. `main.py` renders HTML, exposes JSON APIs, and orchestrates import/export flows.
  - `services/` – coarse-grained business services.
    - `database.py` – engine/session helpers plus Alembic bootstrap utilities.
    - `sheets.py` – `SheetService`/`SheetRepository` pair that encapsulates sheet CRUD, cell writes, and import/export helpers.
  - `models.py` – SQLModel tables for `Sheet`/`SheetCell` persisted via Alembic migrations.
  - `schemas.py` – Pydantic request/response models shared across blueprints and tests.
- `templates/` – Jinja templates rendered by the blueprint. `index.html` bootstraps the spreadsheet view layer.
- `static/` – Front-end assets (`js/spreadsheet.js`, `css/styles.css`) that mount and style the grid component.
- `alembic/` – Database migration environment and generated revisions.
- `tests/` – Pytest suites covering the factory, services, schemas, and import/export integrations.
- `/docs/` – Deeper references covering API contracts, data lifecycle, testing strategy, and operations guidance.

## Planned Architecture Direction
- **Grid component**: AG Grid remains the primary spreadsheet surface for its virtualised rendering, CSV/XLSX helpers, and rich editing APIs. Custom behaviour (toolbar actions, validation) layers on top of its event hooks without forking core rendering.
- **Service boundaries**: Continue funnelling business rules through `SheetService` and collaborating repositories. New capabilities (imports, exports, background jobs, caching) should expose explicit service modules (`app/services/imports.py`, etc.) so blueprints stay thin.
- **Data flows**:
  1. Browser requests `/` and receives `templates/index.html` with initial sheet metadata embedded in the page payload.
  2. `static/js/spreadsheet.js` mounts AG Grid, seeds it with the provided data, and listens for toolbar/UI events.
  3. UI events emit JSON calls to `/api/grid` or `/api/sheets`; payloads are validated via `schemas.py` before reaching services.
  4. Services persist state through SQLModel sessions managed by `database.py` and surface responses back through schemas.
  5. Import/export routes stream files through the same service layer, storing previews in `instance/` and writing normalised values back into the database.
- **Scalability roadmap**: Anticipate background workers for long-running imports/exports, caching layers for frequently accessed sheets, and websocket-style notifications to keep multiple clients in sync. Each addition should be documented under `/docs/operations.md` and linked services should live alongside existing modules.
