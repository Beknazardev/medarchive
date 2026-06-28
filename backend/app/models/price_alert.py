"""Price alert model - admin-only prototype."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)

from app.core.database import Base, ID_TYPE


class PriceAlert(Base):
    """Price alert subscription (admin-only prototype)."""
    __tablename__ = "price_alerts"

    id = Column(ID_TYPE, primary_key=True)
    normalized_service_id = Column(Integer, ForeignKey("normalized_services.id"), nullable=False)
    clinic_id = Column(Integer, nullable=True)
    branch_id = Column(Integer, nullable=True)
    target_price = Column(Numeric(12, 2), nullable=False)
    threshold_type = Column(String(20), nullable=False, server_default="below")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    notify_method = Column(String(20), nullable=False, server_default="log_only")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
