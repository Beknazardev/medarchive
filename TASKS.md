# TASKS

## Status legend

- [ ] Not started
- [x] Done
- [~] In progress
- [!] Blocked

# Case 1: MedPrice / MedServicePrice.kz

Current positioning: **MedServicePrice.kz — a transparent medical price aggregator that collects public prices, normalizes service names, tracks source freshness, and lets patients compare clinics in one search.**

This task board preserves the completed MVP foundation and adds the Case 1 work needed for the hackathon brief.

## Completed MVP Foundation

### Phase 1: Project setup

- [x] Create project structure
- [x] Create `backend/`
- [x] Create `frontend/`
- [x] Create `docs/codex/`
- [x] Create `summary/`
- [x] Add `.gitignore`
- [x] Add `.env.example`
- [x] Add root `README.md`
- [x] Add root `SUMMARY.md`

### Phase 2: Backend skeleton

- [x] Initialize FastAPI app
- [x] Add `/health`
- [x] Add config management
- [x] Add database connection
- [x] Add API v1 router
- [x] Add error response format
- [x] Add CORS config

### Phase 3: Database

- [x] Add SQLAlchemy models
- [x] Add Alembic
- [x] Create initial migration
- [x] Add indexes
- [x] Test migration on empty database

### Phase 4: JSON import

- [x] Add import Pydantic schemas
- [x] Add validation rules
- [x] Add API key protection
- [x] Implement data_source upsert
- [x] Implement clinic upsert
- [x] Implement branch upsert
- [x] Implement category upsert
- [x] Implement normalized service upsert
- [x] Implement service upsert
- [x] Implement price upsert
- [x] Implement price history
- [x] Implement import batches
- [x] Implement import errors
- [x] Add `POST /api/v1/import/prices`

### Phase 5: Search

- [x] Implement SearchService
- [x] Add `GET /api/v1/services/search`
- [x] Add city filter
- [x] Add category filter
- [x] Add price filters
- [x] Add pagination
- [x] Add sorting

### Phase 6: Price comparison

- [x] Implement PriceComparisonService
- [x] Add `GET /api/v1/prices/compare`
- [x] Compare by service_id
- [x] Compare by normalized_service_id
- [x] Compare by query
- [x] Add min/max/average stats
- [x] Add sorting by price

### Phase 7: Clinics and services API

- [x] Add `GET /api/v1/clinics`
- [x] Add `GET /api/v1/clinics/{id}`
- [x] Add `GET /api/v1/services/{id}`
- [x] Add `GET /api/v1/categories`
- [x] Add `GET /api/v1/cities`

### Phase 8: Frontend

- [x] Initialize Next.js + TypeScript
- [x] Configure Tailwind CSS
- [x] Add shadcn/ui-compatible primitives
- [x] Create layout
- [x] Create home page
- [x] Create search page
- [x] Create comparison page
- [x] Create clinic page
- [x] Create service page
- [x] Create API client
- [x] Add loading states
- [x] Add empty states
- [x] Add error states

### Phase 9: Admin import page

- [x] Create `/admin/import`
- [x] Add JSON textarea
- [x] Add example JSON
- [x] Add API key input
- [x] Call import API
- [x] Show import summary
- [x] Show import errors

### Phase 10: Tests

- [x] Add backend unit tests
- [x] Add validation tests
- [x] Add API tests
- [x] Add database tests
- [x] Add import edge case tests
- [x] Add search edge case tests
- [x] Add frontend lint/build verification

### Phase 11: Docker

- [x] Add backend Dockerfile
- [x] Add frontend Dockerfile
- [x] Add `docker-compose.yml`
- [x] Add postgres service
- [x] Verify `docker compose up --build`

### Phase 12: Foundation documentation

- [x] Update `README.md`
- [x] Update `SUMMARY.md`
- [x] Update `summary/project-overview.md`
- [x] Update `summary/backend.md`
- [x] Update `summary/frontend.md`
- [x] Update `summary/database.md`
- [x] Update `summary/api.md`
- [x] Update `summary/import-system.md`

## Case 1 Alignment and Planning

### Phase A: Case 1 final audit and repo snapshot

