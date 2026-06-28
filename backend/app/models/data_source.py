from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base, ID_TYPE


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(ID_TYPE, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    type = Column(String(100), nullable=False)
    public_url = Column(Text, nullable=True)
    robots_policy_notes = Column(Text, nullable=True)
    crawl_delay_seconds = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    clinics = relationship("Clinic", back_populates="data_source")
    services = relationship("Service", back_populates="data_source")
    import_batches = relationship("ImportBatch", back_populates="data_source")
    price_history = relationship("PriceHistory", back_populates="data_source")
    price_observations = relationship("PriceObservation", back_populates="data_source")
    parser_runs = relationship("ParserRun", back_populates="data_source")
    parser_errors = relationship("ParserErrorRecord", back_populates="data_source")
    raw_snapshots = relationship("RawSourceSnapshot", back_populates="data_source")
    raw_rows = relationship("RawSourceRow", back_populates="data_source")

    __table_args__ = (
        Index("ix_data_sources_type", "type"),
    )
