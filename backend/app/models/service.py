from sqlalchemy import (
    Boolean,
    Numeric,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base, ID_TYPE, JSON_TYPE


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id = Column(ID_TYPE, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(255), nullable=False, unique=True)
    normalized_name = Column(String(255), nullable=False, unique=True)
    name_ru = Column(String(255), nullable=True)
    name_kk = Column(String(255), nullable=True)
    name_en = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    normalized_services = relationship("NormalizedService", back_populates="category")
    services = relationship("Service", back_populates="category")


class NormalizedService(Base):
    __tablename__ = "normalized_services"

    id = Column(ID_TYPE, primary_key=True)
    category_id = Column(ID_TYPE, ForeignKey("service_categories.id"), nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True)
    aliases = Column(JSON_TYPE, nullable=False, server_default="[]")
    name_ru = Column(String(255), nullable=True)
    name_kk = Column(String(255), nullable=True)
    name_en = Column(String(255), nullable=True)
    category_ru = Column(String(255), nullable=True)
    category_kk = Column(String(255), nullable=True)
    category_en = Column(String(255), nullable=True)
    canonical_key = Column(String(255), nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    category = relationship("ServiceCategory", back_populates="normalized_services")
    services = relationship("Service", back_populates="normalized_service")
    prices = relationship("ClinicServicePrice", back_populates="normalized_service")

    __table_args__ = (
        Index("ix_normalized_services_category_id", "category_id"),
        Index("ix_normalized_services_aliases", "aliases", postgresql_using="gin").ddl_if(
            dialect="postgresql"
        ),
        Index(
            "ix_normalized_services_name_tsv",
            text("to_tsvector('simple', name)"),
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )


class Service(Base):
    __tablename__ = "services"

    id = Column(ID_TYPE, primary_key=True)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    external_id = Column(String(255), nullable=True)
    category_id = Column(ID_TYPE, ForeignKey("service_categories.id"), nullable=False)
    normalized_service_id = Column(
        ID_TYPE,
        ForeignKey("normalized_services.id"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False)
    normalization_status = Column(String(50), nullable=False, server_default="fallback")
    normalization_confidence = Column(Numeric(4, 3), nullable=False, server_default="0")
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    data_source = relationship("DataSource", back_populates="services")
    category = relationship("ServiceCategory", back_populates="services")
    normalized_service = relationship("NormalizedService", back_populates="services")
    prices = relationship("ClinicServicePrice", back_populates="service")
    price_history = relationship("PriceHistory", back_populates="service")
    unmatched_queue_records = relationship("UnmatchedServiceRecord", back_populates="service")

    __table_args__ = (
        Index(
            "uq_services_source_external",
            "data_source_id",
            "external_id",
            unique=True,
            postgresql_where=external_id.isnot(None),
        ).ddl_if(dialect="postgresql"),
        Index("ix_services_category_id", "category_id"),
        Index("ix_services_normalized_service_id", "normalized_service_id"),
        Index("ix_services_normalized_name", "normalized_name"),
        Index(
            "ix_services_name_tsv",
            text("to_tsvector('simple', name)"),
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )


class UnmatchedServiceRecord(Base):
    __tablename__ = "unmatched_service_records"

    id = Column(ID_TYPE, primary_key=True)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    import_batch_id = Column(ID_TYPE, ForeignKey("import_batches.id"), nullable=True)
    service_id = Column(ID_TYPE, ForeignKey("services.id"), nullable=True)
    raw_source_row_id = Column(ID_TYPE, ForeignKey("raw_source_rows.id"), nullable=True)
    raw_category = Column(String(255), nullable=False)
    raw_name = Column(String(255), nullable=False)
    normalized_raw_category = Column(String(255), nullable=False)
    normalized_raw_name = Column(String(255), nullable=False)
    suggested_normalized_service_id = Column(
        ID_TYPE,
        ForeignKey("normalized_services.id"),
        nullable=True,
    )
    status = Column(String(50), nullable=False, server_default="open")
    confidence = Column(Numeric(4, 3), nullable=False, server_default="0")
    reason = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=True)
    raw_item = Column(JSON_TYPE, nullable=True)
    occurrence_count = Column(Integer, nullable=False, server_default="1")
    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String(255), nullable=True)
    review_action = Column(String(50), nullable=True)
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    service = relationship("Service", back_populates="unmatched_queue_records")
    suggested_normalized_service = relationship("NormalizedService")

    __table_args__ = (
        Index("ix_unmatched_service_records_status", "status"),
        Index("ix_unmatched_service_records_service_id", "service_id"),
        Index("ix_unmatched_service_records_data_source_id", "data_source_id"),
        Index(
            "ix_unmatched_service_records_normalized_raw",
            "normalized_raw_category",
            "normalized_raw_name",
        ),
    )
