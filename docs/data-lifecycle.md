# Data Lifecycle

## Creation
1. The application factory (`create_app`) ensures a default sheet exists via `SheetService.ensure_default_sheet()` during start-up.
2. Users create additional sheets via `POST /api/sheets`, which calls `SheetRepository.add_sheet()` and initialises dimensions. Optional seed cells are normalised and written by `SheetService.write_sheet_data()`.

## Editing
1. AG Grid captures cell edits and batches them into a `DataWriteRequest` payload.
2. `POST /api/grid` invokes `SheetService.write_sheet_data()` which:
   - Validates cell payloads through `CellUpdate` schemas.
   - Applies column-level rules (e.g., numeric validation via `COLUMN_RULES`).
   - Upserts `SheetCell` rows using `SheetRepository.upsert_cell()`.
3. Successful writes return `DataWriteResponse` summarising affected cells and the current sheet dimensions.

## Reading
- `GET /api/grid` loads sheet metadata and the full cell matrix, pre-populating empty strings for unset cells to simplify UI rendering.
- `GET /api/sheets` enumerates sheets for selection menus.
- Export endpoints stream the persisted data directly from SQLModel queries to CSV/XLSX writers.

## Importing
1. Users upload CSV/XLSX files via `POST /api/import`.
2. Files are saved in `instance/import_previews/` and parsed (Pandas when available, CSV fallback otherwise).
3. Preview metadata is stored in JSON files keyed by a random preview ID.
4. `POST /api/import/<preview_id>/confirm` re-loads the preview, normalises values with the same rules as manual edits, and writes them to the target sheet.

## Deletion & Retention
- Individual cells are cleared when an empty value is supplied; the repository deletes rows from `sheet_cells` accordingly.
- Sheet deletion is not yet implemented. When added, ensure cascade behaviour is handled in the ORM and update this section.

## Observability
- Status messages are surfaced in the UI to reflect save/import operations.
- Server-side logs use the configuration in `logging.conf`; instrument additional metrics or tracing here when adding background workers or caching layers.
