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

## Database migrations
The project uses Alembic together with SQLModel/SQLAlchemy models for schema management.
The Flask application automatically applies pending migrations during startup, but when deploying
or running management workflows you can apply them explicitly with:
```bash
export DATABASE_URL=sqlite:///$(pwd)/instance/spreadsheet.db
alembic upgrade head
```
The `DATABASE_URL` can point to any supported SQLAlchemy URL. When evolving the schema,
create new revisions with:
```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Environment Variables
- `FLASK_APP=app:create_app` – required when using the Flask CLI to locate the factory.
- `FLASK_ENV=development` – optional flag to enable development features such as auto-reload.
- `FLASK_RUN_PORT` – optional port override for `flask run` (defaults to `5000`).

## Roadmap
- Improve frontend interactivity with richer spreadsheet behaviors (keyboard navigation, formulas, styling).
- Add authentication and per-user sheet isolation for collaborative scenarios.
- Ship containerization or deployment guides to streamline hosting.
- Extend the API with import/export endpoints for CSV or XLSX data.
