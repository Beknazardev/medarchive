"""Generic city/regional clinic document adapter driven by reviewed mapping profiles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.ingestion.contracts import (
    ExtractionError,
    ExtractionResult,
    ParserStage,
    PriceQualifier,
    RawServiceCandidate,
    SourceDocument,
)

ADAPTER_VERSION = "0.1.0"
SOURCE_ID = "city_clinic_document"


class ProfileColumnMapping(BaseModel):
    """Maps source columns to extraction fields."""

    service_name: int = Field(ge=0)
    price: int = Field(ge=0)
    code: int | None = None
    unit: int | None = None
    category: int | None = None
    duration: int | None = None
    section: int | None = None


class ProfileValidation(BaseModel):
    """Validation rules for extracted data."""

    min_rows: int = Field(default=3, ge=1)
    max_rows: int = Field(default=10000, ge=1)
    min_price: Decimal = Field(default=Decimal("0"))
    max_price: Decimal = Field(default=Decimal("100000000"))
    required_columns: list[int] = Field(default_factory=list)
    header_aliases: dict[str, list[str]] = Field(default_factory=dict)


class ClinicIdentity(BaseModel):
    """Clinic metadata for the profile."""

    external_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = None
    city: str = Field(min_length=1, max_length=100)
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    working_hours: str | None = None


class DocumentClassifier(BaseModel):
    """Assertions for document classification."""

    expected_format: Literal["html", "pdf", "docx", "xlsx", "xls"]
    min_tables: int = Field(default=1, ge=0)
    max_tables: int = Field(default=100, ge=1)
    min_text_length: int = Field(default=100, ge=0)
    scan_detection: bool = Field(default=True)
    tariff_audience: str = Field(default="rk_citizens")
    required_text_patterns: list[str] = Field(default_factory=list)
    forbidden_text_patterns: list[str] = Field(default_factory=list)


class MappingProfile(BaseModel):
    """Immutable mapping profile for a specific clinic document."""

    profile_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    profile_version: str = Field(min_length=1, pattern=r"^\d+\.\d+\.\d+$")
    source_id: str = Field(default=SOURCE_ID, pattern=r"^[a-z0-9_]+$")
    approved_hosts: list[str] = Field(default_factory=list)
    approved_paths: list[str] = Field(default_factory=list)
    expected_checksums: list[str] = Field(default_factory=list)
    document: DocumentClassifier
    clinic: ClinicIdentity
    table_selection: dict[str, Any] = Field(
        default_factory=lambda: {"index": 0, "min_rows": 3}
    )
    columns: ProfileColumnMapping
    validation: ProfileValidation = Field(default_factory=ProfileValidation)
    publication_mode: Literal["dry_run", "manual_review", "live"] = "manual_review"
    reviewer: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None

    @field_validator("expected_checksums")
    @classmethod
    def validate_checksums(cls, v: list[str]) -> list[str]:
        for checksum in v:
            if len(checksum) != 64 or not all(c in "0123456789abcdef" for c in checksum):
                raise ValueError(f"Invalid SHA-256 checksum: {checksum}")
        return v


@dataclass(frozen=True)
class ExtractedRow:
    """A row extracted from a document using a profile."""

    profile_id: str
    row_number: int
    service_name: str
    price: Decimal
    price_raw: str
    code: str | None = None
    unit: str | None = None
    category: str | None = None
    section: str | None = None
    duration_raw: str | None = None
    cells: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileExtractionResult:
    """Result of extracting data using a profile."""

    profile_id: str
    accepted: tuple[ExtractedRow, ...]
    quarantined: tuple[ExtractedRow, ...]
    rejected: tuple[ExtractedRow, ...]
    errors: tuple[ExtractionError, ...]
    metadata: dict[str, Any]


def load_profile(profile_path: Path) -> MappingProfile:
    """Load a mapping profile from a JSON file."""
    import json

    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return MappingProfile.model_validate(data)


def extract_with_profile(
    document: SourceDocument,
    profile: MappingProfile,
) -> ProfileExtractionResult:
    """Extract data from a document using a mapping profile."""
    from app.ingestion.extractors.html import extract_html
    from app.ingestion.extractors.pdf import extract_pdf
    from app.ingestion.extractors.docx import extract_docx
    from app.ingestion.extractors.excel import extract_excel

    content = document.content_bytes or b""
    errors: list[ExtractionError] = []
    accepted: list[ExtractedRow] = []
    quarantined: list[ExtractedRow] = []
    rejected: list[ExtractedRow] = []

    try:
        if profile.document.expected_format == "html":
            output = extract_html(content, source_url=document.final_url)
        elif profile.document.expected_format == "pdf":
            output = extract_pdf(content, source_url=document.final_url)
        elif profile.document.expected_format == "docx":
            output = extract_docx(content, source_url=document.final_url)
        elif profile.document.expected_format in ("xlsx", "xls"):
            output = extract_excel(content, source_url=document.final_url)
        else:
            errors.append(
                ExtractionError(
                    source_id=profile.source_id,
                    stage=ParserStage.EXTRACT,
                    code="UNSUPPORTED_FORMAT",
                    message=f"Format {profile.document.expected_format} not supported",
                )
            )
            return ProfileExtractionResult(
                profile_id=profile.profile_id,
                accepted=(),
                quarantined=(),
                rejected=(),
                errors=tuple(errors),
                metadata={},
            )
    except Exception as exc:
        errors.append(
            ExtractionError(
                source_id=profile.source_id,
                stage=ParserStage.EXTRACT,
                code="EXTRACTION_FAILED",
                message=f"Extraction failed: {exc}",
            )
        )
        return ProfileExtractionResult(
            profile_id=profile.profile_id,
            accepted=(),
            quarantined=(),
            rejected=(),
            errors=tuple(errors),
            metadata={},
        )

    if output.manual_review_required:
        errors.append(
            ExtractionError(
                source_id=profile.source_id,
                stage=ParserStage.EXTRACT,
                code="MANUAL_REVIEW_REQUIRED",
                message="Document requires manual review (scanned/low confidence)",
            )
        )
        return ProfileExtractionResult(
            profile_id=profile.profile_id,
            accepted=(),
            quarantined=(),
            rejected=(),
            errors=tuple(errors),
            metadata={"manual_review": True},
        )

    table_index = profile.table_selection.get("index", 0)
    if table_index >= len(output.tables):
        errors.append(
            ExtractionError(
                source_id=profile.source_id,
                stage=ParserStage.VALIDATE,
                code="TABLE_NOT_FOUND",
                message=f"Table index {table_index} not found; {len(output.tables)} tables available",
            )
        )
        return ProfileExtractionResult(
            profile_id=profile.profile_id,
            accepted=(),
            quarantined=(),
            rejected=(),
            errors=tuple(errors),
            metadata={"table_count": len(output.tables)},
        )

    table = output.tables[table_index]
    row_number = 0

    for generic_row in table.rows:
        if generic_row.is_header:
            continue

        row_number += 1
        cells = tuple(c.text for c in generic_row.cells)

        if len(cells) <= max(
            profile.columns.service_name,
            profile.columns.price,
        ):
            rejected.append(
                ExtractedRow(
                    profile_id=profile.profile_id,
                    row_number=row_number,
                    service_name="",
                    price=Decimal("0"),
                    price_raw="",
                    cells=cells,
                    errors=("Row too short for column mapping",),
                )
            )
            continue

        service_name = cells[profile.columns.service_name].strip()
        price_text = cells[profile.columns.price].strip()

        if not service_name:
            rejected.append(
                ExtractedRow(
                    profile_id=profile.profile_id,
                    row_number=row_number,
                    service_name="",
                    price=Decimal("0"),
                    price_raw=price_text,
                    cells=cells,
                    errors=("Empty service name",),
                )
            )
            continue

        price = _parse_price(price_text)
        if price is None:
            quarantined.append(
                ExtractedRow(
                    profile_id=profile.profile_id,
                    row_number=row_number,
                    service_name=service_name,
                    price=Decimal("0"),
                    price_raw=price_text,
                    cells=cells,
                    errors=(f"Cannot parse price: {price_text}",),
                )
            )
            continue

        if price < profile.validation.min_price or price > profile.validation.max_price:
            quarantined.append(
                ExtractedRow(
                    profile_id=profile.profile_id,
                    row_number=row_number,
                    service_name=service_name,
                    price=price,
                    price_raw=price_text,
                    cells=cells,
                    errors=(f"Price {price} outside bounds [{profile.validation.min_price}, {profile.validation.max_price}]",),
                )
            )
            continue

        code = (
            cells[profile.columns.code].strip()
            if profile.columns.code is not None and profile.columns.code < len(cells)
            else None
        )
        unit = (
            cells[profile.columns.unit].strip()
            if profile.columns.unit is not None and profile.columns.unit < len(cells)
            else None
        )
        category = (
            cells[profile.columns.category].strip()
            if profile.columns.category is not None and profile.columns.category < len(cells)
            else None
        )
        section = (
            cells[profile.columns.section].strip()
            if profile.columns.section is not None and profile.columns.section < len(cells)
            else None
        )
        duration_raw = (
            cells[profile.columns.duration].strip()
            if profile.columns.duration is not None and profile.columns.duration < len(cells)
            else None
        )

        row_errors: list[str] = []
        if profile.validation.required_columns:
            for col_idx in profile.validation.required_columns:
                if col_idx < len(cells) and not cells[col_idx].strip():
                    row_errors.append(f"Required column {col_idx} is empty")

        if row_errors:
            quarantined.append(
                ExtractedRow(
                    profile_id=profile.profile_id,
                    row_number=row_number,
                    service_name=service_name,
                    price=price,
                    price_raw=price_text,
                    code=code,
                    unit=unit,
                    category=category,
                    section=section,
                    duration_raw=duration_raw,
                    cells=cells,
                    errors=tuple(row_errors),
                )
            )
            continue

        accepted.append(
            ExtractedRow(
                profile_id=profile.profile_id,
                row_number=row_number,
                service_name=service_name,
                price=price,
                price_raw=price_text,
                code=code,
                unit=unit,
                category=category,
                section=section,
                duration_raw=duration_raw,
                cells=cells,
            )
        )

    return ProfileExtractionResult(
        profile_id=profile.profile_id,
        accepted=tuple(accepted),
        quarantined=tuple(quarantined),
        rejected=tuple(rejected),
        errors=tuple(errors),
        metadata={
            "table_index": table_index,
            "row_count": table.row_count,
            "accepted_count": len(accepted),
            "quarantined_count": len(quarantined),
            "rejected_count": len(rejected),
        },
    )


def to_scraped_contract(
    result: ProfileExtractionResult,
    profile: MappingProfile,
    document: SourceDocument,
) -> dict[str, Any]:
    """Transform extraction result into case1.scraped_price_list.v1 contract."""
    now = datetime.now(UTC).isoformat()

    rows = []
    for row in result.accepted:
        rows.append(
            {
                "row_id": f"{profile.source_id}_{profile.profile_id}_row_{row.row_number:04d}",
                "source_url": document.final_url,
                "parsed_at": now,
                "service_name_raw": row.service_name,
                "service_category_raw": row.category or profile.clinic.city,
                "price_raw": row.price_raw,
                "price": float(row.price),
                "currency": "KZT",
                "updated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
                "row_code": row.code,
                "unit": row.unit,
                "section": row.section,
                "tariff_audience": profile.document.tariff_audience,
                "is_available": True,
                "raw": {
                    "row_number": row.row_number,
                    "code": row.code,
                    "unit": row.unit,
                    "section": row.section,
                    "cells": list(row.cells),
                    "profile_id": profile.profile_id,
                    "profile_version": profile.profile_version,
                },
            }
        )

    return {
        "contract_version": "case1.scraped_price_list.v1",
        "source": {
            "id": profile.source_id,
            "name": profile.clinic.name,
            "type": "public_price_list",
            "source_url": document.final_url,
            "parsed_at": now,
            "robots": {
                "checked_at": profile.reviewed_at or now,
                "allowed": True,
                "crawl_delay_seconds": 15,
                "notes": f"Reviewed profile {profile.profile_id} v{profile.profile_version}",
            },
            "adapter": {
                "name": "city_clinic_document",
                "version": ADAPTER_VERSION,
                "mode": profile.publication_mode,
            },
        },
        "clinic": {
            "external_id": profile.clinic.external_id,
            "name": profile.clinic.name,
            "legal_name": profile.clinic.legal_name,
            "city": profile.clinic.city,
            "address": profile.clinic.address,
            "phone": profile.clinic.phone,
            "website": profile.clinic.website,
            "working_hours": profile.clinic.working_hours,
        },
        "branches": [],
        "rows": rows,
    }


def to_import_payload(contract: dict[str, Any]) -> Any:
    """Transform scraped contract into ImportPricesRequest-compatible payload."""
    from app.schemas.import_prices import ImportPricesRequest

    source = contract["source"]
    clinic = contract["clinic"]
    robots = source.get("robots", {})

    services = []
    for row in contract["rows"]:
        services.append(
            {
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
        )

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
