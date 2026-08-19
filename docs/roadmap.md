# Roadmap

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

## Milestone 5: Debt planning

- Loan terms and balance history.
- Amortization calculator with tested decimal math.
- Snowball, avalanche, and custom payoff scenarios.
- Scenario comparisons with assumptions made explicit.

## Milestone 6: Expansion

- Additional credit-card statement adapters.
- Additional institutions.
- Hosted deployment and authentication decision.
- Bank synchronization provider evaluation.
- Mobile client or progressive web application improvements.
