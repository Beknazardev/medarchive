from sqlalchemy import select

from app.models import (
    Clinic,
    ClinicServicePrice,
    DataSource,
    ImportBatch,
    ImportErrorRecord,
    NormalizedService,
    PriceObservation,
    PriceHistory,
    RawSourceRow,
    RawSourceSnapshot,
    Service,
    UnmatchedServiceRecord,
)
from app.services.service_catalog_seed_service import ServiceCatalogSeedService


API_KEY = {"X-API-Key": "example-secret"}


def payload(price=25000, services=None):
    return {
        "source": "clinic_partner_api",
        "source_batch_id": "batch_001",
        "clinic": {
            "external_id": "clinic_001",
            "name": "Example Clinic",
            "city": "Astana",
            "address": "Example street 10",
            "phone": "+77001234567",
        },
        "branch": {
            "external_id": "branch_001",
            "name": "Main branch",
            "city": "Astana",
            "address": "Example street 10",
        },
        "services": services
        or [
            {
                "external_id": "srv_001",
                "name": "МРТ головного мозга",
                "category": "МРТ",
                "price": price,
                "currency": "KZT",
                "updated_at": "2026-06-17",
            }
        ],
    }


def test_successful_import(client, db_session):
    response = client.post("/api/v1/import/prices", json=payload(), headers=API_KEY)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "success"
    assert data["received_count"] == 1
    assert data["created_count"] == 1
    assert data["error_count"] == 0
    assert db_session.scalar(select(Clinic).where(Clinic.external_id == "clinic_001"))
    assert db_session.scalar(select(Service).where(Service.external_id == "srv_001"))
    assert db_session.scalar(select(ClinicServicePrice))
    assert db_session.scalar(select(PriceHistory).where(PriceHistory.change_type == "created"))


def test_import_saves_source_metadata_and_price_provenance(client, db_session):
    provenance_payload = payload()
    provenance_payload.update(
        {
            "source_type": "public_price_list",
            "source_url": "https://clinic.example/prices",
            "robots_policy_notes": "Public price list checked before import.",
            "crawl_delay_seconds": 5,
        }
    )
    provenance_payload["services"][0]["source_url"] = "https://clinic.example/prices/mrt"
    provenance_payload["services"][0]["parsed_at"] = "2026-06-26T08:30:00Z"

    response = client.post("/api/v1/import/prices", json=provenance_payload, headers=API_KEY)

    assert response.status_code == 200
    data_source = db_session.scalar(select(DataSource).where(DataSource.name == "clinic_partner_api"))
    assert data_source.type == "public_price_list"
    assert data_source.public_url == "https://clinic.example/prices"
    assert data_source.robots_policy_notes == "Public price list checked before import."
    assert data_source.crawl_delay_seconds == 5

    current_price = db_session.scalar(select(ClinicServicePrice))
    assert current_price.source_url == "https://clinic.example/prices/mrt"
    assert current_price.parsed_at.isoformat().startswith("2026-06-26T08:30:00")

    history = db_session.scalar(select(PriceHistory))
    assert history.source_url == "https://clinic.example/prices/mrt"
    assert history.parsed_at.isoformat().startswith("2026-06-26T08:30:00")


def test_import_without_provenance_remains_compatible(client, db_session):
    response = client.post("/api/v1/import/prices", json=payload(), headers=API_KEY)

    assert response.status_code == 200
    current_price = db_session.scalar(select(ClinicServicePrice))
    assert current_price.source_url is None
    assert current_price.parsed_at is not None


def test_import_uses_official_catalog_match_before_creating_normalized_service(client, db_session):
    ServiceCatalogSeedService(db_session).seed_default_catalog(commit=False)
    catalog_count = db_session.query(NormalizedService).count()

    catalog_payload = payload(
        services=[
            {
                "external_id": "srv_gyn",
                "name": "Прием акушер-гинеколога",
                "category": "Акушер-гинеколог",
                "price": 3500,
                "currency": "KZT",
                "updated_at": "2026-06-17",
            }
        ]
    )

    response = client.post("/api/v1/import/prices", json=catalog_payload, headers=API_KEY)

    assert response.status_code == 200
    service = db_session.scalar(select(Service).where(Service.external_id == "srv_gyn"))
    normalized_service = db_session.get(NormalizedService, service.normalized_service_id)
    assert normalized_service.name == "прием акушер-гинеколога"
    assert normalized_service.aliases == []
    assert service.normalization_status == "matched"
    assert str(service.normalization_confidence) in {"1.000", "1"}
    assert db_session.query(NormalizedService).count() == catalog_count
    assert db_session.scalar(select(UnmatchedServiceRecord)) is None


