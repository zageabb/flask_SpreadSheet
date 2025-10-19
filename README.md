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

## Environment Variables
- `FLASK_APP=app:create_app` – required when using the Flask CLI to locate the factory.
- `FLASK_ENV=development` – optional flag to enable development features such as auto-reload.
- `FLASK_RUN_PORT` – optional port override for `flask run` (defaults to `5000`).

## Roadmap
- Improve frontend interactivity with richer spreadsheet behaviors (keyboard navigation, formulas, styling).
- Add authentication and per-user sheet isolation for collaborative scenarios.
- Ship containerization or deployment guides to streamline hosting.
- Extend the API with import/export endpoints for CSV or XLSX data.
