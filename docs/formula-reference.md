# Formula Reference

The spreadsheet UI ships with a lightweight formula engine implemented in
[`static/js/formula_engine.js`](../static/js/formula_engine.js). Cells that begin
with an equals sign (`=`) are parsed as formulas and can reference other cells
using standard `A1` notation, combine ranges (`A1:B3`), and chain arithmetic or
comparison operators. Evaluation results propagate to dependent cells and error
codes (`#DIV/0!`, `#VALUE!`, `#NAME?`, `#NUM!`, `#ERROR`, `#CYCLE!`) surface in
place when inputs are invalid.

## Supported Operators

- Arithmetic: `+`, `-`, `*`, `/`, `^`
- Comparisons: `=`, `<>`, `>`, `>=`, `<`, `<=`
- Grouping: parentheses `(` `)`

Blank cells coerce to zero for arithmetic unless a function specifies different
behaviour. Text, boolean, and error values follow the coercion rules implemented
inside the engine helpers (`coerceToString`, `coerceToBoolean`, `tryCoerceNumber`).

## Built-in Functions

The following functions are available and mirror the behaviour of their
spreadsheet counterparts. Range arguments expand across all referenced cells,
and individual cells can be combined with literal values.

### Math & Aggregation

- `SUM`
- `AVERAGE`
- `MIN`
- `MAX`
- `COUNT`
- `COUNTA`
- `ABS`
- `ROUND`
- `ROUNDDOWN`
- `ROUNDUP`
- `CEILING`
- `FLOOR`
- `INT`
- `MOD`
- `POWER`
- `SQRT`

### Logical

- `IF`
- `AND`
- `OR`
- `NOT`

### Text

- `CONCAT`
- `CONCATENATE`
- `LEFT`
- `RIGHT`
- `MID`
- `LEN`
- `LOWER`
- `UPPER`
- `TRIM`

When an unrecognised function name is used the engine returns `#NAME?`. Provide
additional functions by extending the `functionHandlers` map.

## Usage Tips

- Select a cell and type `=` to begin a formula. Use the formula bar to edit the
  expression and confirm with Enter.
- Use ranges (`A1:A10`) to aggregate columns or rows without manually listing
  each cell.
- Combine literal numbers, strings in quotes (e.g. `="Hello"`), and boolean
  values (`TRUE`, `FALSE`) just as you would in a desktop spreadsheet.
- Errors propagate—fix the earliest failing cell to resolve downstream
  references.

Refer to [`static/js/spreadsheet.js`](../static/js/spreadsheet.js) for the
wiring between the grid UI and the formula engine.
