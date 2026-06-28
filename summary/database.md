# Database Summary

## Purpose

The database stores imported sources, clinics, branches, services, current prices, price history, import batches, and import errors.

## Database

PostgreSQL for local MVP runtime. SQLite is used only for isolated backend tests.

## Implemented Tables

- `users`
- `data_sources`
- `clinics`
- `clinic_branches`
- `service_categories`
- `normalized_services`
- `services`
- `clinic_service_prices`
- `price_history`
- `price_observations`
- `import_batches`
- `import_errors`
- `parser_runs`
- `parser_errors`
- `raw_source_snapshots`
- `raw_source_rows`
- `unmatched_service_records`

## Implemented Behavior

- Current prices are stored in `clinic_service_prices`.
- Current price rows can store `source_url` and `parsed_at` separately from clinic-provided `updated_at`.
- Price changes are stored immutably in `price_history`.
- Price history snapshots preserve `source_url` and `parsed_at` for created/changed prices.
- Every successfully validated import row creates an append-only `price_observations` row, including unchanged repeats. `change_detected` distinguishes create/update observations from unchanged observations; `price_history` remains a change-event log.
- Every import creates an `import_batches` row.
- Invalid service rows can be stored in `import_errors`.
- Parser execution metadata can be stored in `parser_runs`.
- Parser failures can be stored in `parser_errors`, separate from import validation errors, with explicit `stage` and `retryable` fields.
- Raw source snapshots can store request/final URLs, HTTP status and headers, content type, byte size, a dedicated SHA-256, optional storage URI, source-document date, inline payload, and retention timestamps. Legacy `source_url` and `checksum` remain compatible.
- Row-level raw source data can be stored in `raw_source_rows` and linked to parser runs, snapshots, import batches, services, and current price rows where available. New rows receive a canonical SHA-256 `record_hash`, extraction/validation states, and structured rejection details. `record_hash` remains nullable only for a non-destructive historical-row rollout.
- Unmatched imported service names can be stored in `unmatched_service_records` for manual review. Repeated occurrences increment `occurrence_count` and update `last_seen_at`; review timestamp, reviewer, action, and note fields support a future protected review workflow.
- `services.normalization_status` and `services.normalization_confidence` record whether a row was exactly matched, alias matched, or queued as unmatched.
- Raw snapshots and rows carry `retention_until`; the MVP audit expectation is at least 90 days.
- Deduplication is supported by source, external IDs, normalized names, branch addresses, and current price uniqueness.
- Indexes support city/category/service/price filtering and PostgreSQL text search expressions.
- `data_sources` stores source metadata fields for public URL, source type, robots policy notes, crawl delay, and active status.
- `normalized_services.aliases` can store normalized aliases for the seeded service catalog, but the official Excel catalog has no explicit alias/synonym column, so current official aliases are empty.

## Service Catalog Seed

The default catalog is loaded from the official hackathon workbook rather than a migration:

```text
data/reference/service_catalog.xlsx
```

The loader reads sheet `Справочник услуг`, maps `Специальность` to `service_categories`, maps `Name_ru` to `normalized_services.name`, ignores unreliable `ID` and `Code` values, and treats `TarificatrCode` as supplemental metadata that is not persisted yet. The workbook currently yields 1,281 service rows across 122 categories.

Seed or refresh through the idempotent script:

```bash
cd backend
python -m app.scripts.seed_service_catalog
```

Verify with SQL after seeding:

```sql
SELECT count(*) FROM normalized_services;
```

The expected minimum after a clean seed is at least `50`; the official workbook currently loads 1,281 catalog rows before any duplicate slug updates.

## Migration

Initial migration:

```text
backend/alembic/versions/20260617_0001_initial_schema.py
```

Source provenance migration:

```text
backend/alembic/versions/20260626_0002_source_provenance.py
```

Parser audit migration:

```text
backend/alembic/versions/20260626_0003_parser_audit.py
```

Unmatched queue migration:

```text
backend/alembic/versions/20260626_0004_unmatched_queue.py
```

Ingestion audit and observation migration:

```text
backend/alembic/versions/20260627_0005_ingestion_audit_observations.py
```

Run locally:

```bash
cd backend
alembic -c alembic.ini upgrade head
```

Docker Compose runs migrations automatically before starting the backend:

```bash
docker compose up --build
```

## Tests

Database-related tests verify model metadata creation in SQLite and current price uniqueness constraints.

Catalog tests verify official Excel loading, at least 50 seeded normalized services, 122 catalog categories, empty aliases from the official file, and idempotent reload behavior.

Parser audit tests verify parser run/error persistence, error stage/retryability, separation from import errors, raw HTTP/content metadata, raw row hashes/status/rejections, 90-day retention fields, and links to import batches plus imported service/current price rows.

Unmatched queue tests verify exact matched, alias matched, and unmatched imported rows, including repeat occurrence auditing and preservation of raw service metadata.

Observation tests verify that repeated fixture imports keep 105 current prices and 105 price-change events while preserving 210 successful observations.

## Current Limitations

- Parser audit tables do not have read endpoints or admin UI yet.
- Unmatched queue has a CLI inspection command but no admin UI yet.
- Existing import payloads represent one exact numeric price. `from`, range, indicative, base-fee, and total-price qualifiers are intentionally deferred until the adapter contract defines unambiguous validation and current-price semantics; source values remain auditable in `raw_item`.
- Historical raw rows created before migration `20260627_0005` can have a null `record_hash`; all rows created through `ParserAuditService` after migration receive one.
- No production backup/restore or managed database setup.
- SQLite tests do not exercise every PostgreSQL-specific index type.
