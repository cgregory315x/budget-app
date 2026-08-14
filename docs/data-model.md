# Data Model

## Core entities

| Entity | Purpose | Important fields |
| --- | --- | --- |
| Account | Financial account being tracked | name, institution, type, current balance, currency |
| StatementImport | Temporary and auditable import attempt | adapter, statement period, file hash, status, warnings |
| Transaction | Confirmed financial event | account, posted date, description, amount, category, import |
| Category | User-defined spending or income grouping | name, kind, color, archived flag |
| MerchantRule | Deterministic categorization learned from review | normalized pattern, match type, category, priority, enabled |
| MonthlyBudget | Category limit for a calendar month | month, category, limit amount |
| MonthlyIncome | Expected or actual income for a month | month, amount, description |
| LoanTerms | Inputs used for projections | account, principal, annual rate, minimum payment, term |
| LoanBalanceSnapshot | Historical loan balance | account, as-of date, balance, source |

Category names are unique without regard to letter case, while preserving the user's display spelling. Deleting a category archives it rather than removing it, so transactions, budgets, and merchant rules retain their historical relationship.

Deleting an account also archives it rather than removing it. This preserves its future transaction, statement-import, and loan history. A current balance is optional because an account may be created before a statement or manual balance is available.

## Money conventions

- Persist money as fixed-precision numeric values with two fractional digits for USD-facing fields.
- Use positive amounts for inflows and negative amounts for outflows.
- Preserve transfer classification so transfers can be excluded from spending totals.
- Store interest rates as integer basis points or a fixed-precision decimal, never floating point.
- Store a logical month as the first calendar day of that month and enforce that invariant in both API validation and the database.

## Duplicate detection

Each confirmed transaction receives a deterministic fingerprint derived from the account, posted date, normalized description, amount, and a stable occurrence index. Statement imports also store a SHA-256 file hash. Neither mechanism should silently discard a candidate; possible duplicates must appear in the review flow.

Manual transactions allocate the lowest available positive occurrence index among otherwise identical transactions. Editing fingerprint inputs recalculates the fingerprint and occurrence index. Manual deletion removes the confirmed transaction, while deleting accounts and categories continues to mean archival.

## Import lifecycle

`UPLOADED -> PARSED -> NEEDS_REVIEW -> CONFIRMED`

Terminal alternatives are `FAILED`, `CANCELLED`, and `EXPIRED`. The source PDF is deleted for all terminal states and immediately after successful confirmation.

## Ownership

The MVP is single-user and local. Before multi-user or public deployment, introduce a user identifier and enforce ownership at both repository and API boundaries.
