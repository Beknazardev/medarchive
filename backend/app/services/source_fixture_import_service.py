from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataSource
from app.schemas.import_prices import ImportPricesRequest
from app.services.import_service import ImportService
from app.services.parser_audit_service import ParserAuditService
from app.services.service_catalog_seed_service import ServiceCatalogSeedService


DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "examples" / "sources"
CONTRACT_VERSION = "case1.scraped_price_list.v1"


@dataclass(frozen=True)
class SourceFixtureImportResult:
    fixture: str
    source: str
    received_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    error_count: int
    status: str


class SourceFixtureImportService:
    def __init__(self, db: Session, fixtures_dir: Path | str = DEFAULT_FIXTURES_DIR) -> None:
        self.db = db
        self.fixtures_dir = Path(fixtures_dir)

    def import_all(self, seed_catalog: bool = True) -> list[SourceFixtureImportResult]:
        if seed_catalog:
            ServiceCatalogSeedService(self.db).seed_default_catalog(commit=False)

        results: list[SourceFixtureImportResult] = []
        for fixture_path in self.fixture_paths():
            results.append(self.import_fixture(fixture_path))
        self.db.commit()
        return results

    def import_fixture(self, fixture_path: Path) -> SourceFixtureImportResult:
        fixture = self.load_fixture(fixture_path)
        source = fixture["source"]
        rows = fixture["rows"]

        data_source = self._upsert_data_source(source)
        parser_run = ParserAuditService(self.db).create_parser_run(
            data_source=data_source,
            status="parsed",
            source_url=source["source_url"],
            parsed_at=_parse_datetime(source["parsed_at"]),
            received_count=len(rows),
            notes=(
                "Deterministic seed-source importer. "
                "No live scraping performed during this run."
            ),
        )
        payload = self.to_import_request(fixture, fixture_path, parser_run.id)
        result = ImportService(self.db).import_prices(payload)

        refreshed_run = self.db.get(type(parser_run), parser_run.id)
        if refreshed_run:
            ParserAuditService(self.db).finish_parser_run(
                refreshed_run,
                status=result.status,
                imported_count=result.created_count + result.updated_count + result.unchanged_count,
                error_count=result.error_count,
            )

        return SourceFixtureImportResult(
            fixture=str(fixture_path),
            source=result.source,
            received_count=result.received_count,
            created_count=result.created_count,
            updated_count=result.updated_count,
            unchanged_count=result.unchanged_count,
            error_count=result.error_count,
            status=result.status,
        )

    def fixture_paths(self) -> list[Path]:
        return sorted(self.fixtures_dir.glob("*_adapter_output.json"))

    def load_fixture(self, fixture_path: Path) -> dict[str, Any]:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        if fixture.get("contract_version") != CONTRACT_VERSION:
            raise ValueError(f"{fixture_path} has unsupported contract_version")
        if not fixture.get("rows"):
            raise ValueError(f"{fixture_path} contains no rows")
        return fixture

    def to_import_request(
        self,
        fixture: dict[str, Any],
        fixture_path: Path,
        parser_run_id: int | None = None,
    ) -> ImportPricesRequest:
        source = fixture["source"]
        clinic = fixture["clinic"]
        branch = self._branch_for_fixture(fixture)
        parsed_at = source["parsed_at"]
        robots = source.get("robots", {})

        return ImportPricesRequest.model_validate(
            {
                "source": source["id"],
                "source_type": source.get("type") or "public_price_list",
                "source_url": source["source_url"],
                "robots_policy_notes": robots.get("notes"),
                "crawl_delay_seconds": robots.get("crawl_delay_seconds"),
                "source_batch_id": f"{source['id']}:{parsed_at}",
                "parser_run_id": parser_run_id,
                "raw_snapshot": {
                    "source_url": source["source_url"],
                    "content_type": "application/json",
                    "raw_payload": {
                        "fixture": str(fixture_path),
                        "contract_version": fixture["contract_version"],
                        "source": source,
                        "clinic": clinic,
                        "branch_count": len(fixture.get("branches", [])),
                        "row_count": len(fixture["rows"]),
                    },
                    "captured_at": source.get("retrieved_at") or parsed_at,
                },
                "clinic": self._clinic_payload(clinic),
                "branch": self._branch_payload(branch, clinic),
                "services": [self._service_payload(row, parsed_at) for row in fixture["rows"]],
            }
        )

    def _upsert_data_source(self, source: dict[str, Any]) -> DataSource:
        data_source = self.db.scalar(select(DataSource).where(DataSource.name == source["id"]))
        if data_source is None:
            data_source = DataSource(name=source["id"], type=source.get("type") or "external", is_active=True)
            self.db.add(data_source)
        data_source.type = source.get("type") or data_source.type
        data_source.public_url = source["source_url"]
        robots = source.get("robots", {})
        data_source.robots_policy_notes = robots.get("notes")
        data_source.crawl_delay_seconds = robots.get("crawl_delay_seconds")
        self.db.flush()
        return data_source

    def _branch_for_fixture(self, fixture: dict[str, Any]) -> dict[str, Any] | None:
        branches = fixture.get("branches") or []
        return branches[0] if branches else None

    def _clinic_payload(self, clinic: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": clinic["external_id"],
            "name": clinic["name"],
            "legal_name": clinic.get("legal_name"),
            "city": clinic["city"],
            "address": clinic.get("address"),
            "phone": clinic.get("phone"),
            "website": clinic.get("website"),
        }

    def _branch_payload(
        self,
        branch: dict[str, Any] | None,
        clinic: dict[str, Any],
    ) -> dict[str, Any] | None:
        if branch is None:
            return None
        return {
            "external_id": branch.get("external_id"),
            "name": branch.get("name"),
            "city": branch.get("city") or clinic["city"],
            "address": branch.get("address") or clinic.get("address"),
            "phone": branch.get("phone") or clinic.get("phone"),
        }

    def _service_payload(self, row: dict[str, Any], default_parsed_at: str) -> dict[str, Any]:
        service = {
            "external_id": row["row_id"],
            "name": row["service_name_raw"],
            "category": row.get("service_category_raw") or "Uncategorized",
            "price": row["price"],
            "currency": row["currency"],
            "updated_at": row["updated_at"],
            "source_url": row.get("source_url"),
            "parsed_at": row.get("parsed_at") or default_parsed_at,
            "is_available": row.get("is_available", True),
            "raw_item": row,
        }
        if row.get("duration_minutes") is not None:
            service["duration_minutes"] = row["duration_minutes"]
        return service


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
