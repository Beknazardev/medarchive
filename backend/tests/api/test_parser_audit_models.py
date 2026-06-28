from sqlalchemy import select

from app.models import DataSource, ParserErrorRecord, UnmatchedServiceRecord
from app.services.parser_audit_service import ParserAuditService


def test_parser_error_persists_stage_and_retryability(db_session):
    data_source = DataSource(name="audit-source", type="public_price_list", is_active=True)
    db_session.add(data_source)
    db_session.flush()
    audit = ParserAuditService(db_session)
    parser_run = audit.create_parser_run(data_source=data_source)

    error = audit.save_parser_error(
        parser_run=parser_run,
        code="HTTP_TIMEOUT",
        message="Timed out while fetching the public price page",
        stage="fetch",
        retryable=True,
        source_url="https://clinic.example/prices",
    )

    persisted = db_session.scalar(select(ParserErrorRecord).where(ParserErrorRecord.id == error.id))
    assert persisted.stage == "fetch"
    assert persisted.retryable is True


def test_repeated_unmatched_import_updates_occurrence_audit(client, db_session):
    request = {
        "source": "unmatched-audit-source",
        "source_batch_id": "batch-1",
        "clinic": {
            "external_id": "clinic-1",
            "name": "Audit Clinic",
            "city": "Astana",
        },
        "services": [
            {
                "external_id": "service-1",
                "name": "Unique source-only procedure",
                "category": "Source-only category",
                "price": 5000,
                "currency": "KZT",
                "updated_at": "2026-06-27",
            }
        ],
    }

    first = client.post(
        "/api/v1/import/prices",
        json=request,
        headers={"X-API-Key": "example-secret"},
    )
    request["source_batch_id"] = "batch-2"
    second = client.post(
        "/api/v1/import/prices",
        json=request,
        headers={"X-API-Key": "example-secret"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    record = db_session.scalar(select(UnmatchedServiceRecord))
    assert record.occurrence_count == 2
    assert record.first_seen_at is not None
    assert record.last_seen_at is not None
    assert record.last_seen_at >= record.first_seen_at
    assert record.reviewed_at is None
    assert record.reviewed_by is None
    assert record.review_action is None
    assert record.review_note is None
