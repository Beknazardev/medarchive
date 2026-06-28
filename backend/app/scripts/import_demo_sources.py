from __future__ import annotations

import argparse
from pathlib import Path

from app.core import database
from app.services.source_fixture_import_service import (
    DEFAULT_FIXTURES_DIR,
    SourceFixtureImportService,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import deterministic Case 1 demo source fixtures.",
    )
    parser.add_argument(
        "--fixtures-dir",
        default=str(DEFAULT_FIXTURES_DIR),
        help="Directory containing *_adapter_output.json files.",
    )
    parser.add_argument(
        "--skip-catalog-seed",
        action="store_true",
        help="Do not seed the official service catalog before importing fixtures.",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create SQLAlchemy tables before import. Use only for isolated SQLite checks.",
    )
    args = parser.parse_args()

    database.configure_database()
    if args.create_tables:
        database.Base.metadata.create_all(bind=database.engine)

    db = database.SessionLocal()
    try:
        results = SourceFixtureImportService(
            db,
            fixtures_dir=Path(args.fixtures_dir),
        ).import_all(seed_catalog=not args.skip_catalog_seed)
        for result in results:
            print(
                "Imported demo source: "
                f"source={result.source} "
                f"status={result.status} "
                f"received={result.received_count} "
                f"created={result.created_count} "
                f"updated={result.updated_count} "
                f"unchanged={result.unchanged_count} "
                f"errors={result.error_count}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
