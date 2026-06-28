from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import (
    ClinicBranch,
    ClinicServicePrice,
    DataSource,
    ImportBatch,
    ImportErrorRecord,
    ParserErrorRecord,
    PriceHistory,
    RawSourceRow,
    RawSourceSnapshot,
    Service,
)
from app.services.parser_audit_service import ParserAuditService


API_KEY = {"X-API-Key": "example-secret"}


def payload(services, branch=None):
    result = {
        "source": "clinic_partner_api",
        "clinic": {
            "external_id": "clinic_edge_001",
            "name": "Edge Clinic",
            "city": "Astana",
            "address": "Edge street 10",
            "phone": "+77001234567",
        },
        "services": services,
    }
    if branch is not None:
        result["branch"] = branch
    return result


def service(index, price=1000):
    return {
        "external_id": f"srv_edge_{index}",
        "name": f"Service {index}",
        "category": "Diagnostics",
        "price": price,
        "currency": "KZT",
        "updated_at": "2026-06-17",
    }


def test_missing_branch_creates_default_branch(client, db_session):
    response = client.post(
        "/api/v1/import/prices",
        json=payload([service(1)]),
        headers=API_KEY,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "success"

    branch = db_session.scalar(select(ClinicBranch))
    assert branch is not None
    assert branch.name == "Default branch"
    assert branch.is_default is True
    assert branch.address == "Edge street 10"


def test_price_zero_and_missing_optional_service_fields_are_accepted(client, db_session):
    response = client.post(
        "/api/v1/import/prices",
        json=payload([service(1, price=0)]),
        headers=API_KEY,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["created_count"] == 1
    assert data["error_count"] == 0
    current_price = db_session.scalar(select(ClinicServicePrice))
    assert str(current_price.price) in {"0.00", "0"}
    assert db_session.scalar(select(PriceHistory).where(PriceHistory.change_type == "created"))


def test_large_import_payload_with_100_services(client, db_session):
    response = client.post(
        "/api/v1/import/prices",
        json=payload([service(index) for index in range(100)]),
        headers=API_KEY,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["received_count"] == 100
    assert data["created_count"] == 100
    assert data["error_count"] == 0
    assert len(db_session.scalars(select(Service)).all()) == 100


def test_parser_run_and_parser_error_are_persisted_separately(db_session):
    data_source = DataSource(name="parser_source", type="public_price_list", is_active=True)
    db_session.add(data_source)
    db_session.flush()

    audit_service = ParserAuditService(db_session)
    parser_run = audit_service.create_parser_run(
        data_source=data_source,
        status="running",
        source_url="https://clinic.example/prices",
        started_at=datetime(2026, 6, 26, 8, 0, tzinfo=UTC),
        received_count=10,
    )
    audit_service.save_parser_error(
        parser_run=parser_run,
        code="HTML_TABLE_NOT_FOUND",
        message="Could not find expected price table",
        source_url="https://clinic.example/prices",
        raw_item={"selector": "#prices"},
    )
    audit_service.finish_parser_run(parser_run, status="failed")

    saved_run = db_session.get(type(parser_run), parser_run.id)
    parser_error = db_session.scalar(select(ParserErrorRecord))

    assert saved_run.status == "failed"
    assert saved_run.finished_at is not None
    assert saved_run.error_count == 1
    assert parser_error.code == "HTML_TABLE_NOT_FOUND"
    assert parser_error.parser_run_id == parser_run.id
    assert db_session.scalar(select(ImportErrorRecord)) is None


def test_import_links_raw_snapshot_and_rows_to_imported_records(client, db_session):
    data_source = DataSource(
        name="clinic_partner_api",
        type="public_price_list",
        public_url="https://clinic.example/prices",
        is_active=True,
    )
    db_session.add(data_source)
    db_session.flush()
    parser_run = ParserAuditService(db_session).create_parser_run(
        data_source=data_source,
        status="parsed",
        source_url="https://clinic.example/prices",
        parsed_at=datetime(2026, 6, 26, 8, 30, tzinfo=UTC),
        received_count=1,
    )

    import_payload = payload(
        [
            {
                **service(1),
                "source_url": "https://clinic.example/prices#row-1",
                "raw_item": {
                    "raw_name": "Service 1",
                    "raw_price": "1000 KZT",
                },
            }
        ]
    )
    import_payload["parser_run_id"] = parser_run.id
    import_payload["raw_snapshot"] = {
        "source_url": "https://clinic.example/prices",
        "content_type": "text/html",
        "checksum": "sha256:test",
        "raw_payload": {"html": "<table><tr><td>Service 1</td></tr></table>"},
        "captured_at": "2026-06-26T08:30:00Z",
    }

    response = client.post("/api/v1/import/prices", json=import_payload, headers=API_KEY)

    assert response.status_code == 200
    batch = db_session.scalar(select(ImportBatch))
    snapshot = db_session.scalar(select(RawSourceSnapshot))
    raw_row = db_session.scalar(select(RawSourceRow))
    current_price = db_session.scalar(select(ClinicServicePrice))
    imported_service = db_session.scalar(select(Service))
    refreshed_run = db_session.get(type(parser_run), parser_run.id)

    assert batch.parser_run_id == parser_run.id
    assert snapshot.parser_run_id == parser_run.id
    assert snapshot.retention_until >= snapshot.captured_at + timedelta(days=90)
    assert raw_row.parser_run_id == parser_run.id
    assert raw_row.snapshot_id == snapshot.id
    assert raw_row.import_batch_id == batch.id
    assert raw_row.service_id == imported_service.id
    assert raw_row.clinic_service_price_id == current_price.id
    assert raw_row.retention_until >= raw_row.created_at + timedelta(days=90)
    assert refreshed_run.imported_count == 1
    assert refreshed_run.raw_snapshot_count == 1
    assert refreshed_run.raw_row_count == 1
