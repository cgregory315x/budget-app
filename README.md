# budget-app

A private, single-user budgeting application for importing financial statements, reviewing and categorizing transactions, setting monthly category limits, and understanding spending through clear visual summaries.

The initial supported statement formats are selectable-text Navy Federal Credit Union checking and credit-card statements. The import design is adapter-based so support for additional institutions can be added later.

## Current status

The repository contains the product plan, a migrated domain schema, a FastAPI service, and a React dashboard. Persistent accounts, categories, manual transactions, monthly category budgets, expected income, and a real monthly summary are available through the API and dashboard. Milestone 2 is complete: selectable-text Navy Federal checking and credit-card statements can be safely previewed, reviewed, checked for duplicates, and explicitly confirmed through an atomic import workflow. Milestone 3 has begun with local deterministic merchant rules and an explicit match preview/apply workflow; no external AI provider is connected.

## Statement import API

`POST /api/v1/imports/preview` accepts `multipart/form-data` with an `account_id` field and one `file`. The account must be active and its type must match the identified statement adapter: checking for checking statements or credit card for credit-card statements. The file must be an `application/pdf` upload with a PDF signature, no larger than 10 MiB, and contain selectable text. The response returns the extracted text, PDF metadata, file hash, registered adapter, duplicate annotations, and editable candidate transactions. Preview does not write to the database.

The upload limit can be changed with `STATEMENT_UPLOAD_MAX_BYTES`. Uploaded PDFs are held only in a temporary file and that file is deleted after every success or failure. Recognized Navy Federal statements return their statement period, masked account hint, editable candidate transactions, confidence, and row-level warnings. Preview also flags an exact PDF hash already present in statement-import history and marks exact or possible candidate transaction matches using occurrence-aware fingerprints. If extraction succeeds but the transaction layout is not recognized, the API still returns the extracted-text preview with a parser warning and no candidates.

`POST /api/v1/imports/confirm` accepts the reviewed statement metadata and selected candidate rows. It revalidates the active account and adapter, rejects statement replays and unapproved exact transaction duplicates, and atomically creates the confirmed `StatementImport` and its transactions. Exact duplicates are excluded by default in the UI and require explicit selection. Confirmation does not categorize transactions; assisted categorization remains Milestone 3 work.

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