- [x] Read Case 1 MedPrice brief from `ТЗ_Кейс1_MedPrice.docx`
- [x] Audit existing docs, backend, frontend, and summaries
- [x] Create `docs/codex/CASE1_MEDPRICE_AUDIT.md`
- [x] Create `docs/codex/CASE1_MEDPRICE_PHASE_PROMPTS.md`
- [x] Create `docs/codex/CASE1_REPO_SNAPSHOT.md`
- [x] Reframe task board for Case 1
- [x] Update root `SUMMARY.md` with Case 1 alignment status
- [x] Update `summary/project-overview.md` with Case 1 positioning and gaps

## Case 1 Implementation Phases

### Phase B: Source metadata model extension

- [x] Audit current `data_sources`, `clinic_service_prices`, `price_history`, and import schema against Case 1 provenance fields
- [x] Design fields for `source_url` per price row
- [x] Design `parsed_at` timestamp semantics separate from clinic-provided `updated_at`
- [x] Design source metadata fields: public URL, source type, robots policy notes, crawl delay, active flag
- [x] Design display fields needed by UI without changing contracts prematurely
- [x] Add tests plan for provenance fields
- [x] Update docs after implementation

### Phase C: Service catalog seed/import for normalized services

- [x] Inspect official catalog workbook at `data/reference/service_catalog.xlsx`
- [x] Load normalized services from sheet `Справочник услуг`
- [x] Map categories from `Специальность`
- [x] Map normalized service names from `Name_ru`
- [x] Avoid trusting `ID` and `Code` because the workbook contains many `#REF!` formula errors
- [x] Treat `TarificatrCode` as supplemental metadata only and do not persist it yet
- [x] Document that the official workbook has no explicit aliases/synonyms column
- [x] Decide whether seed data is migration-based, JSON-based, or script-based
- [x] Add repeatable catalog seed/import path
- [x] Verify at least 50 normalized catalog records can be loaded
- [x] Add tests for official Excel loading and catalog-based normalization behavior
- [x] Update docs with catalog source and maintenance workflow

### Phase D: Raw data and parser run tracking

- [x] Design raw source snapshot storage for audit
- [x] Design parser run table or equivalent tracking for source, status, started_at, finished_at, parsed_at, counts, and errors
- [x] Distinguish import errors from parser errors
- [x] Store raw item references linked to imported normalized records where practical
- [x] Define retention expectation: raw data stored at least 90 days for MVP audit
- [x] Add tests for parser run/error persistence
- [x] Update docs with raw/audit model

### Phase E: Demo source adapters and scraped-data JSON contract

- [x] Define a scraped-data JSON contract that maps adapter output into existing `POST /api/v1/import/prices`
- [x] Include `source_url`, `parsed_at`, `service_name_raw`, `duration_days` where applicable
- [x] Document required adapter output validation
- [x] Document source adapter interface boundaries
- [x] Document robots.txt and public-data checks before adapter execution
- [x] Add fixture examples for three future demo sources
- [x] Keep backend core independent from parser implementation

### Phase F: Implement 3 source ingestion adapters or seed-source importers

- [x] Select at least 3 public sources for MVP demo
- [x] Document source URLs, data type, city/market coverage, robots.txt awareness, and load limits
- [x] Implement deterministic seed-source importer for source 1
- [x] Implement deterministic seed-source importer for source 2
- [x] Implement deterministic seed-source importer for source 3
- [x] Ensure repeated adapter/import runs deduplicate existing clinics, services, and prices
- [x] Ensure every imported price has a source URL and parsed timestamp
- [x] Provide manual command to run source fixture ingestion
- [x] Add adapter/import tests and fixtures

### Phase G: Unmatched queue and normalization improvements

- [x] Design unmatched queue for raw service names not confidently matched to a catalog service
- [x] Add confidence/status fields and queue records for manual review
- [x] Improve normalization to use the seeded catalog before creating new normalized services (completed in Phase C)
- [x] Add documented command path to inspect unresolved services
- [x] Add tests for matched, alias-matched, and unmatched cases
- [x] Update docs with manual matching workflow

### Phase H: Stale price and data quality indicators

