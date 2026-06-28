"""AlatauLab adapter - extracts medical analysis prices from public HTML pages."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.ingestion.contracts import (
    ExtractionError,
    ExtractionResult,
    ParserStage,
    PriceQualifier,
    RawServiceCandidate,
    SourceDocument,
)

ADAPTER_VERSION = "0.1.0"
SOURCE_ID = "alataulab_kz"

EXPECTED_HEADINGS = {"наименование", "название", "исследование", "анализ", "услуга"}
EXPECTED_PRICE_HEADINGS = {"цена", "стоимость", "тенге", "₸", "₽"}
MIN_ROWS = 3


def extract_alataulab(document: SourceDocument) -> ExtractionResult:
    """Extract service/price rows from an AlatauLab HTML price list page."""
    content = document.content_bytes or b""
    errors: list[ExtractionError] = []
    candidates: list[RawServiceCandidate] = []

    try:
        from lxml import html as lxml_html
        if isinstance(content, bytes):
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("latin-1")
            doc = lxml_html.fromstring(text)
        else:
            doc = lxml_html.fromstring(content)
    except Exception as exc:
        errors.append(
            ExtractionError(
                source_id=SOURCE_ID,
                stage=ParserStage.EXTRACT,
                code="HTML_PARSE_ERROR",
                message=f"Failed to parse HTML: {exc}",
                source_url=document.final_url,
            )
        )
        return ExtractionResult(
            source_id=SOURCE_ID,
            adapter_version=ADAPTER_VERSION,
            documents=(document,),
            errors=tuple(errors),
        )

    tables = doc.xpath("//table")
    if not tables:
        errors.append(
            ExtractionError(
                source_id=SOURCE_ID,
                stage=ParserStage.EXTRACT,
                code="NO_PRICE_TABLE",
                message="No tables found in document",
                source_url=document.final_url,
            )
        )
        return ExtractionResult(
            source_id=SOURCE_ID,
            adapter_version=ADAPTER_VERSION,
            documents=(document,),
            errors=tuple(errors),
        )

    now = datetime.now(UTC)
    city = _extract_city_from_url(document.final_url)

    for table in tables:
        header_row = _get_header_row(table)
        if header_row is None:
            continue

        col_map = _map_columns(header_row)
        if "name" not in col_map or "price" not in col_map:
            continue

        data_rows = _get_data_rows(table)
        if len(data_rows) < MIN_ROWS:
            continue

        current_section = _detect_section_before_table(table, doc)

        for row_idx, row in enumerate(data_rows):
            cells = _get_row_cells(row)
            if not cells:
                continue

            section_text = _detect_section_row(cells)
            if section_text:
                current_section = section_text
                continue

            name = _get_cell_text(cells, col_map.get("name"))
            price_text = _get_cell_text(cells, col_map.get("price"))
            duration_text = _get_cell_text(cells, col_map.get("duration")) if "duration" in col_map else ""
            code = _get_cell_text(cells, col_map.get("code")) if "code" in col_map else ""

            if not name or not price_text:
                continue

            price = _parse_price(price_text)
            if price is None or price <= 0:
                continue

            duration_days = _parse_duration(duration_text)
            row_number = row_idx + 1

            candidates.append(
                RawServiceCandidate(
                    source_id=SOURCE_ID,
                    clinic_external_id=SOURCE_ID,
                    clinic_name="AlatauLab",
                    clinic_city=city,
                    service_external_id=code if code else None,
                    service_name_raw=name,
                    category_raw=current_section or "Лабораторные исследования",
                    price_raw=price_text,
                    price_qualifier=PriceQualifier.EXACT,
                    price=price,
                    currency="KZT",
                    duration_days=duration_days,
                    duration_raw=duration_text,
                    source_url=document.final_url,
                    parsed_at=now,
                    raw_payload={
                        "row_number": row_number,
                        "code": code,
                        "section": current_section,
                        "cells": tuple(c for c in cells),
                    },
                )
            )

    return ExtractionResult(
        source_id=SOURCE_ID,
        adapter_version=ADAPTER_VERSION,
        documents=(document,),
        candidates=tuple(candidates),
        errors=tuple(errors),
    )


def transform_to_scraped_contract(
    extraction: ExtractionResult,
    *,
    robots_checked_at: str = "2026-06-27T17:45:00+05:00",
    robots_notes: str = "Public AlatauLab price list page. F0 policy rechecked.",
) -> dict[str, Any]:
    """Transform extraction result into case1.scraped_price_list.v1 contract."""
    source_url = ""
    parsed_at = ""
    if extraction.documents:
        source_url = extraction.documents[0].final_url
    if extraction.candidates:
        parsed_at = extraction.candidates[0].parsed_at.isoformat()

    rows = []
    for candidate in extraction.candidates:
        row = {
            "row_id": f"alataulab_kz_row_{candidate.raw_payload.get('row_number', 0):03d}",
            "source_url": candidate.source_url,
            "parsed_at": candidate.parsed_at.isoformat(),
            "service_name_raw": candidate.service_name_raw,
            "service_category_raw": candidate.category_raw,
            "price_raw": candidate.price_raw,
            "price": float(candidate.price) if candidate.price else 0,
            "currency": candidate.currency,
            "updated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
            "duration_days": candidate.duration_days,
            "duration_raw": candidate.duration_raw,
            "service_code": candidate.raw_payload.get("code"),
            "section": candidate.raw_payload.get("section"),
            "is_available": True,
            "raw": {
                "row_number": candidate.raw_payload.get("row_number", 0),
                "code": candidate.raw_payload.get("code"),
                "section": candidate.raw_payload.get("section"),
                "cells": list(candidate.raw_payload.get("cells", [])),
            },
        }
        rows.append(row)

    return {
        "contract_version": "case1.scraped_price_list.v1",
        "source": {
            "id": SOURCE_ID,
            "name": "AlatauLab",
            "type": "public_price_list",
            "source_url": source_url,
            "parsed_at": parsed_at,
            "robots": {
                "checked_at": robots_checked_at,
                "allowed": True,
                "crawl_delay_seconds": 10,
                "notes": robots_notes,
            },
            "adapter": {
                "name": "alataulab_kz",
                "version": ADAPTER_VERSION,
                "mode": "deterministic_fixture",
            },
        },
        "clinic": {
            "external_id": SOURCE_ID,
            "name": "AlatauLab",
            "legal_name": None,
            "city": _extract_city_from_url(source_url),
            "address": None,
            "phone": None,
            "website": "https://alataulab.kz",
            "working_hours": None,
        },
        "branches": [],
        "rows": rows,
    }


def transform_to_import_payload(
    contract: dict[str, Any],
) -> Any:
    """Transform scraped contract into ImportPricesRequest-compatible payload."""
    from app.schemas.import_prices import ImportPricesRequest

    source = contract["source"]
    clinic = contract["clinic"]
    robots = source.get("robots", {})

    services = []
    for row in contract["rows"]:
        service = {
            "external_id": row["row_id"],
            "name": row["service_name_raw"],
            "category": row.get("service_category_raw") or "Uncategorized",
            "price": row["price"],
            "currency": row["currency"],
            "updated_at": row["updated_at"],
            "source_url": row.get("source_url"),
            "parsed_at": row.get("parsed_at"),
            "is_available": row.get("is_available", True),
            "raw_item": row,
        }
        if row.get("duration_days") is not None:
            service["duration_minutes"] = row["duration_days"] * 24 * 60
        services.append(service)

    return ImportPricesRequest.model_validate(
        {
            "source": source["id"],
            "source_type": source.get("type") or "public_price_list",
            "source_url": source["source_url"],
            "robots_policy_notes": robots.get("notes"),
            "crawl_delay_seconds": robots.get("crawl_delay_seconds"),
            "source_batch_id": f"{source['id']}:{source.get('parsed_at', '')}",
            "clinic": {
                "external_id": clinic["external_id"],
                "name": clinic["name"],
                "legal_name": clinic.get("legal_name"),
                "city": clinic["city"],
                "address": clinic.get("address"),
                "phone": clinic.get("phone"),
                "website": clinic.get("website"),
            },
            "branch": None,
            "services": services,
        }
    )


# --- Internal helpers ---


def _extract_city_from_url(url: str) -> str:
    """Extract city name from URL path."""
    url_lower = url.lower()
    city_map = {
        "/almaty/": "Алматы",
        "/astana/": "Астана",
        "/shymkent/": "Шымкент",
        "/karaganda/": "Караганда",
    }
    for path_part, city_name in city_map.items():
        if path_part in url_lower:
            return city_name
    return "Алматы"


def _get_header_row(table: Any) -> list[str] | None:
    """Extract header texts from the table."""
    thead = table.xpath(".//thead/tr")
    if thead:
        ths = thead[0].xpath(".//th")
        if ths:
            return [_clean_text(th.text_content()) for th in ths]

    first_row = table.xpath(".//tr")
    if first_row:
        cells = first_row[0].xpath(".//th | .//td")
        if cells:
            texts = [_clean_text(c.text_content()) for c in cells]
            if any(
                any(kw in t.lower() for kw in EXPECTED_HEADINGS)
                for t in texts
            ):
                return texts
    return None


def _map_columns(headings: list[str]) -> dict[str, int]:
    """Map column roles to indices."""
    mapping: dict[str, int] = {}
    for idx, h in enumerate(headings):
        hl = h.lower()
        if any(kw in hl for kw in {"№", "п/п", "номер", "код", "порядковый"}):
            mapping["code"] = idx
        elif any(kw in hl for kw in EXPECTED_HEADINGS):
            mapping["name"] = idx
        elif any(kw in hl for kw in EXPECTED_PRICE_HEADINGS):
            mapping["price"] = idx
        elif any(kw in hl for kw in {"срок", "дни", "день", "время"}):
            mapping["duration"] = idx
    return mapping


def _get_data_rows(table: Any) -> list[Any]:
    """Get data rows (skip header)."""
    all_rows = table.xpath(".//tr")
    if not all_rows:
        return []

    header = _get_header_row(table)
    if header is None:
        return all_rows[1:] if len(all_rows) > 1 else []

    data_rows = []
    for row in all_rows[1:]:
        cells = row.xpath(".//td")
        if cells:
            data_rows.append(row)
    return data_rows


def _get_row_cells(row: Any) -> list[str]:
    """Get cell texts from a row."""
    cells = row.xpath(".//td | .//th")
    return [_clean_text(c.text_content()) for c in cells]


def _get_cell_text(cells: list[str], col_idx: int | None) -> str:
    """Get text from a specific column, or empty string."""
    if col_idx is None or col_idx >= len(cells):
        return ""
    return cells[col_idx]


def _detect_section_row(cells: list[str]) -> str | None:
    """Detect if a row is a section heading."""
    if len(cells) == 1:
        text = cells[0].strip()
        if text and len(text) > 2:
            return text
    if len(cells) > 1 and all(c.strip() == "" for c in cells[1:]):
        text = cells[0].strip()
        if text and len(text) > 2:
            return text
    return None


def _detect_section_before_table(table: Any, doc: Any) -> str:
    """Detect section heading before a table element."""
    prev = table.getprevious()
    while prev is not None:
        tag = prev.tag.lower() if hasattr(prev, 'tag') else ''
        if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            text = _clean_text(prev.text_content())
            if text:
                return text
        prev = prev.getprevious()
    return "Лабораторные исследования"


def _parse_price(text: str) -> Decimal | None:
    """Parse a price string into Decimal."""
    cleaned = re.sub(r"[^\d.,]", "", text)
    cleaned = cleaned.replace(",", "")
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
        if value >= 0:
            return value
    except (InvalidOperation, ValueError):
        pass
    return None


def _parse_duration(text: str) -> int | None:
    """Parse duration text into days."""
    if not text:
        return None
    match = re.search(r"(\d+)", text)
    if match:
        days = int(match.group(1))
        if 0 < days <= 365:
            return days
    return None


def _clean_text(text: str) -> str:
    """Clean and normalize text content."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned
