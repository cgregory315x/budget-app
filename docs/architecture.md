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
- Confirmation revalidates the account and adapter, then creates the statement import and
  approved transactions atomically. Categorization remains a separate later workflow.

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

The current Milestone 3 slice is local and deterministic:

1. Only enabled rules whose target category is active are considered.
2. Only transactions with no category are eligible.
3. Rules match the stored normalized merchant value without changing the original description.
4. Lower numeric priority wins. At equal priority, exact beats contains, which beats regular
   expression; a longer normalized pattern then wins; creation time and rule ID are stable final
   tie-breakers.
5. Preview returns the winner and any lower-precedence competing rule IDs. It writes nothing.
6. Apply accepts the user's selected transaction IDs, recalculates winners, and skips any
   transaction categorized or no longer matched since preview.
7. Each selected row carries an explicitly approved active category. The user may keep the
   suggestion or correct it; unchecked rows are omitted and remain unchanged.
8. The user may save an approval or correction as an exact rule for that normalized merchant.
   Existing exact rules are retargeted and re-enabled instead of duplicated. Transaction updates
   and learned-rule changes commit atomically.

There is no history-based, AI, or autonomous fallback in this slice. A later Milestone 3 slice may
add suggestions for unresolved items, but they must remain behind explicit user approval.

## Security boundary

- The API accepts PDFs only through the import endpoint with file-size and content checks.
- Temporary storage uses generated names outside publicly served directories.
- Successful, cancelled, and expired imports trigger cleanup.
- Logs contain import identifiers and status, not statement text or account data.
- Merchant matching runs inside the application and database. It makes no external request and
  does not log transaction descriptions, normalized merchant values, statement text, sensitive
  account metadata, rule patterns, or preview payloads.
- No AI provider, credentials, prompt construction, or provider logging exists in this slice.

## Future deployment

Authentication is intentionally deferred while the app is local and single-user. Before public hosting, add user ownership to all records, authentication, authorization tests, secure secret storage, TLS, encrypted backups, retention controls, and an explicit privacy review.
