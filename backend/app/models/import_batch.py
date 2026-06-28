from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base, ID_TYPE, JSON_TYPE


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(ID_TYPE, primary_key=True)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    source_batch_id = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False)
    received_count = Column(Integer, nullable=False, server_default="0")
    created_count = Column(Integer, nullable=False, server_default="0")
    updated_count = Column(Integer, nullable=False, server_default="0")
    unchanged_count = Column(Integer, nullable=False, server_default="0")
    error_count = Column(Integer, nullable=False, server_default="0")
    raw_payload = Column(JSON_TYPE, nullable=True)
    parser_run_id = Column(ID_TYPE, ForeignKey("parser_runs.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    data_source = relationship("DataSource", back_populates="import_batches")
    errors = relationship("ImportErrorRecord", back_populates="import_batch")
    price_history = relationship("PriceHistory", back_populates="import_batch")
    price_observations = relationship("PriceObservation", back_populates="import_batch")
    parser_run = relationship("ParserRun", back_populates="import_batches")
    raw_rows = relationship("RawSourceRow", back_populates="import_batch")

    __table_args__ = (
        Index("ix_import_batches_data_source_id", "data_source_id"),
        Index("ix_import_batches_status", "status"),
        Index("ix_import_batches_created_at", "created_at"),
        Index("ix_import_batches_source_batch_id", "source_batch_id"),
        Index("ix_import_batches_parser_run_id", "parser_run_id"),
    )


class ImportErrorRecord(Base):
    __tablename__ = "import_errors"

    id = Column(ID_TYPE, primary_key=True)
    import_batch_id = Column(ID_TYPE, ForeignKey("import_batches.id"), nullable=False)
    row_index = Column(Integer, nullable=True)
    external_id = Column(String(255), nullable=True)
    code = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    field = Column(String(255), nullable=True)
    raw_item = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    import_batch = relationship("ImportBatch", back_populates="errors")

    __table_args__ = (
        Index("ix_import_errors_import_batch_id", "import_batch_id"),
        Index("ix_import_errors_code", "code"),
        Index("ix_import_errors_created_at", "created_at"),
    )


class ParserRun(Base):
    __tablename__ = "parser_runs"

    id = Column(ID_TYPE, primary_key=True)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    status = Column(String(50), nullable=False)
    source_url = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    parsed_at = Column(DateTime(timezone=True), nullable=True)
    received_count = Column(Integer, nullable=False, server_default="0")
    imported_count = Column(Integer, nullable=False, server_default="0")
    error_count = Column(Integer, nullable=False, server_default="0")
    raw_snapshot_count = Column(Integer, nullable=False, server_default="0")
    raw_row_count = Column(Integer, nullable=False, server_default="0")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    data_source = relationship("DataSource", back_populates="parser_runs")
    import_batches = relationship("ImportBatch", back_populates="parser_run")
    errors = relationship("ParserErrorRecord", back_populates="parser_run")
    raw_snapshots = relationship("RawSourceSnapshot", back_populates="parser_run")
    raw_rows = relationship("RawSourceRow", back_populates="parser_run")
    price_observations = relationship("PriceObservation", back_populates="parser_run")

    __table_args__ = (
        Index("ix_parser_runs_data_source_id", "data_source_id"),
        Index("ix_parser_runs_status", "status"),
        Index("ix_parser_runs_started_at", "started_at"),
        Index("ix_parser_runs_parsed_at", "parsed_at"),
    )


class ParserErrorRecord(Base):
    __tablename__ = "parser_errors"

    id = Column(ID_TYPE, primary_key=True)
    parser_run_id = Column(ID_TYPE, ForeignKey("parser_runs.id"), nullable=False)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    code = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(50), nullable=False, server_default="error")
    stage = Column(String(50), nullable=False, server_default="unknown")
    retryable = Column(Boolean, nullable=False, server_default="false")
    source_url = Column(Text, nullable=True)
    raw_item = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    parser_run = relationship("ParserRun", back_populates="errors")
    data_source = relationship("DataSource", back_populates="parser_errors")

    __table_args__ = (
        Index("ix_parser_errors_parser_run_id", "parser_run_id"),
        Index("ix_parser_errors_data_source_id", "data_source_id"),
        Index("ix_parser_errors_code", "code"),
        Index("ix_parser_errors_created_at", "created_at"),
    )


class RawSourceSnapshot(Base):
    __tablename__ = "raw_source_snapshots"

    id = Column(ID_TYPE, primary_key=True)
    parser_run_id = Column(ID_TYPE, ForeignKey("parser_runs.id"), nullable=True)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    source_url = Column(Text, nullable=True)
    requested_url = Column(Text, nullable=True)
    final_url = Column(Text, nullable=True)
    http_status = Column(Integer, nullable=True)
    response_headers = Column(JSON_TYPE, nullable=True)
    content_type = Column(String(100), nullable=True)
    checksum = Column(String(255), nullable=True)
    content_sha256 = Column(String(64), nullable=True)
    byte_size = Column(Integer, nullable=True)
    storage_uri = Column(Text, nullable=True)
    source_document_date = Column(Date, nullable=True)
    raw_payload = Column(JSON_TYPE, nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    retention_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    parser_run = relationship("ParserRun", back_populates="raw_snapshots")
    data_source = relationship("DataSource", back_populates="raw_snapshots")
    raw_rows = relationship("RawSourceRow", back_populates="snapshot")

    __table_args__ = (
        Index("ix_raw_source_snapshots_parser_run_id", "parser_run_id"),
        Index("ix_raw_source_snapshots_data_source_id", "data_source_id"),
        Index("ix_raw_source_snapshots_captured_at", "captured_at"),
        Index("ix_raw_source_snapshots_retention_until", "retention_until"),
    )


class RawSourceRow(Base):
    __tablename__ = "raw_source_rows"

    id = Column(ID_TYPE, primary_key=True)
    parser_run_id = Column(ID_TYPE, ForeignKey("parser_runs.id"), nullable=True)
    snapshot_id = Column(ID_TYPE, ForeignKey("raw_source_snapshots.id"), nullable=True)
    import_batch_id = Column(ID_TYPE, ForeignKey("import_batches.id"), nullable=True)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    row_index = Column(Integer, nullable=True)
    source_url = Column(Text, nullable=True)
    raw_item = Column(JSON_TYPE, nullable=True)
    record_hash = Column(String(64), nullable=True)
    extraction_status = Column(String(50), nullable=False, server_default="extracted")
    validation_status = Column(String(50), nullable=False, server_default="pending")
    rejection_details = Column(JSON_TYPE, nullable=True)
    service_id = Column(ID_TYPE, ForeignKey("services.id"), nullable=True)
    clinic_service_price_id = Column(ID_TYPE, ForeignKey("clinic_service_prices.id"), nullable=True)
    retention_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    parser_run = relationship("ParserRun", back_populates="raw_rows")
    snapshot = relationship("RawSourceSnapshot", back_populates="raw_rows")
    import_batch = relationship("ImportBatch", back_populates="raw_rows")
    data_source = relationship("DataSource", back_populates="raw_rows")
    price_observations = relationship("PriceObservation", back_populates="raw_source_row")

    __table_args__ = (
        Index("ix_raw_source_rows_parser_run_id", "parser_run_id"),
        Index("ix_raw_source_rows_snapshot_id", "snapshot_id"),
        Index("ix_raw_source_rows_import_batch_id", "import_batch_id"),
        Index("ix_raw_source_rows_data_source_id", "data_source_id"),
        Index("ix_raw_source_rows_service_id", "service_id"),
        Index("ix_raw_source_rows_clinic_service_price_id", "clinic_service_price_id"),
        Index("ix_raw_source_rows_retention_until", "retention_until"),
        Index("ix_raw_source_rows_record_hash", "record_hash"),
        Index("ix_raw_source_rows_validation_status", "validation_status"),
    )
