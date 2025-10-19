# API Contracts

All endpoints live under the `main` blueprint (`app/blueprints/main.py`). JSON payloads are validated through Pydantic models defined in `app/schemas.py`.

## `/api/grid`
### `GET`
- **Query parameters**: `sheetId` (optional `int`) selects a sheet. When omitted, the first sheet is returned.
- **Response** (`200 OK`):
  ```json
  {
    "sheetId": 1,
    "sheetName": "Sheet 1",
    "rowCount": 12,
    "colCount": 8,
    "cells": [["value", ""], ...],
    "sheets": [
      {"id": 1, "name": "Sheet 1"},
      {"id": 2, "name": "Budget"}
    ]
  }
  ```

### `POST`
- **Request body** (`DataWriteRequest`):
  ```json
  {
    "sheetId": 1,
    "rowCount": 12,
    "colCount": 8,
    "cells": [
      {"row": 0, "col": 1, "value": "42"}
    ]
  }
  ```
- **Response** (`200 OK`, `DataWriteResponse`):
  ```json
  {
    "rowCount": 12,
    "colCount": 8,
    "updatedCells": 1
  }
  ```

Validation failures return `400 Bad Request` with an error message from the schema validator.

## `/api/sheets`
### `GET`
- **Response** (`200 OK`):
  ```json
  { "sheets": [{"id": 1, "name": "Sheet 1"}] }
  ```

### `POST`
- **Request body**:
  ```json
  {
    "name": "Quarterly Plan",
    "rowCount": 20,
    "colCount": 10,
    "cells": [["Name", "Target"]]
  }
  ```
- **Responses**:
  - `201 Created` on success, returning the new sheet dimensions and the refreshed sheet list.
  - `400 Bad Request` when the name is missing or row/column counts are invalid.
  - `409 Conflict` when the name already exists.

### `PATCH /api/sheets/<sheet_id>`
- **Request body**:
  ```json
  { "name": "Renamed Sheet" }
  ```
- **Responses**:
  - `200 OK` with updated sheet metadata.
  - `400 Bad Request` for invalid names.
  - `404 Not Found` when the sheet is missing.
  - `409 Conflict` for duplicate names.

## Import/Export
### `POST /api/import`
- Multipart form upload (`file`, optional `includeHeader` flag). Responds with preview metadata including a generated `previewId` and sample rows. Large previews are truncated to `MAX_IMPORT_ROWS`/`MAX_IMPORT_COLUMNS` from `main.py`.

### `POST /api/import/<preview_id>/confirm`
- JSON body specifying the target `sheetId`, optional `rowOffset`, and `includeHeader` override. Writes normalised values through `SheetService` and returns a `DataWriteResponse` payload.

### `GET /api/export/csv` and `GET /api/export/xlsx`
- Stream the current sheet as CSV/XLSX respectively. Query parameter `sheetId` selects a sheet; defaults to the first sheet. Responses are `text/csv` or `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` with `Content-Disposition` headers for download.

When adding new endpoints, update this document and include the relevant Pydantic schema names for traceability.
