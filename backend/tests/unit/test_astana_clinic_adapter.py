"""Tests for Astana Clinic adapter - Phase G1 TDD."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.adapters.astana_clinic import (
    ADAPTER_VERSION,
    extract_astana_clinic,
    transform_to_scraped_contract,
    transform_to_import_payload,
)
from app.ingestion.contracts import (
    ExtractionResult,
    PriceQualifier,
    RawServiceCandidate,
    SourceDocument,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "astana_clinic"
SOURCE_URL = "https://www.astanaclinic.kz/index.php/ru/p-tsient-m/prejskurant-tsen-po-platnym-uslugam/1335-otdelenie-interventsionnoj-kardiologii-i-aritmologii"


def _make_document(html_path: Path) -> SourceDocument:
    content = html_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return SourceDocument(
        source_id="astana_clinic",
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

class TestAstanaClinicExtraction:
    def test_extracts_rk_tariff_only(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        assert isinstance(result, ExtractionResult)
        assert result.source_id == "astana_clinic"
        assert len(result.candidates) == 10

    def test_extracts_service_name_raw(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        names = [c.service_name_raw for c in result.candidates]
        assert "Консультация кардиолога первичная" in names
        assert "ЭхоКГ (эхокардиография)" in names

    def test_extracts_exact_rk_prices(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        prices = {c.service_name_raw: c.price for c in result.candidates}
        assert prices["Консультация кардиолога первичная"] == Decimal("8000")
        assert prices["ЭхоКГ (эхокардиография)"] == Decimal("8000")
        assert all(c.price_qualifier == PriceQualifier.EXACT for c in result.candidates)

    def test_extracts_units(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        for candidate in result.candidates:
            assert candidate.raw_payload["unit"] is not None

    def test_extracts_section_headings(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        sections = [c.raw_payload.get("section") for c in result.candidates]
        assert "Консультативные приемы" in sections
        assert "Диагностические исследования" in sections
        assert "Лабораторные исследования" in sections

    def test_preserves_price_raw(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        for candidate in result.candidates:
            assert candidate.price_raw is not None

    def test_sets_source_url(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        for candidate in result.candidates:
            assert candidate.source_url == SOURCE_URL

    def test_sets_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        for candidate in result.candidates:
            assert candidate.source_id == "astana_clinic"
            assert candidate.clinic_name == "Astana Clinic"
            assert candidate.clinic_city == "Астана"

    def test_preserves_raw_payload(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        for candidate in result.candidates:
            assert candidate.raw_payload is not None
            assert "row_number" in candidate.raw_payload
            assert "cells" in candidate.raw_payload
            assert "tariff_audience" in candidate.raw_payload

    def test_rejects_header_section_rows(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result = extract_astana_clinic(doc)
        for candidate in result.candidates:
            assert candidate.price is not None
            assert candidate.price > 0

    def test_detects_schema_drift_on_wrong_headings(self):
        html = """<html><body>
        <table>
        <thead><tr><th>Wrong</th><th>Headers</th><th>More</th><th>Extra</th><th>Extra2</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>Service A</td><td>unit</td><td>100</td><td>200</td></tr>
        <tr><td>2</td><td>Service B</td><td>unit</td><td>200</td><td>400</td></tr>
        <tr><td>3</td><td>Service C</td><td>unit</td><td>300</td><td>600</td></tr>
        </tbody>
        </table>
        </body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="astana_clinic",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_astana_clinic(doc)
        assert len(result.candidates) == 0
        assert len(result.errors) >= 1
        assert any("SCHEMA_DRIFT" in e.code for e in result.errors)

    def test_empty_table_returns_error(self):
        html = """<html><body><table></table></body></html>""".encode("utf-8")
        doc = SourceDocument(
            source_id="astana_clinic",
            requested_url=SOURCE_URL,
            final_url=SOURCE_URL,
            content_type="text/html",
            status_code=200,
            content_bytes=html,
            byte_size=len(html),
            content_sha256=hashlib.sha256(html).hexdigest(),
            captured_at=datetime(2026, 6, 27, tzinfo=UTC),
        )
        result = extract_astana_clinic(doc)
        assert len(result.candidates) == 0


# ─── Scraped contract transform tests ───

class TestScrapedContractTransform:
    def test_produces_valid_scraped_contract(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        extraction = extract_astana_clinic(doc)
        contract = transform_to_scraped_contract(extraction)
        assert contract["contract_version"] == "case1.scraped_price_list.v1"
        assert contract["source"]["id"] == "astana_clinic"
        assert len(contract["rows"]) == 10

    def test_contract_source_metadata(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        extraction = extract_astana_clinic(doc)
        contract = transform_to_scraped_contract(extraction)
        source = contract["source"]
        assert source["type"] == "public_price_list"
        assert source["adapter"]["name"] == "astana_clinic"

    def test_contract_clinic_metadata(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        extraction = extract_astana_clinic(doc)
        contract = transform_to_scraped_contract(extraction)
        clinic = contract["clinic"]
        assert clinic["external_id"] == "astana_clinic"
        assert clinic["name"] == "Astana Clinic"
        assert clinic["city"] == "Астана"

    def test_contract_rows_preserve_section(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        extraction = extract_astana_clinic(doc)
        contract = transform_to_scraped_contract(extraction)
        for row in contract["rows"]:
            assert "section" in row
            assert row["section"] is not None

    def test_contract_rows_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        extraction = extract_astana_clinic(doc)
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
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        extraction = extract_astana_clinic(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        assert payload.source == "astana_clinic"
        assert payload.source_type == "public_price_list"
        assert len(payload.services) == 10

    def test_import_payload_services_have_required_fields(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        extraction = extract_astana_clinic(doc)
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
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        extraction = extract_astana_clinic(doc)
        contract = transform_to_scraped_contract(extraction)
        payload = transform_to_import_payload(contract)
        for service in payload.services:
            assert "raw_item" in service
            assert service["raw_item"] is not None


# ─── Deterministic output tests ───

class TestDeterministicOutput:
    def test_same_input_produces_same_output(self):
        doc = _make_document(FIXTURE_DIR / "department_prices.html")
        result1 = extract_astana_clinic(doc)
        result2 = extract_astana_clinic(doc)
        assert len(result1.candidates) == len(result2.candidates)
        for c1, c2 in zip(result1.candidates, result2.candidates):
            assert c1.service_name_raw == c2.service_name_raw
            assert c1.price == c2.price


# ─── Adapter version ───

class TestAdapterVersion:
    def test_version_is_semver(self):
        parts = ADAPTER_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
