# Milestone 4 Handoff: Reporting Polish

Use this document as the starting context for a new implementation session.

## Current state

Milestones 0–3 are complete. The application currently provides:

- React/TypeScript frontend, FastAPI backend, PostgreSQL, SQLAlchemy, and Alembic.
- Account, category, transaction, monthly budget, and expected-income management.
- Monthly summary calculations backed by persisted data.
- Selectable-text Navy Federal checking and credit-card PDF imports.
- Explicit import preview, duplicate detection, editing, selection, and atomic confirmation.
- Local deterministic merchant rules with normalized exact, contains, and restricted-regex matching.
- Explainable precedence and conflict review.
- Explicit match preview, correction, exclusion, and apply workflow.
- Optional exact-rule learning from reviewed decisions.
- Manual versus merchant-rule categorization provenance.
- Review filters with stable corrections and selection.
- Privacy, adversarial-input, regex-safety, and integration coverage.

External categorization and machine-learning providers are intentionally out of scope. Transactions
without a deterministic match remain uncategorized until reviewed manually.

## Milestone 4 objective

Make monthly results faster to understand and the portfolio experience more polished without
changing established budgeting, import, duplicate-detection, or categorization semantics.

## Scope

- Add category-composition visualization for the selected month.
- Improve budget-progress visualization and overspending warnings.
- Add income-versus-spending trends across multiple months.
- Improve responsive layouts and accessible interactions.
- Add synthetic demonstration data containing no real financial information.
- Add backend summary/reporting tests and frontend component/accessibility tests.
- Update product documentation and mark Milestone 4 complete only when the whole slice is verified.

## Constraints

- Preserve `Decimal` and fixed-precision money behavior.
- Preserve transfer and `excluded_from_budget` summary semantics.
- Preserve existing import confirmation and duplicate detection.
- Preserve explicit categorization preview/apply; do not introduce autonomous categorization.
- Do not add external providers, API credentials, telemetry, or sensitive-data logging.
- Prefer accessible HTML/CSS visuals; avoid a chart dependency unless it provides clear value.
- Use synthetic/redacted data exclusively in fixtures and demonstration content.

## Recommended implementation order

1. Review the current monthly-summary API and dashboard tests; define the smallest additional
   reporting response needed for multi-month trends.
2. Add backend trend schemas/service/API coverage while retaining existing monthly calculations.
3. Add category composition and improved budget progress to the current dashboard.
4. Add an income-versus-spending trend view with accessible text equivalents.
5. Test narrow-screen layouts, keyboard use, labels, color-independent states, and reduced motion.
6. Add an explicit synthetic demo-data workflow that cannot overwrite normal user data silently.
7. Run the complete backend and frontend validation suites and update the roadmap.

## Primary files

- `backend/app/services/monthly_summary.py`
- `backend/app/schemas/monthly_summary.py`
- `backend/app/api/routes/monthly_summary.py`
- `backend/tests/api/test_monthly_summary.py`
- `frontend/src/api/monthlySummary.ts`
- `frontend/src/features/summary/MonthlySummaryDashboard.tsx`
- `frontend/src/features/summary/MonthlySummaryDashboard.test.tsx`
- `frontend/src/styles.css`
- `docs/roadmap.md`

## Validation commands

From `backend/`:

```bash
.venv/bin/ruff check app tests
.venv/bin/mypy app tests
.venv/bin/pytest
```

From `frontend/`:

```bash
npm run check
npm test -- --run
```

Also run `git diff --check` from the repository root.
