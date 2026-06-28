# Medical Services Price Aggregator Kazakhstan

MVP web service for importing, searching, and comparing medical service prices for clinics in Kazakhstan.

The project contains a FastAPI backend, PostgreSQL schema and migrations, a Next.js frontend, a manual JSON import page, backend tests, and Docker Compose for local MVP runs.

## MVP Scope

Included:

- JSON price import with API key protection.
- Import batches, import errors, deduplication, current prices, and price history.
- Service search with city, category, price filters, sorting, and pagination.
- Price comparison by service, normalized service, or query.
- Clinics, clinic details, service details, categories, and cities APIs.
- Public frontend pages for home, search, compare, clinic details, and service details.
- Russian-default RU/KZ/EN interface with persistent light and dark themes.
- Multilingual query aliases for common demo services across search and comparison.
- Manual admin import page at `/admin/import`.
- Docker Compose for PostgreSQL, backend, and frontend.
- Deterministic Case 1 demo source ingestion from local public-source fixtures.

Not included:

- Authentication or user roles.
- Online booking.
- Payments.
- Reviews.
- Patient accounts.
- Parser service.
- Background jobs.
- Redis, Celery, MinIO, Nginx, Caddy, Elasticsearch, or OpenSearch.

## Stack

- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic, pytest.
- Document extraction: lxml (HTML), pdfplumber + PyMuPDF (PDF), python-docx (DOCX), openpyxl (XLSX).
- Frontend: Next.js App Router, TypeScript, Tailwind CSS, minimal shadcn/ui-compatible components.
- Database: PostgreSQL.
- Local orchestration: Docker Compose.

## Project Structure

```text
backend/
  app/
  alembic/
  tests/
  Dockerfile
  requirements.txt
frontend/
  app/
  components/
  lib/
  Dockerfile
docs/codex/
summary/
docker-compose.yml
README.md
SUMMARY.md
TASKS.md
```

## Environment Variables

Backend:

```text
PROJECT_NAME="Medical Services Price Aggregator Kazakhstan"
APP_VERSION="0.1.0"
API_V1_PREFIX="/api/v1"
DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/aggregator"
BACKEND_CORS_ORIGINS="http://localhost:3000"
IMPORT_API_KEY="example-secret"
PARSER_USER_AGENT_NAME="MedPriceBot"
PARSER_CONTACT="mailto:replace-with-monitored-address@example.invalid"
```

`PARSER_CONTACT` must be replaced with a monitored `mailto:` address or HTTPS contact page before constructing the live fetcher. An empty value intentionally prevents creation of a compliant parser user agent.

Frontend:

```text
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
```

Copy the example file for local shell-based runs:

```bash
cp .env.example .env
```

## Run Backend Locally

Start PostgreSQL locally and set `DATABASE_URL`, then run:

```bash
cd backend
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
python -m app.scripts.seed_service_catalog
uvicorn app.main:app --reload
```

Healthcheck:

```http
GET http://localhost:8000/health
```

## Run Frontend Locally

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:3000
```

## Run Tests

Backend:

```bash
cd backend
pytest
```

Seed or refresh the official normalized service catalog from `data/reference/service_catalog.xlsx`:

```bash
cd backend
python -m app.scripts.seed_service_catalog
```

Import the deterministic Case 1 demo source fixtures:

```bash
cd backend
python -m app.scripts.import_demo_sources
```

The demo source importer reads `examples/sources/*_adapter_output.json`, preserves source URLs and parsed timestamps, creates parser/raw audit records, and sends data through the existing JSON import pipeline. It imports 105 deterministic price rows across 3 public-source fixtures and does not scrape live websites.

Validate Case 1 demo readiness:

```bash
cd backend
python -m app.scripts.validate_demo_dataset
```

The validation command checks at least 3 sources, at least 100 current service price records, at least 50 normalized catalog records, and complete `source_url`/`parsed_at` coverage for current prices.

Frontend verification:

```bash
cd frontend
npm run lint
npm run build
```

## Run Docker Compose

```bash
docker compose up --build
```

Services:

- PostgreSQL: `localhost:5432`
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

The backend container runs `alembic upgrade head` before starting Uvicorn.

Stop containers:

```bash
docker compose down
```

## API Overview

Base URL:

```text
/api/v1
```

Endpoints:

```http
GET /health
GET /api/v1/
POST /api/v1/import/prices
GET /api/v1/services/search
GET /api/v1/prices/compare
GET /api/v1/clinics
GET /api/v1/clinics/{id}
GET /api/v1/services/{id}
GET /api/v1/categories
GET /api/v1/cities
```

Import endpoint requires:

```http
X-API-Key: <IMPORT_API_KEY>
```

## Known Limitations

- The admin import page is a single utility page, not a full admin panel.
- The API key is a shared configured key.
- Service normalization is rule-based and minimal.
- The frontend has no dedicated smoke-test framework; Phase 10 verifies it with lint and production build.
- UI translations cover product chrome and generic metadata; imported clinic/service/source data is intentionally shown exactly as received.
- Docker Compose is local MVP infrastructure, not production deployment infrastructure.
