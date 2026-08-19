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

- [Started] Temporary PDF upload with limits and cleanup.
- [Started] Text extraction preview and adapter identification boundary.
- [Started] Selectable-text Navy Federal checking adapter.
- [Started] Selectable-text Navy Federal credit-card adapter.
- [Started] Parser fixtures made from synthetic/redacted samples.
- [Started] Import preview with row-level warnings and editing.
- Statement and transaction duplicate detection.

## Milestone 3: Assisted categorization

- Merchant normalization and deterministic matching.
- Rule management.
- External AI provider gateway for unresolved transactions.
- Approval, correction, and rule-learning flow.
- Privacy and prompt-injection tests around statement descriptions.

## Milestone 4: Reporting polish

- Category composition and budget progress visuals.
- Income-versus-spending trends.
- Responsive layout and accessible interactions.
- Portfolio demo data that contains no real financial information.

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
