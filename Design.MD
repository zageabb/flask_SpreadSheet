# Flask Spreadsheet Application

This project is a lightweight spreadsheet web application built with Flask.

## Features

- Persistent spreadsheet grids backed by SQLite with support for multiple named sheets.
- In-browser editing with a familiar table interface and column lettering.
- Automatic saving on cell blur, plus controls to add rows/columns, clear the sheet, duplicate sheets, and rename them.
- Status messaging to surface save progress and errors.

## Project Structure

- `app.py` – Flask application factory, database helpers, and API routes.
- `templates/index.html` – Base HTML page and spreadsheet layout.
- `static/js/spreadsheet.js` – Client-side logic for rendering, editing, and saving grid data.
- `static/css/styles.css` – Styling for the spreadsheet UI.
- `requirements.txt` – Python dependencies.