def test_import_uses_catalog_alias_match_before_queueing_unmatched(client, db_session):
    ServiceCatalogSeedService(db_session).seed_default_catalog(
        catalog=[
            {
                "category": "Diagnostics",
                "name": "electrocardiography",
                "aliases": ["ECG"],
            }
        ],
        commit=False,
    )

    response = client.post(
        "/api/v1/import/prices",
        json=payload(
            services=[
                {
                    "external_id": "srv_ecg",
                    "name": "ECG",
                    "category": "Diagnostics",
                    "price": 5000,
                    "currency": "KZT",
                    "updated_at": "2026-06-17",
                }
            ]
        ),
        headers=API_KEY,
    )

    assert response.status_code == 200
    service = db_session.scalar(select(Service).where(Service.external_id == "srv_ecg"))
    normalized_service = db_session.get(NormalizedService, service.normalized_service_id)
    assert normalized_service.name == "electrocardiography"
    assert service.normalization_status == "alias_matched"
    assert str(service.normalization_confidence) in {"0.900", "0.9"}
    assert db_session.scalar(select(UnmatchedServiceRecord)) is None


def test_import_unmatched_service_creates_queue_record(client, db_session):
    ServiceCatalogSeedService(db_session).seed_default_catalog(commit=False)
    catalog_count = db_session.query(NormalizedService).count()

    response = client.post(
        "/api/v1/import/prices",
        json=payload(
            services=[
                {
                    "external_id": "srv_unknown",
                    "name": "Very specific source-only service",
                    "category": "Source-only category",
                    "price": 7000,
                    "currency": "KZT",
                    "updated_at": "2026-06-17",
                    "source_url": "https://clinic.example/prices#unknown",
                    "raw_item": {
                        "service_name_raw": "Very specific source-only service",
                        "price_raw": "7000 KZT",
                    },
                }
            ]
        ),
        headers=API_KEY,
    )

    assert response.status_code == 200
    service = db_session.scalar(select(Service).where(Service.external_id == "srv_unknown"))
    normalized_service = db_session.get(NormalizedService, service.normalized_service_id)
    unmatched = db_session.scalar(select(UnmatchedServiceRecord))

    assert normalized_service.name == "unmatched service"
    assert service.normalization_status == "unmatched"
    assert str(service.normalization_confidence) in {"0.000", "0"}
    assert db_session.query(NormalizedService).count() == catalog_count + 1
    assert unmatched is not None
    assert unmatched.status == "open"
    assert unmatched.raw_name == "Very specific source-only service"
    assert unmatched.raw_category == "Source-only category"
    assert unmatched.service_id == service.id
    assert unmatched.source_url == "https://clinic.example/prices#unknown"


def test_invalid_api_key(client):
    response = client.post("/api/v1/import/prices", json=payload(), headers={"X-API-Key": "bad"})

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Invalid or missing API key",
            "details": [],
        }
    }


def test_validation_error_for_root_payload(client):
    invalid_payload = payload()
    invalid_payload["clinic"].pop("name")

    response = client.post("/api/v1/import/prices", json=invalid_payload, headers=API_KEY)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]


def test_duplicate_import_does_not_duplicate_current_records(client, db_session):
    first = client.post("/api/v1/import/prices", json=payload(), headers=API_KEY)
    second = client.post("/api/v1/import/prices", json=payload(), headers=API_KEY)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["unchanged_count"] == 1
    assert len(db_session.scalars(select(Clinic)).all()) == 1
    assert len(db_session.scalars(select(Service)).all()) == 1
    assert len(db_session.scalars(select(ClinicServicePrice)).all()) == 1
    assert len(db_session.scalars(select(PriceHistory)).all()) == 1
    observations = db_session.scalars(select(PriceObservation).order_by(PriceObservation.id)).all()
    assert len(observations) == 2
    assert [observation.change_detected for observation in observations] == [True, False]


