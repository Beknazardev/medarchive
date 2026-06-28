# Import System Summary

## Purpose

The import system accepts standardized JSON from external or manual sources and persists clinic, branch, service, price, history, and import metadata.

## Endpoint

```http
POST /api/v1/import/prices
```

Required header:

```http
X-API-Key: <IMPORT_API_KEY>
```

## Flow

```text
Receive JSON
Validate root payload
Create import batch
Upsert data source, clinic, and branch
Optionally link parser run and raw snapshot
Validate each service row
Match service name against the seeded official catalog
Assign normalization status and confidence
Upsert category, normalized service placeholder when needed, service, and current price
Queue unmatched service rows for manual review
Optionally write/link raw source row to imported records
Write price history for created or changed prices
Write one successful price observation, including unchanged prices
Save import errors for invalid service rows
Return import summary
```

## Source Metadata And Provenance

The import contract remains backwards compatible. Existing payloads with `source`, `clinic`, optional `branch`, and `services` continue to work.

Optional root source metadata:

- `source_type`
- `source_url`
- `robots_policy_notes`
- `crawl_delay_seconds`

Optional per-service provenance:

- `source_url`: public URL for the row or service price. If omitted, the root `source_url` is used when provided.
- `parsed_at`: timestamp when the row was parsed. If omitted, the import start time is used.

Current prices and price history store `source_url` and `parsed_at` separately from clinic-provided `updated_at`.

## Parser Audit And Raw Data

The import contract remains compatible but can carry audit links from future source adapters:

- `parser_run_id`: links the import batch to an existing parser run.
- `raw_snapshot`: optional inline raw snapshot metadata/payload for the source document or page.
- service row `raw_source_row_id`: links an imported service row to a pre-created raw source row.
- service row `raw_item`: stores row-level raw source data when no pre-created raw row exists.

Parser audit tables are separate from import error tables:

- `parser_runs`: source, status, started/finished/parsed timestamps, counts, and notes.
- `parser_errors`: parser-specific failures linked to a parser run and source, with processing stage and retryability.
- `raw_source_snapshots`: captured source page/file payloads or metadata, including optional request/final URLs, HTTP status/headers, content type, byte size, SHA-256, storage URI, and source-document date.
- `raw_source_rows`: row-level raw items linked to parser run, snapshot, import batch, service, and current price where available, with a canonical record hash plus extraction/validation/rejection state.

Raw snapshots and raw rows are retained for at least 90 days for MVP auditability through the `retention_until` field.

## Source Adapter Contract

Phase E defines the adapter-side contract in:

```text
docs/codex/CASE1_SOURCE_ADAPTER_CONTRACT.md
docs/codex/CASE1_SOURCE_ADAPTER_EXAMPLES.md
```

The contract keeps three layers separate:

```text
public source -> source adapter -> scraped-data contract -> existing import JSON -> backend import
```

Adapters should emit `case1.scraped_price_list.v1` JSON with source metadata, robots/public-data notes, clinic metadata, branch metadata when available, and raw service rows containing `source_url`, `parsed_at`, `service_name_raw`, category, price, currency, duration fields when available, and raw row metadata.

Phase F should transform that adapter output into the existing `POST /api/v1/import/prices` payload. Backend core remains independent from parser specifics, and live scraping must be replaceable with deterministic seed-source importers for demo reliability.

## Immutable Ingestion Contracts And Registry

Parser Phase C adds a source-independent foundation under:

```text
backend/app/ingestion/contracts.py
backend/app/ingestion/registry.py
```

The Pydantic contracts are frozen, reject unknown fields, use tuple-based collections, and recursively freeze raw JSON payloads. They define:

- `SourceConfig`: code-owned identity, policy state, formats, exact hosts/path prefixes/start URLs, limits, adapter version, and policy evidence;
- `SourceDocument`: requested/final HTTPS URLs, bounded response metadata, bytes or storage reference, SHA-256, capture time, and source-document date;
- `RawServiceCandidate`: source/clinic/branch/raw service data plus explicit exact/from/range/indicative/base-fee-total/on-request price semantics;
- immutable extraction/error/run results carrying a deterministic schema fingerprint.

Registry states are:

- `live`: eligible for selection only when the code-owned configuration is also enabled;
- `scaffold`: identity, policy, or stable price URL is incomplete;
- `manual_import_only`: reviewed local/public snapshots only;
- `permission_required`: written permission is required before live execution;
- `official_api_required`: official provider API only, disabled by default.

`SourceRegistry.require_live(source_id)` fails closed for every non-live or disabled state. Unknown source IDs and arbitrary user URLs are not accepted. Start URLs must be HTTPS, use an exact allowed host, stay inside allowed path prefixes, avoid forbidden prefixes, and contain no query string or fragment. The registry contains all 36 source IDs from `docs/MEDPRICE_SOURCE_POLICY_REGISTRY.md`; 2GIS and Google Places are `official_api_required`, have no HTML configuration, and remain disabled.

The new contracts do not replace or duplicate `ImportPricesRequest`. The transformation boundary remains:

```text
SourceDocument + RawServiceCandidate
-> case1.scraped_price_list.v1
-> explicit transformer
-> ImportPricesRequest
-> ImportService
```

Phase C adds no transformer, source adapter, network request, extractor, route, browser, or scheduler. Existing deterministic fixtures continue to use `case1.scraped_price_list.v1` unchanged.

## Safe Fetch And Raw Audit Infrastructure

Parser Phase D adds:

```text
backend/app/ingestion/fetcher.py
backend/app/ingestion/robots.py
backend/app/ingestion/rate_limit.py
backend/app/ingestion/storage.py
```

The fetch protocol is synchronous and intentionally runs outside FastAPI requests. It uses the existing `httpx` dependency and can later be replaced behind the protocol without changing contracts.

Before each request and redirect it verifies the registry mode, exact host, allowed/forbidden path, standard port, and DNS results. Non-public, private, loopback, link-local, multicast, reserved, and known cloud metadata addresses are rejected. HTTPS downgrade redirects, query strings, credentials, CAPTCHA/challenge responses, authentication responses, unexpected MIME types, oversized bodies, excessive redirects/pages, and unavailable/disallowing robots policy fail closed.

Robots policy is loaded with the configured MedPrice user agent, cached with `checked_at` and evidence URLs, and never bypassed after errors. Requests use one host slot by default, source-configured conservative delay, bounded safe-transient retries with jitter, and optional ETag/Last-Modified conditional headers. Authentication, CAPTCHA, policy, and validation failures are not retried.

Successful response bytes are SHA-256 hashed and must pass through a configured raw storage implementation before a document is returned for future extraction. `FilesystemRawStorage` uses content-addressed atomic files; `MemoryRawStorage` exists only for bounded tests. When database audit context is supplied, response metadata/storage URI is persisted in `raw_source_snapshots`. Final failures persist source, URL, parser stage, code, retryability, and reason in `parser_errors`.

No public API route, live source adapter, browser automation, or scheduler was added.

## Generic Document Extractors

Parser Phase E adds source-agnostic extraction utilities:

```text
backend/app/ingestion/extractors/__init__.py   # package exports and shared types
backend/app/ingestion/extractors/base.py       # ExtractionLimits, GenericTable, GenericTextBlock, error hierarchy
backend/app/ingestion/extractors/html.py       # lxml-based HTML table and text extraction
backend/app/ingestion/extractors/pdf.py        # pdfplumber tables + PyMuPDF text/scanned detection
backend/app/ingestion/extractors/docx.py       # python-docx paragraph and table extraction
backend/app/ingestion/extractors/excel.py      # openpyxl read-only/data-only XLSX extraction
backend/app/ingestion/extractors/text.py       # UTF-8 plain text line extraction
```

### Supported Formats

| Format | Library | Capabilities |
|--------|---------|-------------|
| HTML/XHTML | lxml | Tables with merged cells, text blocks (p, h1-h6), provenance |
| PDF | pdfplumber + PyMuPDF | Tables, text paragraphs, page-level provenance, scanned detection |
| DOCX | python-docx | Tables, paragraphs with style metadata, provenance |
| XLSX | openpyxl (read_only, data_only) | Multi-sheet extraction, numeric-as-text, provenance |
| Plain text | stdlib | Line-based text blocks with source URL provenance |

### Extraction Output

All extractors return `ExtractionOutput` containing:

