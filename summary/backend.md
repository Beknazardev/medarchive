# Backend Summary

## Purpose

The backend provides the REST API, import processing, search, comparison, catalog endpoints, database access, and migrations.

## Stack

- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL
- pytest

## Implemented Modules

- FastAPI app and API v1 router.
- Config and database session setup.
- SQLAlchemy models for users, data sources, clinics, branches, categories, normalized services, services, unmatched service records, current prices, price history, immutable price observations, import batches, import errors, parser runs, parser errors, raw source snapshots, and raw source rows.
- Alembic migrations through `20260627_0005_ingestion_audit_observations.py`.
- `NormalizationService`
- `ParserAuditService`
- immutable ingestion contracts and the code-owned source registry
- bounded `httpx` fetch protocol with DNS/SSRF, redirect, robots, MIME, byte, retry, page, concurrency, and rate controls
- content-addressed filesystem raw-response storage
- `ServiceCatalogSeedService`
- `SourceFixtureImportService`
- `freshness_service` helper
- `ImportService`
- `SearchService`
- `PriceComparisonService`
- `ClinicService`
- `ServiceCatalogService`

## Implemented Endpoints

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

## Local Run

```bash
cd backend
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload
```

Required backend environment variables:

```text
PROJECT_NAME
APP_VERSION
API_V1_PREFIX
DATABASE_URL
BACKEND_CORS_ORIGINS
IMPORT_API_KEY
PARSER_USER_AGENT_NAME
PARSER_CONTACT
```

## Tests

Backend tests live in `backend/tests`.

Run:

```bash
cd backend
pytest
```

Current coverage includes import success and validation, duplicate imports, price updates, import edge cases, search edge cases, comparison edge cases, catalog endpoints, normalization, and database constraints.

Phase B coverage includes optional source metadata, per-price `source_url`, per-price `parsed_at`, backwards-compatible imports without provenance, and provenance fields in search/compare responses.

Phase C coverage includes official Excel catalog loading, idempotent catalog reloads, catalog lookup, and import-time catalog matching before creating fallback normalized services.

Phase D coverage includes parser run/error persistence, import-error separation from parser errors, raw snapshot persistence, raw row persistence, import batch linking, and raw row links to imported service/current price records.

Phase E is documentation/fixture-only: it defines the source adapter JSON contract and three deterministic fixture outputs without adding parser dependencies or backend source-specific code.

Phase F adds deterministic seed-source ingestion for three documented public sources. The command `python -m app.scripts.import_demo_sources` reads local fixtures, creates parser/raw audit records, and routes data through the existing import service without live scraping.

Phase G adds service normalization status/confidence and an unmatched queue for raw service names that do not match the official catalog. Inspect open items with `python -m app.scripts.list_unmatched_services`.

Phase H adds centralized price freshness semantics. Prices are `fresh` from 0-7 days old, `aging` from 8-30 days old, `stale` after 30 days, and `unknown` when neither `parsed_at` nor `updated_at` is available. API response objects expose `freshness_state` and `freshness_age_days` in search, compare, clinic detail, and service detail price rows.

Parser Phase B extends the existing audit model additively. Parser errors carry stage/retryability; raw snapshots carry HTTP/content metadata; raw rows carry canonical hashes and extraction/validation outcomes; unmatched records track repeated occurrences and future review audit fields. `price_observations` records every successful import row while `price_history` remains limited to actual create/update events. Existing import requests and responses remain compatible.

Parser Phase D adds safe fetch infrastructure only. `SafeHttpFetcher` accepts registry source IDs rather than arbitrary configurations, validates every initial/redirect destination and resolved address, evaluates cached robots policy fail-closed, applies per-host concurrency/delay and bounded retries, enforces MIME/byte/redirect limits, supports conditional requests, and stores a SHA-256-addressed raw response before returning it for future extraction. `ParserAuditService` persists successful source-document metadata and final stage-specific failures. `SafeFetchOrchestrator` returns an isolated result per bounded request so one source failure does not abort later sources. It is not called by FastAPI and no source adapter or scheduler exists.

## Service Catalog Seed

The default catalog is loaded from the official hackathon workbook:

```text
data/reference/service_catalog.xlsx
```

The loader reads sheet `Справочник услуг`, maps `Специальность` to categories, maps `Name_ru` to normalized service names, ignores `ID` and `Code`, and does not persist `TarificatrCode` yet. The workbook currently yields 1,281 service rows across 122 categories. It has no explicit alias/synonym column, so official catalog aliases are seeded as empty lists.

Seed or refresh it after migrations:

```bash
cd backend
python -m app.scripts.seed_service_catalog
```

The command is idempotent: existing catalog records are updated and any explicit aliases supplied by future catalog data are merged instead of duplicated.

## Demo Source Ingestion

Run deterministic Phase F source ingestion:

```bash
cd backend
python -m app.scripts.import_demo_sources
```

The command imports fixtures from `examples/sources/` and preserves source URLs, parsed timestamps, raw row metadata, parser runs, raw snapshots, and raw rows. It does not perform live HTTP scraping.

## Unmatched Queue

Inspect queued unmatched service rows:

```bash
cd backend
python -m app.scripts.list_unmatched_services
```

The import flow marks exact catalog matches as `matched` with confidence `1.0`, alias matches as `alias_matched` with confidence `0.9`, and unmatched rows as `unmatched` with confidence `0.0`.

## Docker

The backend image is built from `backend/Dockerfile`.

In Compose, the backend waits for PostgreSQL and runs:

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Current Limitations

- API key auth is only used for import.
- No user authentication or roles.
- No live parser service, parser read endpoints, parser UI, unmatched admin UI, or background jobs.
- No production deployment hardening.
