"""Gemotest Kazakhstan adapter - extracts catalog items from public HTML pages."""

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
SOURCE_ID = "gemotest_kz"
DEFAULT_BIOMATERIAL_FEE = Decimal("1090")
MIN_ITEMS = 3


def extract_gemotest(document: SourceDocument) -> ExtractionResult:
    """Extract catalog items from a Gemotest HTML catalog page."""
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

    items = doc.xpath("//div[@data-code]")
    if not items:
        items = doc.xpath("//div[contains(@class, 'catalog-item') and @data-code]")

    if not items:
        errors.append(
            ExtractionError(
                source_id=SOURCE_ID,
                stage=ParserStage.EXTRACT,
                code="NO_CATALOG_ITEMS",
                message="No catalog items found in document",
                source_url=document.final_url,
            )
        )
        return ExtractionResult(
            source_id=SOURCE_ID,
            adapter_version=ADAPTER_VERSION,
            documents=(document,),
            errors=tuple(errors),
        )

    if len(items) < MIN_ITEMS:
        errors.append(
            ExtractionError(
                source_id=SOURCE_ID,
                stage=ParserStage.VALIDATE,
                code="INSUFFICIENT_ITEMS",
                message=f"Expected at least {MIN_ITEMS} catalog items, found {len(items)}",
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

    for item_idx, item in enumerate(items):
        code = item.get("data-code", "").strip()
        name = _extract_text(item, ".//span[contains(@class, 'item-name')]")
        specimen = _extract_text(item, ".//span[contains(@class, 'item-specimen')]")
        duration_text = _extract_text(item, ".//span[contains(@class, 'item-duration')]")
        discount_text = _extract_text(item, ".//span[contains(@class, 'discount-label')]")

        price_text, biomaterial_fee_text = _extract_prices(item)
        price = _parse_price(price_text)
        biomaterial_fee = _parse_price(biomaterial_fee_text)

        if not name:
            continue

        if price is None:
            errors.append(
                ExtractionError(
                    source_id=SOURCE_ID,
                    stage=ParserStage.VALIDATE,
                    code="MISSING_PRICE",
                    message=f"Item '{name}' has no parseable price",
                    source_url=document.final_url,
                )
            )
            continue

        duration_days = _parse_duration(duration_text)
        row_number = item_idx + 1

        candidates.append(
            RawServiceCandidate(
                source_id=SOURCE_ID,
                clinic_external_id=SOURCE_ID,
                clinic_name="Гемотест",
                clinic_city=city,
                service_external_id=code if code else None,
                service_name_raw=name,
                category_raw="Лабораторные исследования",
                price_raw=price_text,
                price_qualifier=PriceQualifier.EXACT,
                price=price,
                additional_fee=biomaterial_fee,
                currency="KZT",
                duration_days=duration_days,
                duration_raw=duration_text,
                source_url=document.final_url,
                parsed_at=now,
                raw_payload={
                    "row_number": row_number,
                    "code": code,
                    "specimen": specimen,
                    "biomaterial_fee_raw": biomaterial_fee_text,
                    "discount_raw": discount_text,
                    "name_raw": name,
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
    robots_notes: str = "Public Gemotest catalog page. F0 policy rechecked.",
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
            "row_id": f"gemotest_kz_row_{candidate.raw_payload.get('row_number', 0):03d}",
            "source_url": candidate.source_url,
            "parsed_at": candidate.parsed_at.isoformat(),
            "service_name_raw": candidate.service_name_raw,
            "service_category_raw": candidate.category_raw,
            "price_raw": candidate.price_raw,
            "price": float(candidate.price) if candidate.price else 0,
            "biomaterial_fee": float(candidate.additional_fee) if candidate.additional_fee else 0,
            "biomaterial_fee_raw": candidate.raw_payload.get("biomaterial_fee_raw"),
            "currency": candidate.currency,
            "updated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
            "duration_days": candidate.duration_days,
            "duration_raw": candidate.duration_raw,
            "service_code": candidate.raw_payload.get("code"),
            "specimen": candidate.raw_payload.get("specimen"),
            "discount_raw": candidate.raw_payload.get("discount_raw"),
            "is_available": True,
            "raw": {
                "row_number": candidate.raw_payload.get("row_number", 0),
                "code": candidate.raw_payload.get("code"),
                "specimen": candidate.raw_payload.get("specimen"),
                "name_raw": candidate.raw_payload.get("name_raw"),
            },
        }
        rows.append(row)

    return {
        "contract_version": "case1.scraped_price_list.v1",
        "source": {
            "id": SOURCE_ID,
            "name": "Гемотест",
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
                "name": "gemotest_kz",
                "version": ADAPTER_VERSION,
                "mode": "deterministic_fixture",
            },
        },
        "clinic": {
            "external_id": SOURCE_ID,
            "name": "Гемотест",
            "legal_name": "ООО «Лаборатория Гемотест»",
            "city": _extract_city_from_url(source_url),
            "address": None,
            "phone": None,
            "website": "https://gemotest.kz",
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


# ─── Internal helpers ───


def _extract_text(element: Any, xpath: str) -> str:
    """Extract text from an XPath expression."""
    results = element.xpath(xpath)
    if results:
        return _clean_text(results[0].text_content())
    return ""


def _extract_prices(item: Any) -> tuple[str, str]:
    """Extract standard price and biomaterial fee from an item."""
    price_text = ""
    fee_text = ""

    standard_prices = item.xpath(".//div[contains(@class, 'price-standard')]//span[contains(@class, 'price-value')]")
    if standard_prices:
        price_text = _clean_text(standard_prices[0].text_content())

    fee_elements = item.xpath(".//div[contains(@class, 'biomaterial-fee')]//span[contains(@class, 'fee-value')]")
    if fee_elements:
        fee_text = _clean_text(fee_elements[0].text_content())

    if not price_text:
        all_prices = item.xpath(".//span[contains(@class, 'price-value')]")
        if all_prices:
            price_text = _clean_text(all_prices[0].text_content())

    return price_text, fee_text


def _extract_city_from_url(url: str) -> str:
    """Extract city name from URL path."""
    url_lower = url.lower()
    city_map = {
        "/almaty/": "Алматы",
        "/astana/": "Астана",
        "/shymkent/": "Шымкент",
        "/karaganda/": "Караганда",
        "/aktobe/": "Актобе",
        "/pavlodar/": "Павлодар",
        "/uralsk/": "Уральск",
        "/temirtau/": "Темиртау",
        "/kostanay/": "Костанай",
        "/petropavlovsk/": "Петропавловск",
        "/aktau/": "Актау",
        "/ekibastuz/": "Экибастуз",
        "/turkestan/": "Туркестан",
        "/taraz/": "Тараз",
    }
    for path_part, city_name in city_map.items():
        if path_part in url_lower:
            return city_name
    return "Алматы"


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