- `tables`: tuple of `GenericTable` with rows, cells, colspans, headers, and page/sheet provenance
- `text_blocks`: tuple of `GenericTextBlock` with block type, page/sheet, and provenance
- `errors`: tuple of `ExtractorError` subclasses
- `manual_review_required`: boolean flag for scanned/uncertain documents
- `metadata`: dict with format-specific counts

### Limits

All extractors respect `ExtractionLimits`:

- Max pages/sheets: 50 (configurable)
- Max rows per table: 10,000
- Max columns per table: 100
- Max cell text length: 10,000 characters
- Max decompressed bytes: 100 MB
- Max processing time: 60 seconds
- Scanned PDF detection: <200 chars triggers manual review

### Error Hierarchy

- `ExtractorError`: base for all extraction failures
- `ManualReviewRequired`: scanned/uncertain documents
- `UnsupportedFormat`: legacy XLS, unrecognized types
- `MIMEMismatch`: content-type/extension mismatch
- `PasswordProtected`: encrypted documents
- `MalformedDocument`: corrupted or unreadable files
- `ZipBombDetected`: decompression bomb detected

### What Extractors Do Not Do

- No source-specific parsing or field mapping
- No service name normalization or database writes
- No network requests or browser automation
- No paid AI/LLM extraction
- No OCR (scanned documents flagged for manual review)

### Dependencies Added

```text
lxml>=5.0           # HTML/XML parsing and XPath
pdfplumber>=0.11.0  # Machine-generated PDF table extraction
PyMuPDF>=1.25.0     # PDF metadata, text blocks, encryption detection
python-docx>=1.1.0  # DOCX paragraph and table extraction
openpyxl>=3.1.0     # XLSX read-only/data-only extraction
```

## KDL Olymp Adapter (Phase F1)

Parser Phase F1 adds the first source-specific adapter:

```text
backend/app/ingestion/adapters/__init__.py
backend/app/ingestion/adapters/kdl_olymp.py
backend/examples/sources/kdl_olymp_adapter_output.json
backend/tests/fixtures/kdl_olymp/price_list_almaty.html
backend/tests/unit/test_kdl_olymp_adapter.py
```

### Adapter Design

The KDL Olymp adapter extracts price lists from public HTML pages:

- **Input**: `SourceDocument` with HTML content from `https://www.kdlolymp.kz/pricelist/<city>`
- **Output**: `ExtractionResult` with `RawServiceCandidate` records
- **Contract transform**: `case1.scraped_price_list.v1` → `ImportPricesRequest`

### Extracted Fields

| Field | Source | Notes |
|-------|--------|-------|
| `service_name_raw` | Table cell (column: "Наименование") | Original service text |
| `price_raw` | Table cell (column: "Цена") | Original price text with ₸ |
| `price` | Parsed numeric | Decimal value in KZT |
| `duration_days` | Table cell (column: "Срок") | Business days |
| `category_raw` | Fixed | "Лабораторные исследования" |
| `source_url` | Document URL | HTTPS with city slug |
| `row_id` | Generated | `kdl_olymp_row_NNN` |

### Schema Drift Detection

The adapter validates:
- Table headings contain expected keywords (наименование, цена)
- Minimum 3 data rows extracted
- Price values parseable as non-negative decimals

### Policy Status

- Source: `kdl_olymp` (live, P0)
- Robots: confirmed clean
- Cities: Almaty (registered only)
- Rate: 10s delay, concurrency 1
- Adapter version: 0.1.0

## Gemotest Kazakhstan Adapter (Phase F2)

Parser Phase F2 adds the second source-specific adapter:

```text
backend/app/ingestion/adapters/gemotest_kz.py
backend/examples/sources/gemotest_kz_adapter_output.json
backend/tests/fixtures/gemotest_kz/catalog_almaty.html
backend/tests/unit/test_gemotest_adapter.py
```

### Adapter Design

The Gemotest adapter extracts catalog items from public HTML pages:

- **Input**: `SourceDocument` with HTML content from `https://gemotest.kz/<city>/catalog/`
- **Output**: `ExtractionResult` with `RawServiceCandidate` records
- **Contract transform**: `case1.scraped_price_list.v1` → `ImportPricesRequest`

### Critical Semantics

