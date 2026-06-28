# MedServicePrice.kz Demo

## Positioning

MedServicePrice.kz is a transparent public medical price aggregator for Kazakhstan. It collects public clinic and lab price data, normalizes service names against an official catalog, stores source/audit metadata, tracks freshness, and lets patients compare clinics in one search.

## Prerequisites

- Docker Desktop for the full local stack, or local PostgreSQL plus Python/Node for manual runs.
- Backend environment from `.env.example`.
- Frontend environment variable:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Full Local Demo Setup

Start the app stack:

```bash
docker compose up --build
```

Open:

```text
http://localhost:3000
```

The backend is available at:

```text
http://localhost:8000
```

## Manual Backend Setup

Run migrations and backend locally:

```bash
cd backend
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
python -m app.scripts.seed_service_catalog
uvicorn app.main:app --reload
```

Run frontend locally:

```bash
cd frontend
npm install
npm run dev
```

## Demo Data Ingestion

Import the deterministic Case 1 public-source fixtures:

```bash
cd backend
python -m app.scripts.import_demo_sources
```

This command:

- seeds the official Excel service catalog from `data/reference/service_catalog.xlsx`;
- imports 3 documented public-source fixtures from `examples/sources/`;
- creates 105 current service price records;
- preserves source URLs and parsed timestamps;
- creates parser runs, raw snapshots, and raw source rows;
- uses the existing JSON import pipeline.

Run the command a second time to show deduplication:

```bash
cd backend
python -m app.scripts.import_demo_sources
```

Expected second-run behavior:

```text
created=0 updated=0 unchanged=105 errors=0
```

## Demo Dataset Validation

Validate readiness:

```bash
cd backend
python -m app.scripts.validate_demo_dataset
```

Expected successful output shape:

```text
source_count=3 minimum=3
service_price_count=105 minimum=100
normalized_catalog_count>=50
missing_source_url_count=0
missing_parsed_at_count=0
ready=true
```

Phase J isolated verification result:

```text
source_count=3 minimum=3
service_price_count=105 minimum=100
normalized_catalog_count=1300 minimum=50
missing_source_url_count=0
missing_parsed_at_count=0
parser_run_count=6
ready=true
```

## Suggested Demo Flow

1. Open `http://localhost:3000`.
2. Introduce MedServicePrice.kz as a transparent public-price aggregator, not a booking service.
3. Show the ingestion command and explain the source adapter flow:

```text
public source -> deterministic source fixture/importer -> JSON import contract -> backend validation -> catalog matching -> PostgreSQL -> search/compare UI
```

4. Run or show `python -m app.scripts.validate_demo_dataset`.
5. Search for a common query:

```text
PCR
```

Switch `RU | KZ | EN` and repeat with `ПЦР`, `ПТР`, or `polymerase chain reaction` to demonstrate multilingual query aliases without translating source-provided service names.

6. Apply filters:

```text
City: Shymkent
Category: PCR diagnostics
Sort: Price low to high
```

7. Open a result card and point out:

- raw service name;
- normalized catalog behavior;
- clinic and address;
- price;
- source link;
- parsed timestamp;
- clinic update date;
- freshness badge.

8. Open Compare from a result or visit:

```text
http://localhost:3000/compare?q=PCR
```

9. Show the comparison stats and clinic price table.
10. Open a clinic detail page and show branches, contacts, service list, source links, and freshness data.
11. Close on architecture and data quality: public-source provenance, raw audit data, deduplication, normalized catalog, and stale-price handling.

## Useful Demo URLs

```text
http://localhost:3000
http://localhost:3000/search?q=PCR
http://localhost:3000/search?q=ПЦР
http://localhost:3000/search?q=УЗИ
http://localhost:3000/search?q=consultation
http://localhost:3000/search?q=ultrasound&city=Astana
http://localhost:3000/compare?q=PCR
http://localhost:3000/compare?q=ПЦР
http://localhost:3000/compare?q=consultation
```

