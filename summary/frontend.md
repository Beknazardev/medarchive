# Frontend Summary

## Purpose

The frontend provides the public MedServicePrice.kz interface and a minimal manual ingestion utility.

## Stack

- Next.js App Router
- TypeScript
- Tailwind CSS
- Minimal shadcn/ui-compatible components
- npm

## Implemented Routes

- `/`: MedServicePrice.kz home page with public-price positioning and search.
- `/search`: calls `GET /api/v1/services/search`, renders result cards, and supports URL query filters for query, city, category, min/max price, sort, and pagination.
- `/compare`: calls `GET /api/v1/prices/compare` and renders comparison stats plus a clinic price table.
- `/clinics/[id]`: calls `GET /api/v1/clinics/{id}` and shows clinic contacts, branches, service prices, source links, parsed/update dates, and freshness.
- `/services/[id]`: calls `GET /api/v1/services/{id}` and shows normalized catalog context, price stats, clinic offers, source links, parsed/update dates, and freshness.
- `/admin/import`: manual JSON import utility that calls `POST /api/v1/import/prices`.

## Components

- Layout: header, footer, container.
- UI primitives: button, input, card, badge, skeleton.
- Shared states: loading, empty, error.
- Search components: search box, visible filters, pagination, and result cards with source/freshness metadata.
- Compare components: comparison query controls, summary stats, and clinic price table.
- Detail components: clinic and service detail views with provenance and freshness fields.
- Admin component: import form with API key input, JSON textarea, example payload, summary, and errors table.

## API Client

The central API client is `frontend/lib/api.ts`.

It uses:

```text
NEXT_PUBLIC_API_BASE_URL
```

Default:

```text
http://localhost:8000
```

The admin import API key stays in React component state only and is not stored in browser storage.

## Local Run

```bash
cd frontend
npm install
npm run dev
```

## Verification

```bash
cd frontend
npm run lint
npm run build
```

Latest Phase I verification: `npm run lint` and `npm run build` passed.

## Docker

The frontend image is built from `frontend/Dockerfile` and runs with `npm run start` on port `3000`.

## Current Limitations

- No authentication, roles, booking, payments, reviews, or patient account UI.
- `/admin/import` is a single utility page, not a full admin panel.
- No autocomplete/catalog suggestion UI yet.
- Frontend smoke tests are limited to lint and production build in this MVP.
