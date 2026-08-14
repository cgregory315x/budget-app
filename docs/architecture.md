# Architecture

## System shape

Budget App is a modular monolith with separate frontend and backend applications. This keeps local development approachable while preserving boundaries that support a future mobile client and external bank-data providers.

```text
React client
    |
FastAPI JSON API
    |-- budgeting domain services
    |-- categorization service
    |-- statement import pipeline
    |      |-- Navy Federal adapter
    |      `-- future adapters
    |-- external AI categorization gateway
    `-- SQLAlchemy repositories
            |
        PostgreSQL
```

## Frontend

- React with TypeScript and Vite.
- Feature-oriented modules will be introduced as behavior grows: dashboard, imports, transactions, budgets, and debt.
- The client consumes versioned JSON endpoints under `/api/v1`.
- The import preview keeps uncertain parsing visible and editable before confirmation.

## Backend

- FastAPI application split into routers, services, domain models, and infrastructure adapters.
- SQLAlchemy 2-style typed declarative mappings.
- Alembic owns schema migrations.
- Pydantic schemas validate public API inputs and outputs.
- Monetary calculations use `Decimal` and fixed-precision database columns.
- Request-scoped SQLAlchemy sessions are injected into routes, while service modules own transaction boundaries and translate persistence conflicts into sanitized domain errors.

## Statement import boundary

All institution-specific behavior implements a common adapter contract:

1. `can_parse(text)` determines whether the adapter recognizes a statement.
2. `parse(text)` returns statement metadata and normalized candidate rows.
3. Every candidate includes source text, amount, date, confidence, and warnings.
4. The orchestration layer validates totals, detects duplicates, and creates a temporary import preview.

The first adapter targets selectable-text Navy Federal checking statements. Raw PDFs are temporary input, not durable domain data.

## Categorization order

1. User-defined exact or normalized merchant rules.
2. Existing transaction/category history.
3. External AI suggestion for unresolved items.
4. User approval or correction.
5. Optional creation or update of a deterministic rule.

AI output is always treated as a suggestion. The provider gateway must return a category identifier, confidence, and short rationale using only the categories supplied by the application.

## Security boundary

- The API accepts PDFs only through the import endpoint with file-size and content checks.
- Temporary storage uses generated names outside publicly served directories.
- Successful, cancelled, and expired imports trigger cleanup.
- Logs contain import identifiers and status, not statement text or account data.
- AI requests omit personally identifying statement metadata.

## Future deployment

Authentication is intentionally deferred while the app is local and single-user. Before public hosting, add user ownership to all records, authentication, authorization tests, secure secret storage, TLS, encrypted backups, retention controls, and an explicit privacy review.
