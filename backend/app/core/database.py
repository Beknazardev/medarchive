from collections.abc import Generator
from typing import Any

from sqlalchemy import BigInteger, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import declarative_base

from app.core.config import settings


Base = declarative_base()
ID_TYPE = BigInteger().with_variant(Integer, "sqlite")
JSON_TYPE = JSONB().with_variant(JSON, "sqlite")
engine: Any | None = None
SessionLocal: Any | None = None


def configure_database() -> None:
    global engine, SessionLocal

    if engine is not None and SessionLocal is not None:
        return

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
    except ImportError as exc:
        raise RuntimeError("SQLAlchemy is required for database sessions") from exc

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Any, None, None]:
    configure_database()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
