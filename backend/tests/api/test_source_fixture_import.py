from sqlalchemy import select

from app.models import (
    Clinic,
    ClinicServicePrice,
    DataSource,
    ImportBatch,
    ParserRun,
    PriceObservation,
    PriceHistory,
    RawSourceRow,
    RawSourceSnapshot,
    Service,
)
from app.scripts.validate_demo_dataset import validate_demo_dataset
from app.services.source_fixture_import_service import SourceFixtureImportService


def test_source_fixture_import_transforms_and_imports_all_sources(db_session):
    results = SourceFixtureImportService(db_session).import_all()

    assert len(results) == 3
    assert [result.status for result in results] == ["success", "success", "success"]
    assert sum(result.received_count for result in results) == 105
    assert sum(result.created_count for result in results) == 105
    assert sum(result.error_count for result in results) == 0

    assert db_session.query(DataSource).count() == 3
    assert db_session.query(Clinic).count() == 3
    assert db_session.query(Service).count() >= 100
    assert db_session.query(ClinicServicePrice).count() == 105
    assert db_session.query(PriceHistory).count() == 105
    assert db_session.query(PriceObservation).count() == 105
    assert db_session.query(ParserRun).count() == 3
    assert db_session.query(RawSourceSnapshot).count() == 3
    assert db_session.query(RawSourceRow).count() == 105

    prices = db_session.scalars(select(ClinicServicePrice)).all()
    assert all(price.source_url for price in prices)
    assert all(price.parsed_at is not None for price in prices)

    raw_row = db_session.scalar(select(RawSourceRow).where(RawSourceRow.row_index == 0))
    assert raw_row.raw_item["service_name_raw"]
    assert raw_row.raw_item["price_raw"]


def test_source_fixture_import_is_deduplicated_on_repeated_runs(db_session):
    importer = SourceFixtureImportService(db_session)

    first = importer.import_all()
    second = importer.import_all()

    assert sum(result.created_count for result in first) == 105
    assert sum(result.unchanged_count for result in first) == 0
    assert sum(result.created_count for result in second) == 0
    assert sum(result.unchanged_count for result in second) == 105
    assert sum(result.error_count for result in second) == 0

    assert db_session.query(DataSource).count() == 3
    assert db_session.query(Clinic).count() == 3
    assert db_session.query(Service).count() >= 100
    assert db_session.query(ClinicServicePrice).count() == 105
    assert db_session.query(PriceHistory).count() == 105
    assert db_session.query(PriceObservation).count() == 210
    assert db_session.query(ImportBatch).count() == 6
    assert db_session.query(ParserRun).count() == 6
    assert db_session.query(RawSourceSnapshot).count() == 6
    assert db_session.query(RawSourceRow).count() == 210


def test_demo_dataset_validation_passes_after_fixture_import(db_session):
    SourceFixtureImportService(db_session).import_all()

    result = validate_demo_dataset(db_session)

    assert result.is_ready
    assert result.source_count == 3
    assert result.service_price_count == 105
    assert result.normalized_catalog_count >= 50
    assert result.missing_source_url_count == 0
    assert result.missing_parsed_at_count == 0
    assert result.parser_run_count == 3


def test_source_fixture_transform_preserves_crawl_policy_and_raw_metadata(db_session):
    importer = SourceFixtureImportService(db_session)
    fixture_path = importer.fixture_paths()[0]
    fixture = importer.load_fixture(fixture_path)
    payload = importer.to_import_request(fixture, fixture_path)

    assert payload.source == fixture["source"]["id"]
    assert payload.source_type == "public_price_list"
    assert payload.source_url == fixture["source"]["source_url"]
    assert payload.robots_policy_notes == fixture["source"]["robots"]["notes"]
    assert payload.crawl_delay_seconds == fixture["source"]["robots"]["crawl_delay_seconds"]
    assert payload.raw_snapshot is not None
    assert payload.raw_snapshot.raw_payload["fixture"] == str(fixture_path)
    assert payload.services[0]["source_url"] == fixture["rows"][0]["source_url"]
    assert payload.services[0]["parsed_at"] == fixture["rows"][0]["parsed_at"]
    assert payload.services[0]["raw_item"]["raw"]["cells"]
