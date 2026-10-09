# Development Status

## OPS-UDA-001 — Prefix compatibility
Status: IN PROGRESS

The live UDA-listed Flask Spreadsheet now trusts a single isolated proxy hop, generates prefix-aware assets and workbook exports, and scopes client API calls through the mounted path while preserving LAN access. Existing spreadsheet data is not modified. Public UDA proxy exposure remains disabled.

- [ ] CI green, merged to main
- [ ] User tests workbooks, formulas, import/export, AI and data sources through UDA
