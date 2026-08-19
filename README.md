# budget-app

A private, single-user budgeting application for importing financial statements, reviewing and categorizing transactions, setting monthly category limits, and understanding spending through clear visual summaries.

The initial supported statement format is selectable-text Navy Federal Credit Union checking statements. The import design is adapter-based so support for additional institutions can be added later.

## Current status

The repository contains the product plan, a migrated domain schema, a FastAPI service, and a React dashboard. Persistent accounts, categories, manual transactions, monthly category budgets, expected income, and a real monthly summary are available through the API and dashboard; the PDF import workflow is still in development.

## Stack

- React 19 and TypeScript
- Vite
- Python 3.12+
- FastAPI
- SQLAlchemy and Alembic
- PostgreSQL
- Docker Compose for the local database

## Quick start

1. Copy `.env.example` to `.env` and adjust values if needed.
2. Start PostgreSQL and confirm it is running:

   ```bash
   docker compose up -d db
   docker compose ps
   ```

   If Docker reports permission denied while connecting to `/var/run/docker.sock`,
   use `sudo docker compose up -d db` as a temporary workaround.
3. Install and run the backend:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -e '.[dev]'
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

   PostgreSQL must be running before `alembic upgrade head` or any database-backed
   API request. After restarting the database later, run `alembic upgrade head`
   again before refreshing the web client.

4. In another terminal, install and run the frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

The API is available at `http://localhost:8000`; the web client defaults to `http://localhost:5173`.

Run backend validation with `pytest`, `ruff check app tests`, and `mypy app tests` from
`backend/`. Run frontend validation with `npm run check && npm test` from `frontend/`.

## Product documentation

- [Product requirements](docs/product-requirements.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Roadmap](docs/roadmap.md)
