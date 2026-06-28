# API Summary

## Purpose

This file documents the MVP REST API and current API state.

## Base URL

```text
/api/v1
```

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

## Authentication

Only the import endpoint requires an API key:

```http
X-API-Key: <IMPORT_API_KEY>
```

There is no user authentication or role system in the MVP.

## Common Error Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": []
  }
}
```

## Main Query Capabilities

- Service search by `q`, `city`, `category`, `min_price`, `max_price`, `sort`, `limit`, and `offset`.
- Price comparison by `service_id`, `normalized_service_id`, or `q`, with optional `city`, `category`, and sorting.
- Clinic list pagination and filters.
- Clinic and service detail lookup.
- Optional source provenance on imported and returned prices: `source_url` and `parsed_at`.
- Price freshness indicators on returned price rows: `freshness_state` and `freshness_age_days`.
- Optional source metadata on imports: `source_type`, root `source_url`, `robots_policy_notes`, and `crawl_delay_seconds`.

## Current Implementation Status

Status: MVP backend API complete through Phase 12, with Case 1 Phase B provenance fields, Phase E adapter contract documentation, Phase G unmatched queue support, and Phase H freshness indicators added.

Backend API tests cover import, search, comparison, catalog endpoints, validation, edge cases, and database constraints.

Phase E does not add endpoints or change the import API. It documents how future source adapters should transform `case1.scraped_price_list.v1` fixture/output JSON into the existing `POST /api/v1/import/prices` payload.

Phase G does not add public API endpoints. Unmatched service rows are inspected through the backend CLI command `python -m app.scripts.list_unmatched_services`.

Phase H does not add endpoints. It extends existing search, compare, clinic detail, and service detail price response objects with `freshness_state` and `freshness_age_days`. Freshness is based on `parsed_at` first and falls back to `updated_at`: `fresh` is 0-7 days old, `aging` is 8-30 days old, `stale` is older than 30 days, and `unknown` means no usable timestamp exists.

## Current Limitations

- No new endpoints beyond MVP.
- No auth/user/role endpoints.
- No booking, payments, reviews, parser, or background-job endpoints.
- No parser run, raw source snapshot, unmatched queue, or dedicated freshness endpoints yet.
