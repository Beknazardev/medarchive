"""Import all fixture data files into the database."""

from __future__ import annotations

import sys
from pathlib import Path

from app.core import database
from app.services.source_fixture_import_service import (
    DEFAULT_FIXTURES_DIR,
    SourceFixtureImportService,
)


def main() -> None:
    database.configure_database()
    db = database.SessionLocal()

    try:
        service = SourceFixtureImportService(db, fixtures_dir=DEFAULT_FIXTURES_DIR)
        results = service.import_all(seed_catalog=True)

        total_created = 0
        total_updated = 0
        total_errors = 0

        print(f"{'Source':<25} {'Status':<15} {'Created':<10} {'Updated':<10} {'Errors':<10}")
        print("-" * 70)

        for result in results:
            total_created += result.created_count
            total_updated += result.updated_count
            total_errors += result.error_count
            print(
                f"{result.source:<25} "
                f"{result.status:<15} "
                f"{result.created_count:<10} "
                f"{result.updated_count:<10} "
                f"{result.error_count:<10}"
            )

        print("-" * 70)
        print(f"{'TOTAL':<25} {'':<15} {total_created:<10} {total_updated:<10} {total_errors:<10}")
        print(f"\nImported {len(results)} fixtures successfully.")

        print("\nSeeding canonical services with localized names...")
        from app.services.service_catalog_seed_service import ServiceCatalogSeedService
        from app.services.normalization_service import NormalizationService

        seed_service = ServiceCatalogSeedService(db, NormalizationService())
        seed_result = seed_service.seed_canonical_services(commit=True)
        print(f"Canonical services: total={seed_result.total}, created={seed_result.created}, updated={seed_result.updated}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
