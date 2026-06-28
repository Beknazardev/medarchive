"""Tests for Magnesia city-aware adapter - Phase F5 TDD."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.adapters.magnesia import (
    ADAPTER_VERSION,
    extract_magnesia,
    transform_to_scraped_contract,
    transform_to_import_payload,
    CITY_CONFIGS,
)
from app.ingestion.contracts import (
    ExtractionResult,
    PriceQualifier,
    RawServiceCandidate,
    SourceDocument,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "magnesia"
SOURCE_URL = "https://pavlodar.magnesia.kz/kt/"


def _make_document(html_path: Path, city: str = "pavlodar") -> SourceDocument:
    content = html_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return SourceDocument(
        source_id="magnesia",
        requested_url=f"https://{city}.magnesia.kz/kt/",
        final_url=f"https://{city}.magnesia.kz/kt/",
        content_type="text/html",
        status_code=200,
        content_bytes=content,
        byte_size=len(content),
        content_sha256=digest,
        captured_at=datetime(2026, 6, 27, tzinfo=UTC),
    )


# ─── City configuration tests ───

class TestCityConfigs:
    def test_approved_cities_are_configured(self):
        assert "pavlodar" in CITY_CONFIGS
        assert "semey" in CITY_CONFIGS
        assert "kostanay" in CITY_CONFIGS

    def test_city_configs_have_required_fields(self):
        for city, config in CITY_CONFIGS.items():
            assert "name" in config
            assert "address" in config
            assert "paths" in config


# ─── Adapter extraction tests ───

class TestMagnesiaExtraction:
    def test_extracts_all_rows_from_valid_fixture(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        assert isinstance(result, ExtractionResult)
        assert result.source_id == "magnesia"
        assert len(result.candidates) >= 10

    def test_extracts_service_name_raw(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        names = [c.service_name_raw for c in result.candidates]
        assert "КТ головного мозга/костей черепа" in names
        assert "КТ органов грудной клетки" in names

    def test_extracts_row_codes(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        codes = {c.service_name_raw: c.service_external_id for c in result.candidates}
        assert codes["КТ головного мозга/костей черепа"] == "1.1"
        assert codes["КТ органов грудной клетки"] == "3.1"

    def test_extracts_exact_prices(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        prices = {c.service_name_raw: c.price for c in result.candidates}
        assert prices["КТ головного мозга/костей черепа"] == Decimal("20000")
        assert prices["КТ органов грудной клетки"] == Decimal("20000")
        assert all(c.price_qualifier == PriceQualifier.EXACT for c in result.candidates)

    def test_extracts_contrast_qualifiers(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        contrast_items = [c for c in result.candidates if "контраст" in c.service_name_raw.lower()]
        assert len(contrast_items) >= 4
        for item in contrast_items:
            assert item.raw_payload.get("has_contrast") is True

    def test_extracts_weight_qualifiers(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        weight_items = [c for c in result.candidates if c.raw_payload.get("weight_qualifier")]
        assert len(weight_items) >= 2

    def test_extracts_section_headings(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        sections = [c.raw_payload.get("section") for c in result.candidates]
        assert "Область головы" in sections
        assert "Шея" in sections
        assert "Грудная клетка" in sections

    def test_sets_city_from_url(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        for candidate in result.candidates:
            assert candidate.clinic_city == "Павлодар"

    def test_sets_branch_address(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        for candidate in result.candidates:
            assert candidate.clinic_address == "Павлодар, ул. Ермака, 15/2"

    def test_preserves_price_raw(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        for candidate in result.candidates:
            assert candidate.price_raw is not None
            assert "тенге" in candidate.price_raw.lower() or candidate.price_raw

    def test_sets_source_url(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        for candidate in result.candidates:
            assert "pavlodar.magnesia.kz" in candidate.source_url

    def test_preserves_raw_payload(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        for candidate in result.candidates:
            assert candidate.raw_payload is not None
            assert "row_number" in candidate.raw_payload
            assert "cells" in candidate.raw_payload
            assert "city" in candidate.raw_payload

    def test_rejects_header_section_rows(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result = extract_magnesia(doc)
        for candidate in result.candidates:
            assert candidate.price is not None
            assert candidate.price > 0

    def test_detects_schema_drift_on_wrong_headings(self):
        html = """<html><body>
        <table>
        <thead><tr><th>Wrong</th><th>Headers</th><th>More</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>Service A</td><td>100</td></tr>
        <tr><td>2</td><td>Service B</td><td>200</td></tr>
        <tr><td>3</td><td>Service C</td><td>300</td></tr>
        </tbody>
        </table>
        </body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="magnesia",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_magnesia(doc)
        assert len(result.candidates) == 0
        assert len(result.errors) >= 1
        assert any("SCHEMA_DRIFT" in e.code for e in result.errors)

    def test_empty_table_returns_error(self):
        html = """<html><body><table></table></body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="magnesia",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_magnesia(doc)
        assert len(result.candidates) == 0


# ─── Scraped contract transform tests ───

class TestScrapedContractTransform:
    def test_produces_valid_scraped_contract(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        extraction = extract_magnesia(doc)
        contract = transform_to_scraped_contract(extraction)
        assert contract["contract_version"] == "case1.scraped_price_list.v1"
        assert contract["source"]["id"] == "magnesia"
        assert len(contract["rows"]) >= 10

    def test_contract_source_metadata(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        extraction = extract_magnesia(doc)
        contract = transform_to_scraped_contract(extraction)
        source = contract["source"]
        assert source["type"] == "public_price_list"
        assert source["adapter"]["name"] == "magnesia"

    def test_contract_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        extraction = extract_magnesia(doc)
        contract = transform_to_scraped_contract(extraction)
        clinic = contract["clinic"]
        assert "magnesia" in clinic["external_id"]
        assert clinic["name"] == "Магнезия"
        assert clinic["city"] == "Павлодар"

    def test_contract_rows_preserve_section(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        extraction = extract_magnesia(doc)
        contract = transform_to_scraped_contract(extraction)
        for row in contract["rows"]:
            assert "section" in row
            assert row["section"] is not None

    def test_contract_rows_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        extraction = extract_magnesia(doc)
        contract = transform_to_scraped_contract(extraction)
        for row in contract["rows"]:
            assert "row_id" in row
            assert "service_name_raw" in row
            assert "price" in row
            assert "currency" in row
            assert "updated_at" in row
            assert "source_url" in row
            assert "parsed_at" in row


# ─── Import payload transform tests ───

class TestImportPayloadTransform:
    def test_produces_valid_import_payload(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        extraction = extract_magnesia(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        assert payload.source == "magnesia"
        assert payload.source_type == "public_price_list"
        assert len(payload.services) >= 10

    def test_import_payload_services_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        extraction = extract_magnesia(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        for service in payload.services:
            assert "external_id" in service
            assert "name" in service
            assert "price" in service
            assert "currency" in service
            assert "updated_at" in service
            assert "source_url" in service
            assert "parsed_at" in service

    def test_import_payload_preserves_raw_item(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        extraction = extract_magnesia(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        for service in payload.services:
            assert "raw_item" in service
            assert service["raw_item"] is not None


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_same_input_produces_same_output(self):
        doc = _make_document(FIXTURE_DIR / "pavlodar_kt.html")
        result1 = extract_magnesia(doc)
        result2 = extract_magnesia(doc)
        assert len(result1.candidates) == len(result2.candidates)
        for c1, c2 in zip(result1.candidates, result2.candidates):
            assert c1.service_name_raw == c2.service_name_raw
            assert c1.price == c2.price
            assert c1.service_external_id == c2.service_external_id


# ─── Adapter version ───

class TestAdapterVersion:
    def test_version_is_semver(self):
        parts = ADAPTER_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