- [x] Define price freshness states: fresh, aging, stale, unknown
- [x] Treat data older than 30 days as not fully current
- [x] Add backend stale/fresh indicators to search, compare, clinic, and service responses
- [x] Add source freshness summary per clinic/service where useful
- [x] Add tests for freshness thresholds
- [x] Update docs with freshness semantics

### Phase I: Frontend Case 1 UX improvements

- [x] Reposition UI copy around MedServicePrice.kz and transparent public prices
- [x] Add visible filters for city, category, price range, and sorting
- [x] Add source URL and parsed/updated date display in result cards
- [x] Add stale/fresh badges and explanatory labels
- [x] Upgrade compare page from placeholder to useful comparison table
- [x] Improve clinic card/details with contacts, website, all services, source links, and freshness
- [ ] Add autocomplete or catalog suggestions if time allows
- [x] Verify responsive behavior on mobile and desktop
- [x] Run frontend lint/build

### Phase J: Demo dataset and 100 services validation

- [x] Build or import demo dataset with at least 3 public sources
- [x] Ensure at least 100 service price records are present
- [x] Ensure at least 50 normalized catalog positions are present
- [x] Ensure source URL exists for every price
- [x] Ensure parsed timestamp exists for every price
- [x] Ensure deduplication works on repeated import/parser run
- [x] Add validation command or documented SQL checks for demo readiness
- [x] Save demo verification results in documentation

### Phase K: `DEMO.md` and presentation script

- [x] Create `DEMO.md`
- [x] Document exact demo setup commands
- [x] Document parser/import run command or UI workflow
- [x] Document demo search queries and expected results
- [x] Draft 5-7 slide presentation outline
- [x] Add judge-facing story: data quality, UX, technical architecture, market coverage, extras
- [x] Document known limitations honestly

### Phase L: Final stabilization, tests, Docker validation

- [x] Run backend tests
- [x] Run frontend lint
- [x] Run frontend production build
- [x] Run Docker Compose validation
- [x] Validate seed/demo import from a clean database
- [x] Validate repeated parser/import deduplication
- [x] Review docs for consistency with final implementation
- [x] Freeze final demo flow

## Do Not Build Now

- [ ] Patient accounts
- [ ] Authentication and user roles beyond existing import API key
- [ ] Online booking
- [ ] Payments
- [ ] Reviews
- [ ] Medical diagnosis/recommendation features
- [ ] Heavy search infrastructure unless PostgreSQL search becomes insufficient
- [ ] Production deployment hardening beyond local/demo Docker needs

## Future Public-Source Parser Work

- [x] Research all requested Kazakhstan public price sources and map the plan to the existing import/audit models
- [x] Create sequential Codex prompts for parser phases A-O with per-source safety gates
- [x] Complete Phase A repository re-audit and create the full source policy registry
- [x] Recheck official identity, robots.txt, terms, allowed paths, and rate limits immediately before implementing each source
- [x] Add only the missing parser/raw-observation schema fields; reuse `data_sources`, parser audit, raw rows, normalized services, unmatched records, price history, and current prices
- [x] Preserve unchanged successful observations in `price_observations` without creating false `price_history` events
- [x] Add immutable adapter contracts and a source registry with `live`, `scaffold`, `manual_import_only`, `permission_required`, and `official_api_required` states
- [x] Add bounded fetch, robots, SSRF/redirect protection, rate limiting, conditional requests, raw storage, and stage-specific run errors
- [x] Add fixture-tested generic HTML, PDF, DOCX, and XLSX extractors
- [x] Implement approved P0 adapters one source at a time without bypassing access controls
- [x] Add the generic reviewed city/regional clinic document adapter
- [x] Expand exact synonym normalization and add safe fuzzy suggestions without paid-AI dependency
- [x] Add protected unmatched-service review API/admin UI
- [x] Add dry-run/manual CLI execution before scheduled execution
- [x] Add per-source locks and cron-compatible scheduled runs
- [x] Align freshness states to fresh 0-30 days, stale 31-90 days, and expired over 90 days
- [ ] Keep 2GIS and Google Places enrichment disabled unless official API keys, terms, attribution, budget, and storage rules are configured
- [x] Preserve deterministic fixture ingestion as the hackathon fallback and verify repeat-run idempotency
