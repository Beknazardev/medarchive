from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base, ID_TYPE


class ClinicBranch(Base):
    __tablename__ = "clinic_branches"

    id = Column(ID_TYPE, primary_key=True)
    clinic_id = Column(ID_TYPE, ForeignKey("clinics.id"), nullable=False)
    external_id = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    address = Column(Text, nullable=False)
    normalized_address = Column(Text, nullable=False)
    phone = Column(String(100), nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    is_default = Column(Boolean, nullable=False, server_default="false")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    clinic = relationship("Clinic", back_populates="branches")
    prices = relationship("ClinicServicePrice", back_populates="branch")
    price_history = relationship("PriceHistory", back_populates="branch")

    __table_args__ = (
        Index(
            "uq_clinic_branches_clinic_external",
            "clinic_id",
            "external_id",
            unique=True,
            postgresql_where=external_id.isnot(None),
        ).ddl_if(dialect="postgresql"),
        Index("ix_clinic_branches_clinic_id", "clinic_id"),
        Index("ix_clinic_branches_city", "city"),
        Index("ix_clinic_branches_normalized_address", "normalized_address"),
    )
