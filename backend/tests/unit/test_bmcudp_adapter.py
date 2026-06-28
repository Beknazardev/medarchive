"""Tests for BMCUDP adapter - Phase F3 TDD."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.adapters.bmcudp import (
    ADAPTER_VERSION,
    extract_bmcudp,
    transform_to_scraped_contract,
    transform_to_import_payload,
)
from app.ingestion.contracts import (
    ExtractionResult,
    PriceQualifier,
    RawServiceCandidate,
    SourceDocument,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "bmcudp"
SOURCE_URL = "https://bmcudp.kz/ru/services/tsena-dlya-grazhdan-respubliki-kazakhstan/kt-i-mrt/12811"


def _make_document(html_path: Path) -> SourceDocument:
    content = html_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return SourceDocument(
        source_id="bmcudp",
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

class TestBmcudpExtraction:
    def test_extracts_all_rows_from_valid_fixture(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        assert isinstance(result, ExtractionResult)
        assert result.source_id == "bmcudp"
        assert len(result.candidates) >= 14

    def test_extracts_service_name_raw(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        names = [c.service_name_raw for c in result.candidates]
        assert "КТ головного мозга без контраста" in names
        assert "Низкодозовая компьютерная томография легких" in names

    def test_extracts_row_codes(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        codes = {c.service_name_raw: c.service_external_id for c in result.candidates}
        assert codes["КТ головного мозга без контраста"] == "867"
        assert codes["Низкодозовая компьютерная томография легких"] == "882"

    def test_extracts_exact_prices(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        prices = {c.service_name_raw: c.price for c in result.candidates}
        assert prices["КТ головного мозга без контраста"] == Decimal("26250")
        assert prices["Низкодозовая компьютерная томография легких"] == Decimal("21000")
        assert all(c.price_qualifier == PriceQualifier.EXACT for c in result.candidates)

    def test_extracts_units(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        for candidate in result.candidates:
            assert candidate.raw_payload["unit"] == "1 исследование"

    def test_extracts_section_headings(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        sections = [c.raw_payload.get("section") for c in result.candidates]
        assert "Брюшной отдел" in sections
        assert "МСКТ - Головной мозг" in sections
        assert "МСКТ - Грудной сегмент" in sections

    def test_selects_rk_tariff_namespace(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        for candidate in result.candidates:
            assert candidate.raw_payload.get("tariff_audience") == "rk_citizens"

    def test_preserves_price_raw(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        for candidate in result.candidates:
            assert candidate.price_raw is not None
            assert "тенге" in candidate.price_raw.lower() or candidate.price_raw

    def test_sets_source_url(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        for candidate in result.candidates:
            assert candidate.source_url == SOURCE_URL

    def test_sets_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        for candidate in result.candidates:
            assert candidate.source_id == "bmcudp"
            assert candidate.clinic_name == "БМЦ УДП РК"
            assert candidate.clinic_city == "Астана"

    def test_preserves_raw_payload(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        for candidate in result.candidates:
            assert candidate.raw_payload is not None
            assert "row_number" in candidate.raw_payload
            assert "cells" in candidate.raw_payload
            assert "tariff_audience" in candidate.raw_payload

    def test_rejects_header_section_rows(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result = extract_bmcudp(doc)
        for candidate in result.candidates:
            assert candidate.price is not None
            assert candidate.price > 0

    def test_detects_schema_drift_on_wrong_headings(self):
        html = """<html><body>
        <table>
        <thead><tr><th>Wrong</th><th>Headers</th><th>More</th><th>Extra</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>Service A</td><td>unit</td><td>100</td></tr>
        <tr><td>2</td><td>Service B</td><td>unit</td><td>200</td></tr>
        <tr><td>3</td><td>Service C</td><td>unit</td><td>300</td></tr>
        </tbody>
        </table>
        </body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="bmcudp",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_bmcudp(doc)
        assert len(result.candidates) == 0
        assert len(result.errors) >= 1
        assert any("SCHEMA_DRIFT" in e.code for e in result.errors)

    def test_empty_table_returns_error(self):
        html = """<html><body><table></table></body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="bmcudp",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_bmcudp(doc)
        assert len(result.candidates) == 0


# ─── Scraped contract transform tests ───

class TestScrapedContractTransform:
    def test_produces_valid_scraped_contract(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        extraction = extract_bmcudp(doc)
        contract = transform_to_scraped_contract(extraction)
        assert contract["contract_version"] == "case1.scraped_price_list.v1"
        assert contract["source"]["id"] == "bmcudp"
        assert len(contract["rows"]) >= 14

    def test_contract_source_metadata(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        extraction = extract_bmcudp(doc)
        contract = transform_to_scraped_contract(extraction)
        source = contract["source"]
        assert source["type"] == "public_price_list"
        assert source["adapter"]["name"] == "bmcudp"

    def test_contract_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        extraction = extract_bmcudp(doc)
        contract = transform_to_scraped_contract(extraction)
        clinic = contract["clinic"]
        assert clinic["external_id"] == "bmcudp"
        assert clinic["name"] == "БМЦ УДП РК"
        assert clinic["city"] == "Астана"

    def test_contract_rows_preserve_section(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        extraction = extract_bmcudp(doc)
        contract = transform_to_scraped_contract(extraction)
        for row in contract["rows"]:
            assert "section" in row
            assert row["section"] is not None

    def test_contract_rows_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        extraction = extract_bmcudp(doc)
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
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        extraction = extract_bmcudp(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        assert payload.source == "bmcudp"
        assert payload.source_type == "public_price_list"
        assert len(payload.services) >= 14

    def test_import_payload_services_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        extraction = extract_bmcudp(doc)
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
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        extraction = extract_bmcudp(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        for service in payload.services:
            assert "raw_item" in service
            assert service["raw_item"] is not None


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_same_input_produces_same_output(self):
        doc = _make_document(FIXTURE_DIR / "tariff_rk_ct_mrt.html")
        result1 = extract_bmcudp(doc)
        result2 = extract_bmcudp(doc)
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
