"""Magnesia city-aware adapter - extracts CT/MRI tariff tables from city subdomains."""

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
SOURCE_ID = "magnesia"

CITY_CONFIGS: dict[str, dict[str, Any]] = {
    "pavlodar": {
        "name": "Магнезия",
        "city": "Павлодар",
        "address": "Павлодар, ул. Ермака, 15/2",
        "paths": ["/kt/", "/cena/"],
    },
    "semey": {
        "name": "Магнезия",
        "city": "Семей",
        "address": "Семей, ул. Достоевского, 22",
        "paths": ["/cena/"],
    },
    "kostanay": {
        "name": "Магнезия",
        "city": "Костанай",
        "address": "Костанай, ул. Байтурсынова, 50",
        "paths": ["/kt/", "/mrt/", "/cena/"],
    },
}

EXPECTED_HEADINGS = {"компьютерная томография", "кт", "мрт", "услуга", "наименование"}
EXPECTED_PRICE_HEADINGS = {"цена", "стоимость", "тенге", "₸"}
MIN_ROWS = 3


def extract_magnesia(document: SourceDocument) -> ExtractionResult:
    """Extract CT/MRI tariff rows from a Magnesia city HTML page."""
    content = document.content_bytes or b""
    errors: list[ExtractionError] = []
    candidates: list[RawServiceCandidate] = []

    city = _detect_city_from_url(document.final_url)
    if city not in CITY_CONFIGS:
        errors.append(
            ExtractionError(
                source_id=SOURCE_ID,
                stage=ParserStage.VALIDATE,
                code="UNKNOWN_CITY",
                message=f"City '{city}' is not in approved city list",
                source_url=document.final_url,
            )
        )
        return ExtractionResult(
            source_id=SOURCE_ID,
            adapter_version=ADAPTER_VERSION,
            documents=(document,),
            errors=tuple(errors),
        )

    city_config = CITY_CONFIGS[city]

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

    table = _find_price_table(doc)
    if table is None:
        errors.append(
            ExtractionError(
                source_id=SOURCE_ID,
                stage=ParserStage.EXTRACT,
                code="NO_PRICE_TABLE",
                message="No price table found in document",
                source_url=document.final_url,
            )
        )
        return ExtractionResult(
            source_id=SOURCE_ID,
            adapter_version=ADAPTER_VERSION,
            documents=(document,),
            errors=tuple(errors),
        )

    header_row = _get_header_row(table)
    if header_row is None:
        errors.append(
            ExtractionError(
                source_id=SOURCE_ID,
                stage=ParserStage.EXTRACT,
                code="NO_HEADER_ROW",
                message="No header row found in price table",
                source_url=document.final_url,
            )
        )
        return ExtractionResult(
            source_id=SOURCE_ID,
            adapter_version=ADAPTER_VERSION,
            documents=(document,),
            errors=tuple(errors),
        )

    if not _validate_headings(header_row):
        errors.append(
            ExtractionError(
                source_id=SOURCE_ID,
                stage=ParserStage.VALIDATE,
                code="SCHEMA_DRIFT",
                message="Table headings do not match expected Magnesia schema",
                source_url=document.final_url,
            )
        )
        return ExtractionResult(
            source_id=SOURCE_ID,
            adapter_version=ADAPTER_VERSION,
            documents=(document,),
            errors=tuple(errors),
        )

    col_map = _map_columns(header_row)
    data_rows = _get_data_rows(table)

    if len(data_rows) < MIN_ROWS:
        errors.append(
            ExtractionError(
                source_id=SOURCE_ID,
                stage=ParserStage.VALIDATE,
                code="INSUFFICIENT_ROWS",
                message=f"Expected at least {MIN_ROWS} data rows, found {len(data_rows)}",
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
    current_section = ""

    for row_idx, row in enumerate(data_rows):
        cells = _get_row_cells(row)
        if not cells:
            continue

        section_text = _detect_section_row(cells)
        if section_text:
            current_section = section_text
            continue

        row_code = _get_cell_text(cells, col_map.get("code"))
        name = _get_cell_text(cells, col_map.get("name"))
        price_text = _get_cell_text(cells, col_map.get("price"))

        if not name or not price_text:
            continue

        price = _parse_price(price_text)
        if price is None or price <= 0:
            continue

        has_contrast = "контраст" in name.lower()
        weight_qualifier = _extract_weight_qualifier(name)
        row_number = row_idx + 1

        candidates.append(
            RawServiceCandidate(
                source_id=SOURCE_ID,
                clinic_external_id=f"magnesia_{city}",
                clinic_name=city_config["name"],
                clinic_city=city_config["city"],
                clinic_address=city_config["address"],
                service_external_id=row_code if row_code else None,
                service_name_raw=name,
                category_raw="КТ и МРТ",
                price_raw=price_text,
                price_qualifier=PriceQualifier.EXACT,
                price=price,
                currency="KZT",
                source_url=document.final_url,
                parsed_at=now,
                raw_payload={
                    "row_number": row_number,
                    "row_code": row_code,
                    "section": current_section,
                    "city": city,
                    "has_contrast": has_contrast,
                    "weight_qualifier": weight_qualifier,
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
    robots_notes: str = "Public Magnesia city page. F0 policy rechecked.",
) -> dict[str, Any]:
    """Transform extraction result into case1.scraped_price_list.v1 contract."""
    source_url = ""
    parsed_at = ""
    city = "Алматы"
    if extraction.documents:
        source_url = extraction.documents[0].final_url
        city = _detect_city_from_url(source_url)
    if extraction.candidates:
        parsed_at = extraction.candidates[0].parsed_at.isoformat()
        city = extraction.candidates[0].clinic_city

    city_config = CITY_CONFIGS.get(city.lower().replace(" ", ""), {})
    clinic_name = city_config.get("name", "Магнезия")
    clinic_address = city_config.get("address")

    rows = []
    for candidate in extraction.candidates:
        row = {
            "row_id": f"magnesia_{candidate.raw_payload.get('city', 'unknown')}_row_{candidate.raw_payload.get('row_number', 0):03d}",
            "source_url": candidate.source_url,
            "parsed_at": candidate.parsed_at.isoformat(),
            "service_name_raw": candidate.service_name_raw,
            "service_category_raw": candidate.category_raw,
            "price_raw": candidate.price_raw,
            "price": float(candidate.price) if candidate.price else 0,
            "currency": candidate.currency,
            "updated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
            "row_code": candidate.raw_payload.get("row_code"),
            "section": candidate.raw_payload.get("section"),
            "city": candidate.raw_payload.get("city"),
            "has_contrast": candidate.raw_payload.get("has_contrast", False),
            "weight_qualifier": candidate.raw_payload.get("weight_qualifier"),
            "is_available": True,
            "raw": {
                "row_number": candidate.raw_payload.get("row_number", 0),
                "row_code": candidate.raw_payload.get("row_code"),
                "section": candidate.raw_payload.get("section"),
                "city": candidate.raw_payload.get("city"),
                "has_contrast": candidate.raw_payload.get("has_contrast", False),
                "weight_qualifier": candidate.raw_payload.get("weight_qualifier"),
                "cells": list(candidate.raw_payload.get("cells", [])),
            },
        }
        rows.append(row)

    return {
        "contract_version": "case1.scraped_price_list.v1",
        "source": {
            "id": SOURCE_ID,
            "name": "Магнезия",
            "type": "public_price_list",
            "source_url": source_url,
            "parsed_at": parsed_at,
            "robots": {
                "checked_at": robots_checked_at,
                "allowed": True,
                "crawl_delay_seconds": 15,
                "notes": robots_notes,
            },
            "adapter": {
                "name": "magnesia",
                "version": ADAPTER_VERSION,
                "mode": "deterministic_fixture",
            },
        },
        "clinic": {
            "external_id": f"magnesia_{city.lower().replace(' ', '_')}",
            "name": clinic_name,
            "legal_name": 'ТОО "Центр МРТ Магнесия Казахстан"',
            "city": city,
            "address": clinic_address,
            "phone": None,
            "website": f"https://{city.lower().replace(' ', '')}.magnesia.kz",
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


# ─── Internal helpers ───


def _detect_city_from_url(url: str) -> str:
    """Extract city name from URL subdomain."""
    url_lower = url.lower()
    for city in CITY_CONFIGS:
        if f"{city}.magnesia.kz" in url_lower:
            return city
    return "unknown"


def _find_price_table(doc: Any) -> Any | None:
    """Find the price table in the HTML document."""
    for table in doc.xpath("//table"):
        rows = table.xpath(".//tr")
        if len(rows) >= MIN_ROWS + 1:
            return table
    return None


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


def _validate_headings(headings: list[str]) -> bool:
    """Validate that headings match expected Magnesia schema."""
    lower_headings = [h.lower() for h in headings]
    has_name = any(
        any(kw in h for kw in EXPECTED_HEADINGS) for h in lower_headings
    )
    has_price = any(
        any(kw in h for kw in EXPECTED_PRICE_HEADINGS) for h in lower_headings
    )
    return has_name and has_price


def _map_columns(headings: list[str]) -> dict[str, int]:
    """Map column roles to indices."""
    mapping: dict[str, int] = {}
    for idx, h in enumerate(headings):
        hl = h.lower()
        if any(kw in hl for kw in {"№", "п/п", "номер", "порядковый"}):
            mapping["code"] = idx
        elif any(kw in hl for kw in EXPECTED_HEADINGS):
            mapping["name"] = idx
        elif any(kw in hl for kw in EXPECTED_PRICE_HEADINGS):
            mapping["price"] = idx
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
    """Detect if a row is a section heading (merged cell or bold text)."""
    if len(cells) == 1:
        text = cells[0].strip()
        if text and len(text) > 2:
            return text
    if len(cells) > 1 and all(c.strip() == "" for c in cells[1:]):
        text = cells[0].strip()
        if text and len(text) > 2:
            return text
    return None


def _extract_weight_qualifier(name: str) -> str | None:
    """Extract weight qualifier from service name."""
    match = re.search(r"вес\s+(?:от\s+)?(\d+)\s*(?:кг)?", name.lower())
    if match:
        return match.group(0)
    return None


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


def _clean_text(text: str) -> str:
    """Clean and normalize text content."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned
