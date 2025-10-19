# Documentation Index

This directory houses deeper references for the Flask Spreadsheet project. Use it to explore detailed architecture plans, API contracts, lifecycle diagrams, and operational guidance that complement the high-level summary in `README.md`.

- [System Architecture](architecture.md) – module boundaries, request/client flows, and planned evolution.
- [API Contracts](api-contracts.md) – endpoint payloads, validation rules, and response schemas.
- [Data Lifecycle](data-lifecycle.md) – diagrams and prose describing how data is created, edited, imported, exported, and observed.
- [Testing Strategy](testing-strategy.md) – tooling, suite coverage, and future automation goals.
- [Operations Guide](operations.md) – migrations, background jobs, caching plans, and deployment checklists.
- [Formula Reference](formula-reference.md) – supported operators, functions, and guidance for the built-in formula engine.

Keep these references aligned with the codebase. When introducing new services (imports, exports, background workers, caches) or operational dependencies, update the corresponding document and link to the responsible modules so contributors and operators stay informed.
