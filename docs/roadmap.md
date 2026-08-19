# Roadmap

## Current status

Development is intentionally stopping at Milestone 4. The application currently covers the
budgeting, statement-import, categorization, and reporting workflows needed for its present use.
Debt planning is not part of the product scope.

There is no committed next milestone. Future development will focus on small quality-of-life,
maintenance, accessibility, and reliability improvements as real needs emerge.

## Milestone 0: Foundation

- React/TypeScript and FastAPI applications.
- PostgreSQL local service.
- Health endpoint and dashboard shell.
- Typed domain model and migration setup.
- Automated frontend and backend validation.

## Milestone 1: Manual budgeting core

- Account, category, transaction, monthly budget, and income CRUD.
- Monthly summary query.
- Dashboard backed by real API data.
- Transaction filtering and manual categorization.

## Milestone 2: Navy Federal import

- [Complete] Temporary PDF upload with limits and cleanup.
- [Complete] Text extraction preview and adapter identification boundary.
- [Complete] Selectable-text Navy Federal checking adapter.
- [Complete] Selectable-text Navy Federal credit-card adapter.
- [Complete] Parser fixtures made from synthetic/redacted samples.
- [Complete] Import preview with row-level warnings and editing.
- [Complete] Statement and transaction duplicate detection.
- [Complete] Explicit selection and atomic import confirmation.

## Milestone 3: Deterministic categorization — Complete

- [Complete] Initial deterministic merchant normalization and matching slice.
- [Complete] Merchant-rule management and explicit match preview/apply review.
- [Complete] Explainable precedence, conflict visibility, and existing-category protection.
- [Complete] Deterministic approval, correction, and exact-rule learning flow.
- [Complete] Transaction categorization provenance for manual and merchant-rule assignments.
- [Complete] Rule re-enabling and explainable conflict review.
- [Complete] Scalable match review filters with stable corrections and selection.
- [Complete] Deterministic end-to-end, privacy, adversarial-description, and regex-safety tests.

## Milestone 4: Reporting polish — Complete

- [Complete] Category composition and accessible budget progress visuals.
- [Complete] Six-month income-versus-spending trends with exact-value table.
- [Complete] Responsive layout, keyboard focus, reduced motion, and color-independent warnings.
- [Complete] Protected portfolio demo-data workflow containing no real financial information.
- [Complete] Backend reporting and frontend component/accessibility coverage.

## Future quality-of-life work — As needed

- Address usability friction discovered through normal use.
- Refine responsive behavior, accessibility, and keyboard workflows.
- Improve reporting or import ergonomics when a concrete need is identified.
- Keep dependencies, tests, documentation, and local-development tooling healthy.
- Consider larger integrations or deployment work only if priorities change.

## Intentionally out of scope

- Debt and loan planning, including amortization and payoff scenarios.
- Speculative integrations or expansion without a demonstrated need.

The initial migration still contains dormant loan-related tables. They are not exposed by the
application and remain only to preserve migration history.
