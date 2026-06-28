from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base, ID_TYPE


class ClinicServicePrice(Base):
    __tablename__ = "clinic_service_prices"

    id = Column(ID_TYPE, primary_key=True)
    clinic_id = Column(ID_TYPE, ForeignKey("clinics.id"), nullable=False)
    branch_id = Column(ID_TYPE, ForeignKey("clinic_branches.id"), nullable=False)
    service_id = Column(ID_TYPE, ForeignKey("services.id"), nullable=False)
    normalized_service_id = Column(
        ID_TYPE,
        ForeignKey("normalized_services.id"),
        nullable=False,
    )
    price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    is_available = Column(Boolean, nullable=False, server_default="true")
    updated_at = Column(Date, nullable=False)
    source_url = Column(String(2048), nullable=True)
    parsed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    system_updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    clinic = relationship("Clinic", back_populates="prices")
    branch = relationship("ClinicBranch", back_populates="prices")
    service = relationship("Service", back_populates="prices")
    normalized_service = relationship("NormalizedService", back_populates="prices")
    history = relationship("PriceHistory", back_populates="clinic_service_price")
    observations = relationship("PriceObservation", back_populates="clinic_service_price")

    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "branch_id",
            "service_id",
            "currency",
            name="uq_clinic_service_prices_current",
        ),
        Index("ix_clinic_service_prices_normalized_service_id", "normalized_service_id"),
        Index("ix_clinic_service_prices_clinic_id", "clinic_id"),
        Index("ix_clinic_service_prices_branch_id", "branch_id"),
        Index("ix_clinic_service_prices_price", "price"),
        Index("ix_clinic_service_prices_currency", "currency"),
        Index("ix_clinic_service_prices_updated_at", "updated_at"),
        Index("ix_clinic_service_prices_parsed_at", "parsed_at"),
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(ID_TYPE, primary_key=True)
    clinic_service_price_id = Column(
        ID_TYPE,
        ForeignKey("clinic_service_prices.id"),
        nullable=False,
    )
    clinic_id = Column(ID_TYPE, ForeignKey("clinics.id"), nullable=False)
    branch_id = Column(ID_TYPE, ForeignKey("clinic_branches.id"), nullable=False)
    service_id = Column(ID_TYPE, ForeignKey("services.id"), nullable=False)
    old_price = Column(Numeric(12, 2), nullable=True)
    new_price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    change_type = Column(String(50), nullable=False)
    import_batch_id = Column(ID_TYPE, ForeignKey("import_batches.id"), nullable=False)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    source_url = Column(String(2048), nullable=True)
    parsed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    clinic_service_price = relationship("ClinicServicePrice", back_populates="history")
    clinic = relationship("Clinic", back_populates="price_history")
    branch = relationship("ClinicBranch", back_populates="price_history")
    service = relationship("Service", back_populates="price_history")
    import_batch = relationship("ImportBatch", back_populates="price_history")
    data_source = relationship("DataSource", back_populates="price_history")

    __table_args__ = (
        Index("ix_price_history_clinic_service_price_id", "clinic_service_price_id"),
        Index("ix_price_history_clinic_id", "clinic_id"),
        Index("ix_price_history_service_id", "service_id"),
        Index("ix_price_history_changed_at", "changed_at"),
        Index("ix_price_history_parsed_at", "parsed_at"),
        Index("ix_price_history_import_batch_id", "import_batch_id"),
    )


class PriceObservation(Base):
    """One successful source observation, including unchanged repeat observations."""

    __tablename__ = "price_observations"

    id = Column(ID_TYPE, primary_key=True)
    clinic_service_price_id = Column(
        ID_TYPE,
        ForeignKey("clinic_service_prices.id"),
        nullable=False,
    )
    clinic_id = Column(ID_TYPE, ForeignKey("clinics.id"), nullable=False)
    branch_id = Column(ID_TYPE, ForeignKey("clinic_branches.id"), nullable=False)
    service_id = Column(ID_TYPE, ForeignKey("services.id"), nullable=False)
    normalized_service_id = Column(
        ID_TYPE,
        ForeignKey("normalized_services.id"),
        nullable=False,
    )
    import_batch_id = Column(ID_TYPE, ForeignKey("import_batches.id"), nullable=False)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    parser_run_id = Column(ID_TYPE, ForeignKey("parser_runs.id"), nullable=True)
    raw_source_row_id = Column(ID_TYPE, ForeignKey("raw_source_rows.id"), nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    is_available = Column(Boolean, nullable=False, server_default="true")
    source_updated_at = Column(Date, nullable=False)
    source_url = Column(String(2048), nullable=True)
    parsed_at = Column(DateTime(timezone=True), nullable=False)
    change_detected = Column(Boolean, nullable=False, server_default="false")
    observed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    clinic_service_price = relationship("ClinicServicePrice", back_populates="observations")
    import_batch = relationship("ImportBatch", back_populates="price_observations")
    data_source = relationship("DataSource", back_populates="price_observations")
    parser_run = relationship("ParserRun", back_populates="price_observations")
    raw_source_row = relationship("RawSourceRow", back_populates="price_observations")

    __table_args__ = (
        Index("ix_price_observations_current_price_id", "clinic_service_price_id"),
        Index("ix_price_observations_service_id", "service_id"),
        Index("ix_price_observations_normalized_service_id", "normalized_service_id"),
        Index("ix_price_observations_import_batch_id", "import_batch_id"),
        Index("ix_price_observations_data_source_id", "data_source_id"),
        Index("ix_price_observations_parser_run_id", "parser_run_id"),
        Index("ix_price_observations_raw_source_row_id", "raw_source_row_id"),
        Index("ix_price_observations_observed_at", "observed_at"),
        Index("ix_price_observations_parsed_at", "parsed_at"),
    )
