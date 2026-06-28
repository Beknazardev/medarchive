# Project Summary

## Project

Medical Services Price Aggregator Kazakhstan.

## Description

MVP web service for importing medical service prices, storing current and historical prices, searching services, comparing clinic prices, and displaying results through a Next.js frontend.

The project is now being aligned to Hackathon Case 1: **MedPrice / MedServicePrice.kz**. The judge-facing position is a transparent medical price aggregator that collects public prices, normalizes service names, tracks source freshness, and lets patients compare clinics in one search.

## Current Status

Status: Phase 1 through Phase 12 and Case 1 Phase A through Phase L completed. Backend, frontend, demo-data, and Docker Compose verification pass in the current workspace.

Implemented:

- Project setup and Codex documentation.
- FastAPI backend with API v1 routing, CORS, config, database sessions, and JSON error format.
- SQLAlchemy models and Alembic migration.
- JSON import API with API key protection, deduplication, import batches, import errors, price updates, and price history.
- Search, comparison, clinics, services, categories, and cities APIs.
- Next.js frontend with home, search, compare, clinic detail, service detail, and admin import pages.
- Backend tests and frontend lint/build verification.
- Docker Compose for PostgreSQL, backend, and frontend.
- Final README and summary documentation.
- Case 1 audit, gap analysis, practical task board, and phased Codex prompts.
- Case 1 source metadata/provenance model extension with optional import fields, per-price `source_url`, per-price `parsed_at`, and API response exposure.
- Case 1 official Excel service catalog seed from `data/reference/service_catalog.xlsx`, with 1,281 service rows, categories from `Специальность`, normalized names from `Name_ru`, and catalog matching during import.
- Case 1 parser audit model with parser runs, parser errors, raw source snapshots, raw source rows, 90-day retention fields, and import links.
- Case 1 source adapter contract documentation and three deterministic scraped-data fixture outputs for future source ingestion.
- Case 1 deterministic seed-source importer for three documented public sources, preserving source URLs, parsed timestamps, parser runs, raw snapshots, and raw rows.
- Case 1 unmatched service queue with normalization status/confidence and CLI inspection for unresolved rows.
- Case 1 freshness indicators on search, compare, clinic detail, and service detail responses.
- Judge-ready Case 1 frontend with RU/KZ/EN localization, persistent light/dark themes, responsive search and comparison views, source links, parsed/update dates, and freshness badges.
- Shared multilingual query expansion for common PCR, ultrasound, MRI, CT, blood test, therapist, ECG, and X-ray aliases in both search and comparison.
- Case 1 demo dataset validation with 3 deterministic public-source fixtures, 105 current service price records, 1,300 normalized catalog records after import, and complete source URL / parsed timestamp coverage.
- `DEMO.md` with setup, ingestion, validation, demo flow, slide outline, judge-facing script, limitations, and roadmap.

Case 1 gaps still to implement:

- Live public-source scraping/parsing.
- Live source adapter implementation.

## Summary Files

| File | Purpose |
|---|---|
| `summary/project-overview.md` | MVP scope, current status, limitations, and verification commands |
| `summary/backend.md` | Backend stack, modules, endpoints, tests, Docker behavior |
| `summary/frontend.md` | Frontend routes, components, API client, verification, limitations |
| `summary/database.md` | Database tables, migrations, indexes, Docker migration behavior |
| `summary/api.md` | REST API endpoint overview, auth, errors, current status |
| `summary/import-system.md` | JSON import flow, deduplication, price updates, tests, limitations |
| `docs/codex/CASE1_MEDPRICE_AUDIT.md` | Case 1 requirements audit, gap table, priority list, demo flow, and presentation angle |
| `docs/codex/CASE1_MEDPRICE_PHASE_PROMPTS.md` | Ready-to-copy phased Codex prompts for safe Case 1 implementation |
| `docs/codex/CASE1_REPO_SNAPSHOT.md` | Phase A repo snapshot before Case 1 implementation |
| `docs/codex/CASE1_DEMO_DATASET.md` | Phase J demo dataset counts, validation command, and deduplication results |
| `DEMO.md` | Judge-facing demo setup, flow, slide outline, script, limitations, and roadmap |

## Run Commands

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

Docker:

```bash
docker compose up --build
```

## Latest Changes

- Rebuilt the frontend visual system and all existing routes for the hackathon demo, added Russian-default RU/KZ/EN localization, persistent light/dark themes, responsive comparison cards, and multilingual service query aliases.

- Completed Phase D: added parser run/error tracking, raw source snapshots, raw source rows, import links, retention fields, migration, and tests.
- Completed Phase E: documented the three-layer source adapter contract and added three deterministic scraped-data fixture outputs for Phase F.
- Completed Phase F: added deterministic source fixture ingestion for three public source pages and verified repeated-run deduplication.
- Completed Phase G: added unmatched queue records, normalization match status/confidence, CLI inspection, migration, and matched/alias/unmatched tests.
- Completed Phase H: added centralized price freshness states and exposed `freshness_state`/`freshness_age_days` in search, compare, clinic detail, and service detail responses.
- Completed Phase I core UX: repositioned frontend copy, added search filters, built comparison table, and surfaced source/freshness metadata across public views.
- Completed Phase J: expanded deterministic demo source fixtures to 105 price rows, added `validate_demo_dataset`, and verified repeated-run deduplication plus provenance coverage.
- Completed Phase K: created `DEMO.md` with exact demo commands, flow, slide outline, judge-facing script, limitations, and roadmap.
- Phase L verification: backend tests, frontend lint/build, demo validation, repeated import deduplication, and Docker Compose build/start passed.
- Completed Phase C: switched the repeatable catalog seed/import path to the official Excel workbook and verified catalog matching before fallback normalized-service creation.
- Completed Phase B: added data source metadata, per-price provenance fields, import compatibility, migration, API response fields, and TypeScript contract updates.
- Completed Case 1 alignment step: updated `TASKS.md`, created the Case 1 audit, created phased implementation prompts, and updated project summary positioning.
- Completed Phase 10: backend stabilization tests and frontend lint/build verification.
- Added focused backend tests for normalization, import edge cases, search edge cases, and database constraints.
- Completed Phase 11: Docker setup for PostgreSQL, backend, frontend, healthchecks, and backend migration startup.
- Added `backend/Dockerfile`, `frontend/Dockerfile`, `.dockerignore` files, backend `requirements.txt`, and root `docker-compose.yml`.
- Completed Phase 12: README, root summary, task list, and summary folder refresh.

## MVP Exclusions

The MVP does not include authentication, user roles, patient accounts, booking, payments, reviews, parser service, background jobs, Redis/Celery/MinIO, Elasticsearch/OpenSearch, or production infrastructure.

## Navigation For Codex

Before future changes, read:

```text
docs/codex/
TASKS.md
SUMMARY.md
summary/
```

For Case 1 work, start with:

```text
docs/codex/CASE1_MEDPRICE_AUDIT.md
docs/codex/CASE1_MEDPRICE_PHASE_PROMPTS.md
```

Keep MVP boundaries focused on Case 1 unless the user explicitly expands scope.
