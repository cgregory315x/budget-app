# Milestone 5 Handoff: Debt Planning

Use this document as the starting context for a new implementation session.

## Current state

Milestones 0–4 are complete. The application currently provides:

- React/TypeScript frontend, FastAPI backend, PostgreSQL, SQLAlchemy, and Alembic.
- Account, category, transaction, monthly budget, and expected-income management.
- Selectable-text Navy Federal statement imports with explicit preview and atomic confirmation.
- Local deterministic categorization with explainable matching and explicit review/apply.
- Monthly category composition, accessible budget warnings, and six-month income/spending trends.
- Responsive layouts, keyboard focus treatment, reduced-motion support, and exact-value chart tables.
- A protected synthetic demo-data workflow that refuses to modify a non-empty database.
- 98 passing backend tests and 39 passing frontend tests at the Milestone 4 boundary.

The initial database schema already contains `LoanTerms` and `LoanBalanceSnapshot` models and
tables. They are not exposed through schemas, services, API routes, or frontend features yet.
Do not create duplicate debt tables or replace the initial migration.

## Milestone 5 objective

Let the user record debts, calculate transparent payoff schedules, and compare snowball,
avalanche, and custom payoff strategies without obscuring assumptions or sacrificing exact money
behavior.

## Scope

- Add CRUD for loan terms tied one-to-one to loan accounts.
- Add dated balance-history CRUD for each loan.
- Add a deterministic amortization calculator with a month-by-month schedule.
- Detect payments that do not cover accrued interest and schedules that cannot converge.
- Add snowball, avalanche, and explicit custom-order payoff scenarios.
- Support an explicit extra monthly payment shared across the active payoff strategy.
- Compare scenarios by payoff date, total interest, total paid, and months saved.
- Show all calculation assumptions and provide accessible exact-value tables.
- Add backend decimal-math/API tests and frontend component/accessibility tests.
- Update product documentation and mark Milestone 5 complete only after full verification.

## Existing debt model

`backend/app/db/models.py` currently defines:

- `AccountType.LOAN`.
- `LoanTerms`: unique `account_id`, `principal`, `annual_rate_basis_points`, `minimum_payment`, and
  optional `term_months`.
- `LoanBalanceSnapshot`: `loan_terms_id`, unique `as_of_date` per loan, `balance`, and `source`.
- Nonnegative database constraints for principal, rate, payment, and snapshot balance.

The initial Alembic migration already creates these tables. Extend the schema only if the product
behavior genuinely needs additional persisted fields, and use a new migration for any extension.

## Calculation contract to establish first

- Keep all money and interest calculations in `Decimal`; never use binary floating point.
- Treat `annual_rate_basis_points` as fixed APR where 100 basis points equals 1% APR.
- State the periodic-rate and compounding assumptions in API responses and the UI.
- Quantize currency to cents with an explicit, tested rounding mode at defined calculation points.
- Clamp the final payment to principal plus accrued interest so schedules do not overpay.
- Reject negative inputs and zero/insufficient payments that cannot amortize the balance.
- Put a documented upper bound on schedule iterations and fail explicitly if payoff does not
  converge.
- Do not infer balances from imported transactions or silently change saved loan terms.
- Scenario results are projections, not promises; expose assumptions with every comparison.

## Strategy semantics

- Snowball: direct extra payment to the lowest current balance first, with deterministic tie-breaks.
- Avalanche: direct extra payment to the highest APR first, with deterministic tie-breaks.
- Custom: require the user to provide an explicit ordering containing every selected debt once.
- Continue minimum payments on all active debts, then roll freed payments into the next debt.
- Define how payments are handled when the available monthly amount is below combined minimums;
  return a clear validation error rather than inventing a distribution.
- Preserve stable ordering and explain which debt receives extra payment each month.

## Constraints

- Preserve all established budgeting, summary, import, duplicate-detection, and categorization
  semantics.
- Preserve fixed-precision database columns and `Decimal` behavior end to end.
- Keep create/update/delete operations explicit; do not derive or mutate debt data autonomously.
- Do not add external financial providers, credentials, telemetry, or sensitive-data logging.
- Do not present projections as financial advice or guaranteed payoff outcomes.
- Prefer accessible HTML/CSS visuals and exact-value tables over a chart dependency.
- Use synthetic debt names, balances, and rates exclusively in fixtures and demo content.
- Do not mark Milestone 5 complete after CRUD or a calculator alone; the full scenario slice and
  verification are required.

## Recommended implementation order

1. Review the existing debt models and constraints; write the calculation contract as tests.
2. Implement and thoroughly test the pure single-loan amortization service using `Decimal`.
3. Add loan-term and balance-snapshot schemas, services, routes, and API coverage.
4. Implement multi-debt snowball, avalanche, and custom scenario services with stable tie-breaks.
5. Add scenario response schemas containing assumptions, schedules, totals, and comparison metrics.
6. Build debt management and calculator UI with validation, accessible tables, and empty/error
   states.
7. Add scenario comparison UI with visible assumptions and color-independent results.
8. Extend the protected synthetic demo dataset with fictional loan data if useful.
9. Test narrow screens, keyboard use, reduced motion, exact values, and non-converging cases.
10. Run complete backend/frontend validation and update the README and roadmap.

## Suggested API boundary

Keep persistence separate from pure projections. A reasonable initial boundary is:

- `/api/v1/loans` for loan-term CRUD.
- `/api/v1/loans/{loan_id}/balances` for balance-history CRUD.
- `/api/v1/debt/amortization` for a non-persisting single-loan projection.
- `/api/v1/debt/scenarios` for non-persisting multi-debt strategy comparisons.

Confirm naming against existing route conventions before implementation. Projection endpoints
should not write data unless persistence is introduced later as an explicit product decision.

## Primary files

Existing files to review:

- `backend/app/db/models.py`
- `backend/alembic/versions/20260814_0001_initial_schema.py`
- `backend/app/api/router.py`
- `backend/tests/conftest.py`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `docs/data-model.md`
- `docs/product-requirements.md`
- `docs/roadmap.md`

Likely new files:

- `backend/app/schemas/debt.py`
- `backend/app/services/debt.py`
- `backend/app/api/routes/debt.py`
- `backend/tests/services/test_debt.py`
- `backend/tests/api/test_debt.py`
- `frontend/src/api/debt.ts`
- `frontend/src/features/debt/DebtPlanner.tsx`
- `frontend/src/features/debt/DebtPlanner.test.tsx`

## Validation commands

From `backend/`:

```bash
.venv/bin/ruff check app tests
.venv/bin/mypy app tests
.venv/bin/pytest
```

If the virtual environment is already active, the equivalent commands are `ruff`, `mypy`, and
`pytest` without the `.venv/bin/` prefix.

From `frontend/`:

```bash
npm run check
npm test -- --run
```

Also run `git diff --check` from the repository root.