| Field | Source | Semantics |
|-------|--------|-----------|
| `price` | Standard price cell | Base test price (NOT discount/bonus) |
| `additional_fee` | Biomaterial fee cell | Separate collection fee (+1090 KZT venous blood) |
| `service_external_id` | Code attribute | Specimen/code qualifier preserved |
| `raw_payload.specimen` | Specimen text | Blood/urine/saliva qualifier |
| `raw_payload.discount_raw` | Discount label | Preserved but NOT used to overwrite base price |

### Price Semantics Rules

1. **Base price is sacred**: Never overwrite with discount/bonus text
2. **Biomaterial fee is separate**: Stored in `additional_fee`, not summed
3. **No total calculation**: Unless source explicitly supplies it
4. **Specimen preserved**: Venous blood, urine, etc. kept as qualifiers
5. **Code preserved**: Test code (e.g., "9.1.") stored as `service_external_id`

### Schema Drift Detection

The adapter validates:
- Catalog items exist with `data-code` attribute
- Minimum 3 catalog items extracted
- Price values parseable as non-negative decimals
- Missing prices quarantined with error (not silently skipped)

### Policy Status

- Source: `gemotest_kz` (live, P0)
- Robots: confirmed clean (catalog paths allowed)
- Cities: Almaty (city in URL path)
- Rate: 10s delay, concurrency 1
- Adapter version: 0.1.0

## BMCUDP Adapter (Phase F3)

Parser Phase F3 adds the third source-specific adapter:

```text
backend/app/ingestion/adapters/bmcudp.py
backend/examples/sources/bmcudp_adapter_output.json
backend/tests/fixtures/bmcudp/tariff_rk_ct_mrt.html
backend/tests/unit/test_bmcudp_adapter.py
```

### Adapter Design

The BMCUDP adapter extracts tariff tables from public HTML pages:

- **Input**: `SourceDocument` with HTML content from `https://bmcudp.kz/ru/services/tsena-dlya-grazhdan-respubliki-kazakhstan/<category>/`
- **Output**: `ExtractionResult` with `RawServiceCandidate` records
- **Contract transform**: `case1.scraped_price_list.v1` → `ImportPricesRequest`

### Critical Semantics

| Field | Source | Semantics |
|-------|--------|-----------|
| `service_external_id` | Row number column | Original row code (e.g., "867") |
| `service_name_raw` | Service name column | Original service text |
| `raw_payload.unit` | Unit column | "1 исследование" |
| `raw_payload.section` | Section heading | Carried forward from merged rows |
| `raw_payload.tariff_audience` | Configured | Always "rk_citizens" |

### Tariff Namespace Protection

1. **RK citizens only**: Adapter only processes `/tsena-dlya-grazhdan-respubliki-kazakhstan/` URLs
2. **CIS/Foreign rejected**: Never mix tariff namespaces in same extraction
3. **Section headings carried**: Merged section rows propagate to subsequent data rows
4. **Row codes preserved**: Original row numbers stored as `service_external_id`

### Schema Drift Detection

The adapter validates:
- Table headings contain expected keywords (наименование, цена)
- Minimum 3 data rows extracted
- Price values parseable as positive decimals
- Zero/header rows rejected (price > 0 required)

### Policy Status

- Source: `bmcudp` (live, P0)
- Robots: confirmed clean (service pages allowed)
- Cities: Astana (RK tariff only)
- Rate: 10s delay, concurrency 1
- Adapter version: 0.1.0

## Almaty CGKB Adapter (Phase F4)

Parser Phase F4 adds the fourth source-specific adapter:

```text
backend/app/ingestion/adapters/almaty_cgkb.py
backend/examples/sources/almaty_cgkb_adapter_output.json
backend/tests/fixtures/almaty_cgkb/price_page.html
backend/tests/unit/test_almaty_cgkb_adapter.py
```

### Adapter Design

The Almaty CGKB adapter extracts tariff tables from public HTML pages:

- **Input**: `SourceDocument` with HTML content from `https://almaty-cgkb.kz/kz/prajs-parak/`
- **Output**: `ExtractionResult` with `RawServiceCandidate` records
- **Contract transform**: `case1.scraped_price_list.v1` → `ImportPricesRequest`

### Critical Semantics

