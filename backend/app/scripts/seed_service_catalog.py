from app.core import database
from app.services.service_catalog_seed_service import ServiceCatalogSeedService


def main() -> None:
    database.configure_database()
    db = database.SessionLocal()
    try:
        result = ServiceCatalogSeedService(db).seed_default_catalog()
        print(
            "Seeded service catalog: "
            f"total={result.total}, created={result.created}, updated={result.updated}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
