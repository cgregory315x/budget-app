# budget-app

A private, single-user budgeting application for importing financial statements, reviewing and categorizing transactions, setting monthly category limits, and understanding spending through clear visual summaries.

The initial supported statement format is selectable-text Navy Federal Credit Union checking statements. The import design is adapter-based so support for additional institutions can be added later.

## Current status

The repository contains the product plan, a migrated domain schema, a FastAPI service, and a React dashboard. Persistent account, category, and manually entered transaction management are available through the API and dashboard; monthly budgeting and the PDF import workflow are still in development.

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
2. Start PostgreSQL with `docker compose up -d db`.
3. Install and run the backend:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -e '.[dev]'
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

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