| Field | Source | Semantics |
|-------|--------|-----------|
| `service_external_id` | Row number column | Original row code (e.g., "1") |
| `service_name_raw` | Service name column | Original service text |
| `raw_payload.unit` | Unit column | "1 визит", "1 исследование", etc. |
| `raw_payload.section` | Section heading | Carried forward from merged rows |
| `raw_payload.tariff_audience` | Configured | Always "almaty_residents" |

### Authoritative Source Decision

1. **HTML is primary**: Price page is the authoritative source
2. **Downloads are cross-check**: Laboratory documents are secondary validation only
3. **No double-counting**: Same price not imported from both HTML and download
4. **Section headings carried**: Merged section rows propagate to subsequent data rows

### Schema Drift Detection

The adapter validates:
- Table headings contain expected keywords (наименование, цена)
- Minimum 3 data rows extracted
- Price values parseable as positive decimals
- Zero/header rows rejected (price > 0 required)

### Policy Status

- Source: `almaty_cgkb` (live, P0/P1)
- Robots: confirmed clean (price page allowed)
- Cities: Almaty
- Rate: 15s delay, concurrency 1
- Adapter version: 0.1.0

## Magnesia City-Aware Adapter (Phase F5)

Parser Phase F5 adds the fifth source-specific adapter family:

```text
backend/app/ingestion/adapters/magnesia.py
backend/examples/sources/magnesia_adapter_output.json
backend/tests/fixtures/magnesia/pavlodar_kt.html
backend/tests/unit/test_magnesia_adapter.py
```

### Approved Cities

| City | Subdomain | Paths | Address |
|------|-----------|-------|---------|
| Павлодар | `pavlodar.magnesia.kz` | `/kt/`, `/cena/` | ул. Ермака, 15/2 |
| Семей | `semey.magnesia.kz` | `/cena/` | ул. Достоевского, 22 |
| Костанай | `kostanay.magnesia.kz` | `/kt/`, `/mrt/`, `/cena/` | ул. Байтурсынова, 50 |

### Adapter Design

The Magnesia adapter is city-aware:

- **Input**: `SourceDocument` with HTML content from `<city>.magnesia.kz`
- **Output**: `ExtractionResult` with `RawServiceCandidate` records
- **Contract transform**: `case1.scraped_price_list.v1` → `ImportPricesRequest`

### Critical Semantics

| Field | Source | Semantics |
|-------|--------|-----------|
| `clinic_external_id` | URL subdomain | `magnesia_<city>` |
| `clinic_city` | URL subdomain | City name |
| `clinic_address` | City config | Branch address |
| `raw_payload.has_contrast` | Service name | Contrast qualifier |
| `raw_payload.weight_qualifier` | Service name | Weight range qualifier |

### City Isolation

1. **City from URL**: Subdomain determines city scope
2. **City validation**: Only approved cities accepted
3. **Branch identity**: City + address in clinic/branch identity
4. **No cross-city mixing**: Each extraction is city-scoped

### Qualifier Preservation

1. **Contrast preserved**: `has_contrast` flag for contrast studies
2. **Weight preserved**: Weight range qualifiers (e.g., "вес от 61 кг")
3. **Body part preserved**: Section headings (e.g., "Область головы")
4. **Package preserved**: Contrast amount + weight as separate qualifiers

### Schema Drift Detection

The adapter validates:
- Table headings contain expected keywords (кт, мрт, цена)
- Minimum 3 data rows extracted
- Price values parseable as positive decimals
- City in approved list

### Policy Status

- Source: `magnesia` (live, P0/P1)
- Robots: confirmed clean (HTML paths only, no XLS)
- Cities: Павлодар, Семей, Костанай
- Rate: 15s delay per subdomain, concurrency 1
- Adapter version: 0.1.0

## GPK/Hippokrat Adapter (Phase F6)

Parser Phase F6 adds the sixth source-specific adapter:

```text
backend/app/ingestion/adapters/gpk_hippokrat.py
backend/examples/sources/gpk_hippokrat_adapter_output.json
backend/tests/fixtures/gpk_hippokrat/price_list.html
backend/tests/unit/test_gpk_hippokrat_adapter.py
```

### Adapter Design

The GPK/Hippokrat adapter extracts large irregular price tables:

