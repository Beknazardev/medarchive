"""Price alert schemas and service - admin-only deterministic prototype.

This is a DRAFT implementation for design review. It does NOT:
- Send real emails/SMS/notifications
- Expose public subscription endpoints
- Process real user contact information

It DOES:
- Define the data model for future implementation
- Provide admin-only CRUD for alert configurations
- Simulate alert evaluation against price changes
- Log what would be sent (dry-run only)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import Base, ID_TYPE
from app.models import PriceAlert


# ─── Schemas ───

class ThresholdType(str, Enum):
    BELOW = "below"
    ABOVE = "above"
    CHANGED = "changed"


class NotifyMethod(str, Enum):
    LOG_ONLY = "log_only"  # Admin-only prototype
    # Future: email, sms, webhook


class AlertCreate(BaseModel):
    """Create a price alert (admin-only)."""
    normalized_service_id: int
    clinic_id: int | None = None
    branch_id: int | None = None
    target_price: Decimal = Field(ge=0)
    threshold_type: ThresholdType = ThresholdType.BELOW
    notify_method: NotifyMethod = NotifyMethod.LOG_ONLY

    @field_validator("target_price")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Price must be non-negative")
        return v


class AlertResponse(BaseModel):
    """Response for alert operations."""
    id: int
    normalized_service_id: int
    clinic_id: int | None
    branch_id: int | None
    target_price: Decimal
    threshold_type: str
    is_active: bool
    notify_method: str
    created_at: datetime
    last_triggered_at: datetime | None


class AlertEvaluationResult(BaseModel):
    """Result of evaluating an alert."""
    alert_id: int
    triggered: bool
    current_price: Decimal | None
    target_price: Decimal
    threshold_type: str
    reason: str


class AlertStats(BaseModel):
    """Alert statistics."""
    total_alerts: int
    active_alerts: int
    triggered_today: int


# ─── Service ───

class PriceAlertService:
    """Admin-only price alert service (dry-run prototype)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_alert(self, alert: AlertCreate) -> AlertResponse:
        """Create a new price alert."""
        from app.models import PriceAlert

        db_alert = PriceAlert(
            normalized_service_id=alert.normalized_service_id,
            clinic_id=alert.clinic_id,
            branch_id=alert.branch_id,
            target_price=alert.target_price,
            threshold_type=alert.threshold_type.value,
            notify_method=alert.notify_method.value,
        )
        self.db.add(db_alert)
        self.db.flush()

        return AlertResponse(
            id=db_alert.id,
            normalized_service_id=db_alert.normalized_service_id,
            clinic_id=db_alert.clinic_id,
            branch_id=db_alert.branch_id,
            target_price=db_alert.target_price,
            threshold_type=db_alert.threshold_type,
            is_active=db_alert.is_active,
            notify_method=db_alert.notify_method,
            created_at=db_alert.created_at,
            last_triggered_at=db_alert.last_triggered_at,
        )

    def list_alerts(self, active_only: bool = True) -> list[AlertResponse]:
        """List all alerts."""
        from app.models import PriceAlert

        query = self.db.query(PriceAlert)
        if active_only:
            query = query.filter(PriceAlert.is_active == True)

        alerts = query.all()
        return [
            AlertResponse(
                id=a.id,
                normalized_service_id=a.normalized_service_id,
                clinic_id=a.clinic_id,
                branch_id=a.branch_id,
                target_price=a.target_price,
                threshold_type=a.threshold_type,
                is_active=a.is_active,
                notify_method=a.notify_method,
                created_at=a.created_at,
                last_triggered_at=a.last_triggered_at,
            )
            for a in alerts
        ]

    def deactivate_alert(self, alert_id: int) -> bool:
        """Deactivate an alert."""
        from app.models import PriceAlert

        alert = self.db.get(PriceAlert, alert_id)
        if not alert:
            return False

        alert.is_active = False
        self.db.flush()
        return True

    def evaluate_alerts(self, price_changes: list[dict[str, Any]]) -> list[AlertEvaluationResult]:
        """Evaluate alerts against price changes (dry-run only)."""
        from app.models import PriceAlert, ClinicServicePrice

        results: list[AlertEvaluationResult] = []
        alerts = self.db.query(PriceAlert).filter(PriceAlert.is_active == True).all()

        for alert in alerts:
            current_price = self._get_current_price(
                alert.normalized_service_id,
                alert.clinic_id,
                alert.branch_id,
            )

            if current_price is None:
                results.append(AlertEvaluationResult(
                    alert_id=alert.id,
                    triggered=False,
                    current_price=None,
                    target_price=alert.target_price,
                    threshold_type=alert.threshold_type,
                    reason="No current price found",
                ))
                continue

            triggered = False
            reason = ""

            if alert.threshold_type == "below" and current_price < alert.target_price:
                triggered = True
                reason = f"Price {current_price} is below target {alert.target_price}"
            elif alert.threshold_type == "above" and current_price > alert.target_price:
                triggered = True
                reason = f"Price {current_price} is above target {alert.target_price}"
            elif alert.threshold_type == "changed":
                triggered = True
                reason = f"Price changed to {current_price}"

            if triggered:
                # Dry-run: log but do not send
                print(f"[DRY-RUN] Alert {alert.id} triggered: {reason}")
                alert.last_triggered_at = datetime.now(UTC)

            results.append(AlertEvaluationResult(
                alert_id=alert.id,
                triggered=triggered,
                current_price=current_price,
                target_price=alert.target_price,
                threshold_type=alert.threshold_type,
                reason=reason,
            ))

        self.db.flush()
        return results

    def _get_current_price(
        self,
        normalized_service_id: int,
        clinic_id: int | None,
        branch_id: int | None,
    ) -> Decimal | None:
        """Get current price for a service."""
        from app.models import ClinicServicePrice

        query = self.db.query(ClinicServicePrice).filter(
            ClinicServicePrice.normalized_service_id == normalized_service_id,
        )

        if clinic_id:
            query = query.filter(ClinicServicePrice.clinic_id == clinic_id)
        if branch_id:
            query = query.filter(ClinicServicePrice.branch_id == branch_id)

        price = query.first()
        return price.price if price else None

    def get_stats(self) -> AlertStats:
        """Get alert statistics."""
        from app.models import PriceAlert

        total = self.db.query(PriceAlert).count()
        active = self.db.query(PriceAlert).filter(PriceAlert.is_active == True).count()

        today = datetime.now(UTC).date()
        triggered_today = self.db.query(PriceAlert).filter(
            PriceAlert.last_triggered_at >= datetime.combine(today, datetime.min.time().replace(tzinfo=UTC))
        ).count()

        return AlertStats(
            total_alerts=total,
            active_alerts=active,
            triggered_today=triggered_today,
        )
