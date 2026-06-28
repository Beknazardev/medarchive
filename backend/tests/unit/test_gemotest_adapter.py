"""Tests for Gemotest Kazakhstan adapter - Phase F2 TDD."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.adapters.gemotest_kz import (
    ADAPTER_VERSION,
    extract_gemotest,
    transform_to_scraped_contract,
    transform_to_import_payload,
)
from app.ingestion.contracts import (
    ExtractionResult,
    PriceQualifier,
    RawServiceCandidate,
    SourceDocument,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "gemotest_kz"
SOURCE_URL = "https://gemotest.kz/almaty/catalog/"


def _make_document(html_path: Path) -> SourceDocument:
    content = html_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return SourceDocument(
        source_id="gemotest_kz",
        requested_url=SOURCE_URL,
        final_url=SOURCE_URL,
        content_type="text/html",
        status_code=200,
        content_bytes=content,
        byte_size=len(content),
        content_sha256=digest,
        captured_at=datetime(2026, 6, 27, tzinfo=UTC),
    )


# ─── Adapter extraction tests ───

class TestGemotestExtraction:
    def test_extracts_all_items_from_valid_fixture(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        assert isinstance(result, ExtractionResult)
        assert result.source_id == "gemotest_kz"
        assert len(result.candidates) == 5

    def test_extracts_service_name_raw(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        names = [c.service_name_raw for c in result.candidates]
        assert "Общий анализ мочи" in names
        assert "ТТГ" in names

    def test_extracts_exact_base_prices(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        prices = {c.service_name_raw: c.price for c in result.candidates}
        assert prices["Общий анализ мочи"] == Decimal("1450")
        assert prices["ТТГ"] == Decimal("1820")
        assert all(c.price_qualifier == PriceQualifier.EXACT for c in result.candidates)

    def test_extracts_biomaterial_fee(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        oak = next(c for c in result.candidates if c.service_name_raw == "Общий анализ мочи")
        assert oak.additional_fee == Decimal("1090")
        assert oak.raw_payload["biomaterial_fee_raw"] == "+1 090 ₸"

    def test_extracts_service_code(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        oak = next(c for c in result.candidates if c.service_name_raw == "Общий анализ мочи")
        assert oak.service_external_id == "9.1."

    def test_extracts_specimen_qualifier(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        oak = next(c for c in result.candidates if c.service_name_raw == "Общий анализ мочи")
        assert oak.raw_payload["specimen"] == "Моча"

    def test_extracts_duration(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        for candidate in result.candidates:
            assert candidate.duration_days == 1
            assert candidate.duration_raw == "1 день"

    def test_does_not_overwrite_with_discount(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        vit_d = next(c for c in result.candidates if "Витамин D" in c.service_name_raw)
        assert vit_d.price == Decimal("3790")
        assert vit_d.raw_payload.get("discount_raw") is not None

    def test_preserves_price_raw(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        for candidate in result.candidates:
            assert candidate.price_raw is not None
            assert "₸" in candidate.price_raw

    def test_sets_source_url_with_city(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        for candidate in result.candidates:
            assert "almaty" in candidate.source_url.lower() or "Алматы" in candidate.clinic_city

    def test_sets_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        for candidate in result.candidates:
            assert candidate.source_id == "gemotest_kz"
            assert candidate.clinic_name == "Гемотест"
            assert candidate.clinic_city == "Алматы"

    def test_preserves_raw_payload(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result = extract_gemotest(doc)
        for candidate in result.candidates:
            assert candidate.raw_payload is not None
            assert "code" in candidate.raw_payload
            assert "specimen" in candidate.raw_payload

    def test_detects_schema_drift_on_missing_items(self):
        html = """<html><body>
        <div class="catalog-items">
        <p>No items here</p>
        </div>
        </body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="gemotest_kz",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_gemotest(doc)
        assert len(result.candidates) == 0
        assert len(result.errors) >= 1
        assert any("NO_CATALOG_ITEMS" in e.code for e in result.errors)

    def test_quarantines_row_without_price(self):
        html = """<html><body>
        <div class="catalog-items">
        <div class="catalog-item" data-code="1.0.">
        <div class="item-header">
        <span class="item-code">Код 1.0.</span>
        <span class="item-name">Test without price</span>
        </div>
        <div class="item-prices"></div>
        </div>
        <div class="catalog-item" data-code="2.0.">
        <div class="item-header">
        <span class="item-code">Код 2.0.</span>
        <span class="item-name">Valid test 1</span>
        </div>
        <div class="item-prices">
        <div class="price-standard">
        <span class="price-value">1 000 ₸</span>
        </div>
        </div>
        </div>
        <div class="catalog-item" data-code="3.0.">
        <div class="item-header">
        <span class="item-code">Код 3.0.</span>
        <span class="item-name">Valid test 2</span>
        </div>
        <div class="item-prices">
        <div class="price-standard">
        <span class="price-value">2 000 ₸</span>
        </div>
        </div>
        </div>
        </div>
        </body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="gemotest_kz",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_gemotest(doc)
        assert len(result.candidates) == 2
        assert result.candidates[0].service_name_raw == "Valid test 1"
        assert result.candidates[1].service_name_raw == "Valid test 2"


# ─── Scraped contract transform tests ───

class TestScrapedContractTransform:
    def test_produces_valid_scraped_contract(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        extraction = extract_gemotest(doc)
        contract = transform_to_scraped_contract(extraction)
        assert contract["contract_version"] == "case1.scraped_price_list.v1"
        assert contract["source"]["id"] == "gemotest_kz"
        assert len(contract["rows"]) == 5

    def test_contract_source_metadata(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        extraction = extract_gemotest(doc)
        contract = transform_to_scraped_contract(extraction)
        source = contract["source"]
        assert source["type"] == "public_price_list"
        assert "almaty" in source["source_url"].lower()
        assert source["adapter"]["name"] == "gemotest_kz"

    def test_contract_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        extraction = extract_gemotest(doc)
        contract = transform_to_scraped_contract(extraction)
        clinic = contract["clinic"]
        assert clinic["external_id"] == "gemotest_kz"
        assert clinic["name"] == "Гемотест"
        assert clinic["city"] == "Алматы"

    def test_contract_rows_preserve_biomaterial_fee(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        extraction = extract_gemotest(doc)
        contract = transform_to_scraped_contract(extraction)
        for row in contract["rows"]:
            assert "biomaterial_fee" in row
            assert row["biomaterial_fee"] >= 0

    def test_contract_rows_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        extraction = extract_gemotest(doc)
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
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        extraction = extract_gemotest(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        assert payload.source == "gemotest_kz"
        assert payload.source_type == "public_price_list"
        assert len(payload.services) == 5

    def test_import_payload_services_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        extraction = extract_gemotest(doc)
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
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        extraction = extract_gemotest(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        for service in payload.services:
            assert "raw_item" in service
            assert service["raw_item"] is not None


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_same_input_produces_same_output(self):
        doc = _make_document(FIXTURE_DIR / "catalog_almaty.html")
        result1 = extract_gemotest(doc)
        result2 = extract_gemotest(doc)
        assert len(result1.candidates) == len(result2.candidates)
        for c1, c2 in zip(result1.candidates, result2.candidates):
            assert c1.service_name_raw == c2.service_name_raw
            assert c1.price == c2.price
            assert c1.additional_fee == c2.additional_fee


# ─── Adapter version ───

class TestAdapterVersion:
    def test_version_is_semver(self):
        parts = ADAPTER_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