- **Input**: `SourceDocument` with HTML content from `https://gpk.kz/прайс-лист`
- **Output**: `ExtractionResult` with `RawServiceCandidate` records
- **Contract transform**: `case1.scraped_price_list.v1` → `ImportPricesRequest`

### Irregular Row Handling

| Pattern | Decision |
|---------|----------|
| **Section headings** | Merged rows detected, section name carried forward |
| **Parent services** | Rows ending with `:` treated as parent, sub-services prefixed |
| **Side-by-side prices** | Primary (7000) and repeat (6000) split into separate services |
| **Empty price rows** | Skipped (parent service headers) |
| **Note rows** | Rejected (containing "примечание", "cito") |
| **Irregular numbering** | Row codes preserved as-is (e.g., "3,10", "5.5,1") |

### Service Name Construction

```python
# Parent service: "Первичный прием (консультация) врача специалиста:"
# Sub-service: "уролог"
# Result: "Первичный прием (консультация) врача специалиста уролог"
```

### Quarantined Cases

1. **"Cito +50%"**: Note row detected and rejected
2. **Bundles**: Package text preserved in raw but not split
3. **Source typos**: Row codes preserved as-is (e.g., "3,10" instead of "3.10")
4. **Ambiguous cells**: Empty prices rejected, parent rows skipped

### Schema Drift Detection

The adapter validates:
- Table headings contain expected keywords (наименование, цена)
- Minimum 10 data rows extracted (large table required)
- Price values parseable as positive decimals
- Section headings detected and carried forward

### Policy Status

- Source: `gpk_hippokrat` (live, P0/P1)
- Robots: confirmed clean (price page allowed)
- Cities: Костанай
- Rate: 15s delay, concurrency 1
- Adapter version: 0.1.0

## Invitro Kazakhstan (Phase F7 — BLOCKED)

Parser Phase F7 documents the Invitro permission gate:

```text
No adapter implemented.
Status: permission_required
Blocker: Written permission required per site footer.
```

### Permission Gate Decision

| Check | Result |
|-------|--------|
| Official identity | Confirmed: `invitro.kz` |
| robots.txt | Confirmed: disallows results, booking, query URLs |
| Site footer/copyright | "Копирование и иное использование материалов сайта требует письменного разрешения" |
| Written permission | **NOT OBTAINED** |
| Bulk automated reuse | **NOT PERMITTED** |

### Blocked Reason

The site footer explicitly states that copying or other use of site materials requires written permission. No such permission has been obtained or documented.

### Manual Fixture Import Fallback

If manual price data is provided by Invitro or obtained through authorized channels:

1. Create a JSON fixture following `case1.scraped_price_list.v1` contract
2. Place in `examples/sources/invitro_kz_adapter_output.json`
3. Import via `SourceFixtureImportService.import_fixture()`
4. No automated fetching or parsing

### What Would Be Required for Approval

1. Written permission from Invitro Kazakhstan for automated price data collection
2. Documentation of permitted scope (cities, pages, frequency)
3. Confirmation that data can be redistributed to patients
4. Policy registry update with approval evidence

### Policy Status

- Source: `invitro_kz` (**BLOCKED**)
- Permission: **NOT OBTAINED**
- Adapter: **NOT IMPLEMENTED**
- Manual import: Available as fallback

Example adapter outputs live in:

```text
examples/sources/source_1_adapter_output.json
examples/sources/source_2_adapter_output.json
examples/sources/source_3_adapter_output.json
```

## Demo Source Importer

Phase F adds a deterministic seed-source importer:

```bash
cd backend
python -m app.scripts.import_demo_sources
```

It reads the three fixture files, seeds the official Excel catalog unless `--skip-catalog-seed` is passed, creates parser run records, creates raw snapshots, transforms rows into `ImportPricesRequest`, and calls the existing `ImportService`.

Phase J expands those fixtures to 105 deterministic current service price rows: 35 rows per public source fixture.

Selected public sources and crawl notes are documented in:

```text
docs/codex/CASE1_SOURCES.md
```

Command-level deduplication was verified against an isolated SQLite database. First run imported 105 created prices; second run imported the same fixtures as 105 unchanged prices with 0 errors.

Validate a prepared database with:

