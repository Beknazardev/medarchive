from __future__ import annotations

import argparse

from sqlalchemy import select

from app.core import database
from app.models import DataSource, Service, UnmatchedServiceRecord


def main() -> None:
    parser = argparse.ArgumentParser(description="List unmatched imported service rows.")
    parser.add_argument(
        "--status",
        default="open",
        help="Queue status to list. Use 'all' to show every status.",
    )
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    database.configure_database()
    db = database.SessionLocal()
    try:
        statement = (
            select(UnmatchedServiceRecord, Service, DataSource)
            .join(Service, UnmatchedServiceRecord.service_id == Service.id, isouter=True)
            .join(DataSource, UnmatchedServiceRecord.data_source_id == DataSource.id)
            .order_by(UnmatchedServiceRecord.updated_at.desc())
            .limit(args.limit)
        )
        if args.status != "all":
            statement = statement.where(UnmatchedServiceRecord.status == args.status)

        rows = db.execute(statement).all()
        if not rows:
            print("No unmatched service records found.")
            return

        for record, service, data_source in rows:
            print(
                f"#{record.id} status={record.status} confidence={record.confidence} "
                f"source={data_source.name} service_id={service.id if service else '-'}"
            )
            print(f"  raw_category: {record.raw_category}")
            print(f"  raw_name: {record.raw_name}")
            print(f"  source_url: {record.source_url or '-'}")
            print(f"  reason: {record.reason}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
