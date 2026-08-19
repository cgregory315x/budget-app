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
    `-- SQLAlchemy repositories
            |
        PostgreSQL
```

## Frontend

- React with TypeScript and Vite.
- Feature-oriented modules separate dashboard, imports, transactions, budgets, accounts,
  categories, and merchant-rule behavior.
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

Milestone 3 categorization is local and deterministic:

1. Only enabled rules whose target category is active are considered.
2. Only transactions with no category are eligible.
3. Rules match the stored normalized merchant value without changing the original description.
4. Lower numeric priority wins. At equal priority, exact beats contains, which beats regular
   expression; a longer normalized pattern then wins; creation time and rule ID are stable final
   tie-breakers.
5. Preview returns the winner, the lower-precedence rules with their category and priority, and a
   concise explanation of the decisive tie-breaker. It writes nothing.
6. Apply accepts the user's selected transaction IDs, recalculates winners, and skips any
   transaction categorized or no longer matched since preview.
7. Each selected row carries an explicitly approved active category. The user may keep the
   suggestion or correct it; unchecked rows are omitted and remain unchanged.
8. The user may save an approval or correction as an exact rule for that normalized merchant.
   Existing exact rules are retargeted and re-enabled instead of duplicated. Transaction updates
   and learned-rule changes commit atomically.
9. Transactions expose categorization provenance. Accepted rule suggestions reference the winning
   rule; direct assignments and corrected suggestions are manual. A later category change clears
   stale rule provenance without relabeling unrelated transaction edits.
10. Match-review filters run locally over the read-only preview. Merchant, account, date, approved
    category, and corrected-only filters never alter matching or discard hidden decisions. Bulk
    selection applies only to visible rows while the interface retains the total selected count.

There is no history-based, probabilistic, external-provider, or autonomous fallback. Transactions
without a deterministic match remain uncategorized until the user assigns a category or adds a rule.

## Security boundary

- The API accepts PDFs only through the import endpoint with file-size and content checks.
- Temporary storage uses generated names outside publicly served directories.
- Successful, cancelled, and expired imports trigger cleanup.
- Logs contain import identifiers and status, not statement text or account data.
- Merchant matching runs inside the application and database. It makes no external request and
  does not log transaction descriptions, normalized merchant values, statement text, sensitive
  account metadata, rule patterns, or preview payloads.
- Adversarial transaction descriptions are treated only as data. Integration tests cover
  instruction-like text, control characters, unusual Unicode, bounded normalization, regex complexity,
  and the absence of descriptions or sensitive account labels from application logs.

## Future deployment

Authentication is intentionally deferred while the app is local and single-user. Before public hosting, add user ownership to all records, authentication, authorization tests, secure secret storage, TLS, encrypted backups, retention controls, and an explicit privacy review.