```bash
cd backend
python -m app.scripts.validate_demo_dataset
```

The validation command checks at least 3 sources, at least 100 current service price records, at least 50 normalized catalog records, and complete current-price `source_url` / `parsed_at` coverage.

## Deduplication Rules

- Data source: by name.
- Clinic: by `data_source_id + external_id`, fallback normalized name and city.
- Branch: by `clinic_id + external_id`, fallback normalized address.
- Category: by normalized name.
- Normalized service: seeded catalog exact match first, optional alias match if aliases exist, fallback to one `unmatched service` placeholder per category.
- Service: by `data_source_id + external_id`, fallback normalized service and normalized name.
- Current price: by `clinic_id + branch_id + service_id + currency`.

## Unmatched Queue

Phase G adds unmatched service queue behavior. Each imported service receives:

- `normalization_status`: `matched`, `alias_matched`, `unmatched`, or legacy `fallback`.
- `normalization_confidence`: `1.0` for exact catalog matches, `0.9` for alias matches, and `0.0` for unmatched rows.

When a row cannot be matched to the official catalog, the import still succeeds for compatibility. The service is linked to a generic `unmatched service` normalized-service placeholder for its category instead of creating a new low-quality normalized catalog entry from the raw source name. An `unmatched_service_records` row is created or updated with raw values, provenance, confidence, occurrence/first-seen/last-seen audit fields, future review audit fields, and links to the imported service/raw row where available.

Inspect unresolved rows with:

```bash
cd backend
python -m app.scripts.list_unmatched_services
```

Use `--status all` to include resolved or historical rows, and `--limit N` to adjust output size.

## Catalog Matching

The default catalog is loaded with:

```bash
cd backend
python -m app.scripts.seed_service_catalog
```

The seed command reads the official workbook at `data/reference/service_catalog.xlsx`. It uses sheet `Справочник услуг`, maps `Специальность` to categories, maps `Name_ru` to normalized service names, ignores unreliable `ID` and `Code` values, and treats `TarificatrCode` as supplemental metadata that is not persisted yet.

On import, service names are normalized and checked against the seeded catalog's normalized names before a new normalized service is created. The model still supports aliases if future catalog data provides them, but the official workbook has no explicit alias/synonym column, so current official aliases are empty.

## Price Update Rules

- New price creates current price and `price_history`.
- Same price updates `last_seen_at` and does not create duplicate history.
- Changed price updates current price and creates `price_history`.
- Every successfully validated row creates one immutable `price_observations` record. This includes unchanged repeats and does not alter `price_history` semantics.
- Same-price imports still refresh `source_url`, `parsed_at`, `last_seen_at`, `updated_at`, and availability on the current price without creating duplicate history.
- Imports linked to parser runs increment imported counts and can create/link raw rows without turning parser errors into import errors.

## Frontend Import UI

The frontend has a manual import utility at:

```text
/admin/import
```

It keeps the API key only in component state and does not provide authentication or roles.

## Tests

Backend tests cover:

- successful import;
- invalid API key;
- validation errors;
- duplicate import;
- price update;
- partial success;
- missing branch default behavior;
- zero price;
- 100-service payload.
- source metadata and price provenance;
- backwards-compatible imports without provenance.
- official Excel catalog loading and idempotent reload;
- catalog matching during import.
- parser run/error persistence;
- raw snapshot and raw row persistence with imported-record links.
- successful unchanged observation persistence without false price-change events;
- raw snapshot HTTP/content metadata, raw-row hashes/status/rejections, parser-error stage/retryability, and unmatched occurrence auditing.

## Current Limitations

- API key is a single shared configured value.
- Normalization is catalog-assisted but still deterministic and rule-based.
- No live parser service or live source adapters yet; Phase F uses deterministic seed-source importers.
- Parser audit records have no read endpoint or UI yet.
- No background import jobs.
- No full admin panel.
- The current JSON contract models one exact numeric price. Qualifier/range/base-fee/total fields are deferred until source-adapter contracts define safe semantics.
- Generic extractors return raw tables/text blocks; source-specific field mapping requires adapters (Phase F+).
- Legacy XLS format is rejected; users must convert to XLSX before import.
- Scanned/low-text PDFs are flagged for manual review; no OCR in MVP.
