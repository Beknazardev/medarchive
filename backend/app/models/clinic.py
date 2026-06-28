from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base, ID_TYPE


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(ID_TYPE, primary_key=True)
    data_source_id = Column(ID_TYPE, ForeignKey("data_sources.id"), nullable=False)
    external_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    phone = Column(String(100), nullable=True)
    website = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    data_source = relationship("DataSource", back_populates="clinics")
    branches = relationship("ClinicBranch", back_populates="clinic")
    prices = relationship("ClinicServicePrice", back_populates="clinic")
    price_history = relationship("PriceHistory", back_populates="clinic")

    __table_args__ = (
        UniqueConstraint("data_source_id", "external_id", name="uq_clinics_source_external"),
        Index("ix_clinics_normalized_name", "normalized_name"),
        Index("ix_clinics_city", "city"),
        Index(
            "ix_clinics_name_tsv",
            text("to_tsvector('simple', name)"),
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )
