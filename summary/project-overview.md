# Project Overview Summary

## Purpose

Medical Services Price Aggregator Kazakhstan is an MVP for importing, searching, and comparing clinic medical service prices.

For Hackathon Case 1, the project is now positioned as **MedServicePrice.kz**: a transparent medical price aggregator that collects public prices, normalizes service names, tracks source freshness, and lets patients compare clinics in one search.

## Current MVP Status

Status: Phase 1 through Phase 12 completed. Case 1 Phase A through Phase K are complete; live source scraping has not started yet.

Implemented:

- Project documentation and summary structure.
- FastAPI backend with standard JSON response and error shapes.
- PostgreSQL schema through SQLAlchemy models and Alembic migration.
- JSON import API with API key protection, import batches, import errors, deduplication, price updates, and price history.
- Search, price comparison, clinics, services, categories, and cities APIs.
- Next.js frontend with public MVP pages and manual admin import page.
- Backend tests for import, validation, edge cases, search, comparison, catalog endpoints, normalization, and database constraints.
- Docker Compose with PostgreSQL, backend, frontend, healthchecks, and backend migration startup.
- Final README, task list, and summary documentation.
- Case 1 audit, gap analysis, phased implementation prompts, and updated task board.
- Case 1 source metadata/provenance fields: data source public URL/robots/crawl metadata, per-price `source_url`, per-price `parsed_at`, and API response exposure.
- Case 1 official Excel service catalog seed from `data/reference/service_catalog.xlsx`, with 1,281 service rows, categories from `Специальность`, normalized names from `Name_ru`, and catalog matching during import.
- Case 1 parser audit model: parser runs, parser errors, raw source snapshots, raw source rows, import links, and 90-day retention fields.
- Case 1 source adapter contract documentation and three deterministic scraped-data fixture outputs for future source ingestion.
- Case 1 deterministic source fixture ingestion for three documented public sources, preserving source URL, parsed timestamp, parser run, raw snapshot, and raw row audit data.
- Case 1 unmatched service queue with normalization status/confidence and CLI inspection for unresolved rows.
- Case 1 stale/fresh data quality indicators in backend responses and frontend result/detail views.
- Case 1 frontend UX with MedServicePrice.kz positioning, visible filters, source links, parsed/update dates, freshness badges, and a comparison table.
- Case 1 demo dataset with 3 public-source fixtures, 105 current price records, 1,300 normalized catalog records after import, complete source URL / parsed timestamp coverage, and validation command.
- `DEMO.md` with setup, ingestion, validation, demo flow, presentation outline, script, limitations, and roadmap.

## Case 1 Positioning

The project should be presented as a data transparency platform, not only as a price website:

```text
Public sources -> parser/source adapters -> JSON import contract -> normalization/catalog -> PostgreSQL -> search and comparison UI
```

The existing JSON import pipeline is the core extension point. Future source adapters should transform public clinic/lab price data into the standardized import contract instead of coupling scraping logic directly to the search and comparison APIs.

## Current Case 1 Gap

The foundation already covers import, deduplication, price history, search, comparison, clinic details, frontend pages, tests, Docker, provenance, parser audit models, deterministic source ingestion, stale/fresh indicators, and demo validation. The remaining Case 1 work is focused on final stabilization and optional live-source work:

- Live scraping for public sources.
- Source adapter implementation.
- Final Docker/test validation and demo-flow freeze.

## MVP Boundaries

Included:

- Manual JSON import.
- Public search and comparison.
- Clinic and service detail views.
- Local Docker Compose run.

Not included:

- Authentication, user roles, patient accounts, booking, payments, reviews, parser service, background jobs, Redis/Celery/MinIO, Elasticsearch/OpenSearch, or production infrastructure.

## Current Limitations

- Import API uses one shared configured API key.
- Normalization is catalog-assisted and records unmatched rows for manual review, but it is still rule-based.
- Frontend verification uses lint/build rather than a dedicated browser smoke-test framework.
- Live source parsers are not implemented yet; deterministic seed-source importers are used for demo reliability.
- Parser audit records have no read endpoint or UI yet.
- Unmatched queue inspection is CLI-only.
- Autocomplete/catalog suggestion UI is not implemented.

## Run And Verification

- Backend tests: `cd backend && pytest`
- Frontend lint: `cd frontend && npm run lint`
- Frontend build: `cd frontend && npm run build`
- Demo data import: `cd backend && python -m app.scripts.import_demo_sources`
- Demo data validation: `cd backend && python -m app.scripts.validate_demo_dataset`
- Docker: `docker compose up --build`