def test_import_persists_raw_audit_metadata_and_row_status(client, db_session):
    audit_payload = payload()
    audit_payload["raw_snapshot"] = {
        "source_url": "https://clinic.example/requested",
        "requested_url": "https://clinic.example/requested",
        "final_url": "https://clinic.example/prices",
        "http_status": 200,
        "response_headers": {"content-type": "text/html; charset=utf-8"},
        "content_type": "text/html",
        "byte_size": 128,
        "content_sha256": "a" * 64,
        "storage_uri": "file:///audit/snapshot.html",
        "source_document_date": "2026-06-20",
        "raw_payload": {"html": "<table></table>"},
    }

    response = client.post("/api/v1/import/prices", json=audit_payload, headers=API_KEY)

    assert response.status_code == 200
    snapshot = db_session.scalar(select(RawSourceSnapshot))
    assert snapshot.requested_url == "https://clinic.example/requested"
    assert snapshot.final_url == "https://clinic.example/prices"
    assert snapshot.http_status == 200
    assert snapshot.response_headers["content-type"].startswith("text/html")
    assert snapshot.byte_size == 128
    assert snapshot.content_sha256 == "a" * 64
    assert snapshot.storage_uri == "file:///audit/snapshot.html"
    assert snapshot.source_document_date.isoformat() == "2026-06-20"

    raw_row = db_session.scalar(select(RawSourceRow))
    assert len(raw_row.record_hash) == 64
    assert raw_row.extraction_status == "extracted"
    assert raw_row.validation_status == "valid"
    assert raw_row.rejection_details is None


def test_import_rejects_invalid_raw_snapshot_metadata(client):
    audit_payload = payload()
    audit_payload["raw_snapshot"] = {
        "http_status": 99,
        "byte_size": -1,
        "content_sha256": "not-a-sha256",
    }

    response = client.post("/api/v1/import/prices", json=audit_payload, headers=API_KEY)

    assert response.status_code == 400
    fields = {
        ".".join(str(part) for part in detail["loc"] if part != "body")
        for detail in response.json()["error"]["details"]
    }
    assert {
        "raw_snapshot.http_status",
        "raw_snapshot.byte_size",
        "raw_snapshot.content_sha256",
    }.issubset(fields)


def test_invalid_import_row_records_validation_rejection(client, db_session):
    invalid_payload = payload(
        services=[
            {
                "external_id": "srv_bad",
                "name": "Bad service",
                "category": "Diagnostics",
                "price": -1,
                "currency": "KZT",
                "updated_at": "2026-06-17",
            }
        ]
    )

    response = client.post("/api/v1/import/prices", json=invalid_payload, headers=API_KEY)

    assert response.status_code == 200
    raw_row = db_session.scalar(select(RawSourceRow))
    assert len(raw_row.record_hash) == 64
    assert raw_row.extraction_status == "extracted"
    assert raw_row.validation_status == "invalid"
    assert raw_row.rejection_details["code"] == "VALIDATION_ERROR"
    assert db_session.query(PriceObservation).count() == 0


def test_price_update_creates_price_history(client, db_session):
    client.post("/api/v1/import/prices", json=payload(price=25000), headers=API_KEY)
    response = client.post("/api/v1/import/prices", json=payload(price=30000), headers=API_KEY)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["updated_count"] == 1
    current_price = db_session.scalar(select(ClinicServicePrice))
    assert str(current_price.price) in {"30000.00", "30000"}
    history = db_session.scalars(select(PriceHistory).order_by(PriceHistory.id)).all()
    assert [item.change_type for item in history] == ["created", "updated"]
    assert str(history[-1].old_price) in {"25000.00", "25000"}
    assert str(history[-1].new_price) in {"30000.00", "30000"}
    observations = db_session.scalars(select(PriceObservation).order_by(PriceObservation.id)).all()
    assert len(observations) == 2
    assert all(observation.change_detected for observation in observations)


def test_partial_success_saves_import_errors(client, db_session):
    mixed_services = [
        {
            "external_id": "srv_001",
            "name": "МРТ головного мозга",
            "category": "МРТ",
            "price": 25000,
            "currency": "KZT",
            "updated_at": "2026-06-17",
        },
        {
            "external_id": "srv_bad",
            "name": "Bad service",
            "category": "МРТ",
            "price": -1,
            "currency": "KZT",
            "updated_at": "2026-06-17",
        },
    ]

    response = client.post(
        "/api/v1/import/prices",
        json=payload(services=mixed_services),
        headers=API_KEY,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "partial_success"
    assert data["created_count"] == 1
    assert data["error_count"] == 1
    assert data["errors"][0]["external_id"] == "srv_bad"
    assert db_session.scalar(select(ImportBatch).where(ImportBatch.status == "partial_success"))
    assert db_session.scalar(select(ImportErrorRecord).where(ImportErrorRecord.external_id == "srv_bad"))