## Source Coverage

| Source | Fixture | Rows | Mode |
|---|---|---:|---|
| BMCUDP public functional diagnostics price page | `examples/sources/source_1_adapter_output.json` | 35 | deterministic fixture |
| KSCDID public medical services price list | `examples/sources/source_2_adapter_output.json` | 35 | deterministic fixture |
| DTL DNA Laboratory Shymkent public price page | `examples/sources/source_3_adapter_output.json` | 35 | deterministic fixture |

Public-data and robots notes are documented in `docs/codex/CASE1_SOURCES.md`.

## Slide Outline

1. **Problem**
   Patients compare medical prices manually across clinic/lab websites. Price data is fragmented, inconsistent, and often lacks visible update/source context.

2. **Solution**
   MedServicePrice.kz aggregates public prices into one searchable and comparable interface with source links and freshness indicators.

3. **Data Pipeline**
   Public source pages are represented by deterministic seed-source importers for demo reliability. The architecture keeps adapter output separate from the backend import contract.

4. **Data Quality**
   Each price stores `source_url`, `parsed_at`, clinic-provided `updated_at`, parser/raw audit records, deduplication state, and freshness status.

5. **Catalog Normalization**
   The official Excel service catalog provides 1,281 normalized services across 122 categories. Imports match catalog records first and queue unmatched service names for review.

6. **User Experience**
   Users search by service, filter by city/category/price/sort, compare clinics, and open clinic/service details with contacts, source links, dates, and freshness badges.

7. **Demo And Roadmap**
   Current demo: 3 public sources, 105 price records, complete source/timestamp coverage, repeatable import. Roadmap: live adapters, parser UI, unmatched review UI, production hardening.

## Judge-Facing Script

MedServicePrice.kz solves a practical transparency problem: patients need to compare medical service prices, but public prices are scattered across clinic and laboratory websites.

Our approach is not just a frontend search page. The core is a data pipeline. Public source data is transformed into a stable JSON contract, validated by the backend, matched against an official normalized service catalog, and stored with source and audit metadata.

For demo reliability, the three public sources are represented as deterministic source fixtures. That avoids live-site instability and avoids generating load during judging, while preserving the same fields a live adapter would send: source URL, parsed timestamp, raw service name, category, price, currency, and raw row metadata.

The demo dataset has 3 sources and 105 current service price records. Every current price has a source URL and parsed timestamp. The official Excel catalog loads more than 50 normalized services; in the verified run it loaded 1,300 normalized catalog records after source import. Running the importer twice proves deduplication: the second run creates no new current prices and marks all 105 as unchanged.

In the UI, users can switch Russian, Kazakh, and English, choose light or dark theme, search with multilingual aliases, filter by city/category/price, compare clinics, and inspect clinic/service details. Price cards and tables show the public source, parsed date, clinic update date, and freshness state so older data does not look fully current.

The main limitation is that this demo uses deterministic importers rather than live scraping. The architecture is ready for live adapters because scraper-specific logic stays outside the backend core.

## Known Limitations

- Live scraping is not implemented in this phase.
- Demo ingestion uses deterministic public-source fixtures for reliability and to avoid load on public sites.
- Working hours and duration fields are preserved as raw metadata where there is no dedicated product field yet.
- Parser runs and raw rows have no read-only UI yet.
- The unmatched queue is inspectable by CLI, not by an admin panel.
- Autocomplete/catalog suggestion UI is not implemented.
- Docker Compose is local demo infrastructure, not production deployment infrastructure.

## Roadmap

- Implement live adapters for the three documented public sources with crawl-delay safeguards.
- Add read-only parser/source run visibility.
- Add unmatched-service review UI.
- Add catalog autocomplete in search.
- Add demo-source coverage dashboard.
- Harden production deployment, auth, observability, and backup operations.

## Verification Commands

Backend tests:

```bash
cd backend
pytest
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

Demo validation:

```bash
cd backend
python -m app.scripts.validate_demo_dataset
```
