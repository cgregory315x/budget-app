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

## Merchant matching

Transaction descriptions remain exactly as confirmed or manually entered. A separate
`merchant_normalized` value is used for matching: Unicode is converted conservatively to ASCII,
letters are uppercased, punctuation becomes spaces, repeated whitespace collapses, and numbers
are retained. Exact and contains rule patterns use the same normalization. Regular-expression
patterns preserve operators, are converted to ASCII uppercase, and run against the normalized
merchant value; invalid expressions are rejected.

Rules can only be created or retargeted to active categories. Disabled rules and rules whose
category was later archived do not match. Normalized pattern plus match type is unique. Priority
uses a lower-number-wins convention; equal-priority conflicts resolve by match type (exact,
contains, regular expression), longer pattern, older creation time, then rule ID. Preview exposes
losing matches so the outcome remains explainable.

Preview is read-only. Apply recalculates the preview and changes only explicitly selected,
currently uncategorized transactions. A manual category assignment is never overwritten, including
when it happens between preview and apply.

During review, each selected match may retain its suggested category or use a different active
category. A corrected decision can optionally be learned as an exact rule for the transaction's
normalized merchant. If that exact rule already exists, learning retargets and re-enables it;
otherwise it creates a priority-100 exact rule. The assignment and learned rule are one atomic
operation. Archived correction categories and stale matches are skipped without changing data.

## Money conventions

- Persist money as fixed-precision numeric values with two fractional digits for USD-facing fields.
- Use positive amounts for inflows and negative amounts for outflows.
- Preserve transfer classification so transfers can be excluded from spending totals.
- Store interest rates as integer basis points or a fixed-precision decimal, never floating point.
- Store a logical month as the first calendar day of that month and enforce that invariant in both API validation and the database.

Monthly budgets apply only to active expense categories, with at most one limit per category and month. Monthly income is stored as one or more positive entries so separate expected income sources remain visible while still supporting a monthly total.

The monthly summary compares that expected-income total with confirmed transactions for the selected month. Transfers and transactions excluded from the budget do not affect the summary. Positive transactions in income categories, along with positive uncategorized transactions, count as recorded inflows. Expense-category refunds reduce that category's spending, while negative uncategorized transactions count as uncategorized spending. The available amount is expected income less total spending; recorded inflows are shown separately and do not replace the user's plan.

## Duplicate detection

Each confirmed transaction receives a deterministic fingerprint derived from the account, posted date, normalized description, amount, and a stable occurrence index. Statement imports also store a SHA-256 file hash. Neither mechanism should silently discard a candidate; possible duplicates must appear in the review flow.

Manual transactions allocate the lowest available positive occurrence index among otherwise identical transactions. Editing fingerprint inputs recalculates the fingerprint and occurrence index. Manual deletion removes the confirmed transaction, while deleting accounts and categories continues to mean archival.

## Import lifecycle

`UPLOADED -> PARSED -> NEEDS_REVIEW -> CONFIRMED`

Terminal alternatives are `FAILED`, `CANCELLED`, and `EXPIRED`. The source PDF is deleted for all terminal states and immediately after successful confirmation.

## Ownership

The MVP is single-user and local. Before multi-user or public deployment, introduce a user identifier and enforce ownership at both repository and API boundaries.
