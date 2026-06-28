"""Unmatched service review service - handles review actions for unmatched services."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import (
    NormalizedService,
    Service,
    ServiceCategory,
    UnmatchedServiceRecord,
)


class UnmatchedServiceListItem(BaseModel):
    """Schema for unmatched service list item."""

    id: int
    raw_name: str
    raw_category: str
    normalized_raw_name: str
    normalized_raw_category: str
    status: str
    confidence: float
    reason: str
    source_url: str | None
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    reviewed_at: datetime | None
    review_action: str | None
    suggested_normalized_service_id: int | None

    model_config = {"from_attributes": True}


class UnmatchedServiceDetail(BaseModel):
    """Schema for unmatched service detail."""

    id: int
    data_source_id: int
    import_batch_id: int | None
    service_id: int | None
    raw_source_row_id: int | None
    raw_name: str
    raw_category: str
    normalized_raw_name: str
    normalized_raw_category: str
    status: str
    confidence: float
    reason: str
    source_url: str | None
    raw_item: dict[str, Any] | None
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    reviewed_at: datetime | None
    reviewed_by: str | None
    review_action: str | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime
    suggested_normalized_service_id: int | None

    model_config = {"from_attributes": True}


class UnmatchedServiceListResponse(BaseModel):
    """Response for unmatched service list."""

    items: list[UnmatchedServiceListItem]
    total: int
    page: int
    page_size: int


class ReviewAction(BaseModel):
    """Action to review an unmatched service."""

    action: Literal[
        "approve_to_existing",
        "approve_with_new_synonym",
        "create_new_service",
        "reject",
        "needs_clarification",
        "ignore",
    ]
    target_normalized_service_id: int | None = None
    new_service_name: str | None = None
    new_category_name: str | None = None
    new_synonym: str | None = None
    reason: str | None = None
    reviewer: str = "admin"

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid_actions = {
            "approve_to_existing",
            "approve_with_new_synonym",
            "create_new_service",
            "reject",
            "needs_clarification",
            "ignore",
        }
        if v not in valid_actions:
            raise ValueError(f"Invalid action: {v}")
        return v


class ReviewResult(BaseModel):
    """Result of a review action."""

    record_id: int
    action: str
    status: str
    message: str
    affected_services: int = 0


class UnmatchedServiceStats(BaseModel):
    """Statistics for unmatched services."""

    total: int
    open: int
    approved: int
    rejected: int
    needs_clarification: int
    ignored: int


class UnmatchedServiceReviewService:
    """Service for reviewing unmatched services."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_unmatched(
        self,
        *,
        status: str | None = None,
        source_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> UnmatchedServiceListResponse:
        """List unmatched services with filtering and pagination."""
        query = select(UnmatchedServiceRecord)

        if status:
            query = query.where(UnmatchedServiceRecord.status == status)
        if source_id:
            query = query.where(UnmatchedServiceRecord.data_source_id == source_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        query = query.order_by(UnmatchedServiceRecord.last_seen_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        records = self.db.scalars(query).all()

        items = [
            UnmatchedServiceListItem(
                id=record.id,
                raw_name=record.raw_name,
                raw_category=record.raw_category,
                normalized_raw_name=record.normalized_raw_name,
                normalized_raw_category=record.normalized_raw_category,
                status=record.status,
                confidence=float(record.confidence),
                reason=record.reason,
                source_url=record.source_url,
                occurrence_count=record.occurrence_count,
                first_seen_at=record.first_seen_at,
                last_seen_at=record.last_seen_at,
                reviewed_at=record.reviewed_at,
                review_action=record.review_action,
                suggested_normalized_service_id=record.suggested_normalized_service_id,
            )
            for record in records
        ]

        return UnmatchedServiceListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_detail(self, record_id: int) -> UnmatchedServiceDetail | None:
        """Get detailed information about an unmatched service."""
        record = self.db.get(UnmatchedServiceRecord, record_id)
        if not record:
            return None

        return UnmatchedServiceDetail(
            id=record.id,
            data_source_id=record.data_source_id,
            import_batch_id=record.import_batch_id,
            service_id=record.service_id,
            raw_source_row_id=record.raw_source_row_id,
            raw_name=record.raw_name,
            raw_category=record.raw_category,
            normalized_raw_name=record.normalized_raw_name,
            normalized_raw_category=record.normalized_raw_category,
            status=record.status,
            confidence=float(record.confidence),
            reason=record.reason,
            source_url=record.source_url,
            raw_item=record.raw_item,
            occurrence_count=record.occurrence_count,
            first_seen_at=record.first_seen_at,
            last_seen_at=record.last_seen_at,
            reviewed_at=record.reviewed_at,
            reviewed_by=record.reviewed_by,
            review_action=record.review_action,
            review_note=record.review_note,
            created_at=record.created_at,
            updated_at=record.updated_at,
            suggested_normalized_service_id=record.suggested_normalized_service_id,
        )

    def review(self, record_id: int, action: ReviewAction) -> ReviewResult:
        """Review an unmatched service with the specified action."""
        record = self.db.get(UnmatchedServiceRecord, record_id)
        if not record:
            return ReviewResult(
                record_id=record_id,
                action=action.action,
                status="error",
                message=f"Record {record_id} not found",
            )

        if record.status not in ("open", "needs_clarification"):
            return ReviewResult(
                record_id=record_id,
                action=action.action,
                status="error",
                message=f"Record is already {record.status}; cannot review",
            )

        now = datetime.now(UTC)

        if action.action == "approve_to_existing":
            return self._approve_to_existing(record, action, now)
        elif action.action == "approve_with_new_synonym":
            return self._approve_with_new_synonym(record, action, now)
        elif action.action == "create_new_service":
            return self._create_new_service(record, action, now)
        elif action.action == "reject":
            return self._reject(record, action, now)
        elif action.action == "needs_clarification":
            return self._needs_clarification(record, action, now)
        elif action.action == "ignore":
            return self._ignore(record, action, now)
        else:
            return ReviewResult(
                record_id=record_id,
                action=action.action,
                status="error",
                message=f"Unknown action: {action.action}",
            )

    def _approve_to_existing(
        self,
        record: UnmatchedServiceRecord,
        action: ReviewAction,
        now: datetime,
    ) -> ReviewResult:
        """Approve mapping to existing canonical service."""
        if not action.target_normalized_service_id:
            return ReviewResult(
                record_id=record.id,
                action=action.action,
                status="error",
                message="target_normalized_service_id is required for approve_to_existing",
            )

        target_service = self.db.get(NormalizedService, action.target_normalized_service_id)
        if not target_service:
            return ReviewResult(
                record_id=record.id,
                action=action.action,
                status="error",
                message=f"Normalized service {action.target_normalized_service_id} not found",
            )

        # Update the record
        record.status = "approved"
        record.reviewed_at = now
        record.reviewed_by = action.reviewer
        record.review_action = action.action
        record.review_note = action.reason
        record.suggested_normalized_service_id = target_service.id

        # Update affected source services
        affected = self._update_affected_services(record, target_service)

        self.db.flush()

        return ReviewResult(
            record_id=record.id,
            action=action.action,
            status="success",
            message=f"Approved mapping to service '{target_service.name}'",
            affected_services=affected,
        )

    def _approve_with_new_synonym(
        self,
        record: UnmatchedServiceRecord,
        action: ReviewAction,
        now: datetime,
    ) -> ReviewResult:
        """Approve and add as synonym to existing service."""
        if not action.target_normalized_service_id or not action.new_synonym:
            return ReviewResult(
                record_id=record.id,
                action=action.action,
                status="error",
                message="target_normalized_service_id and new_synonym required",
            )

        target_service = self.db.get(NormalizedService, action.target_normalized_service_id)
        if not target_service:
            return ReviewResult(
                record_id=record.id,
                action=action.action,
                status="error",
                message=f"Normalized service {action.target_normalized_service_id} not found",
            )

        # Add synonym
        normalizer = __import__("app.services.normalization_service", fromlist=["EnhancedNormalizationService"]).EnhancedNormalizationService()
        normalized_synonym = normalizer.normalize_service_name(action.new_synonym)

        existing_aliases = list(target_service.aliases or [])
        if normalized_synonym not in existing_aliases:
            existing_aliases.append(normalized_synonym)
            target_service.aliases = sorted(existing_aliases)

        # Update the record
        record.status = "approved"
        record.reviewed_at = now
        record.reviewed_by = action.reviewer
        record.review_action = action.action
        record.review_note = action.reason
        record.suggested_normalized_service_id = target_service.id

        # Update affected source services
        affected = self._update_affected_services(record, target_service)

        self.db.flush()

        return ReviewResult(
            record_id=record.id,
            action=action.action,
            status="success",
            message=f"Added synonym '{normalized_synonym}' to service '{target_service.name}'",
            affected_services=affected,
        )

    def _create_new_service(
        self,
        record: UnmatchedServiceRecord,
        action: ReviewAction,
        now: datetime,
    ) -> ReviewResult:
        """Create a new canonical service."""
        if not action.new_service_name or not action.new_category_name:
            return ReviewResult(
                record_id=record.id,
                action=action.action,
                status="error",
                message="new_service_name and new_category_name required",
            )

        normalizer = __import__("app.services.normalization_service", fromlist=["EnhancedNormalizationService"]).EnhancedNormalizationService()
        slugify = __import__("app.services.normalization_service", fromlist=["slugify"]).slugify

        # Upsert category
        normalized_category = normalizer.normalize_text(action.new_category_name)
        category = self.db.scalar(
            select(ServiceCategory).where(ServiceCategory.normalized_name == normalized_category)
        )
        if not category:
            category = ServiceCategory(
                name=action.new_category_name,
                slug=slugify(action.new_category_name),
                normalized_name=normalized_category,
            )
            self.db.add(category)
            self.db.flush()

        # Create normalized service
        normalized_name = normalizer.normalize_service_name(action.new_service_name)
        slug = slugify(f"{normalized_category}-{normalized_name}")

        new_service = NormalizedService(
            category_id=category.id,
            name=normalized_name,
            slug=slug,
            aliases=[],
        )
        self.db.add(new_service)
        self.db.flush()

        # Update the record
        record.status = "approved"
        record.reviewed_at = now
        record.reviewed_by = action.reviewer
        record.review_action = action.action
        record.review_note = action.reason
        record.suggested_normalized_service_id = new_service.id

        # Update affected source services
        affected = self._update_affected_services(record, new_service)

        self.db.flush()

        return ReviewResult(
            record_id=record.id,
            action=action.action,
            status="success",
            message=f"Created new service '{new_service.name}'",
            affected_services=affected,
        )

    def _reject(
        self,
        record: UnmatchedServiceRecord,
        action: ReviewAction,
        now: datetime,
    ) -> ReviewResult:
        """Reject a non-service/header/no-price row."""
        record.status = "rejected"
        record.reviewed_at = now
        record.reviewed_by = action.reviewer
        record.review_action = action.action
        record.review_note = action.reason or "Rejected"

        self.db.flush()

        return ReviewResult(
            record_id=record.id,
            action=action.action,
            status="success",
            message="Record rejected",
        )

    def _needs_clarification(
        self,
        record: UnmatchedServiceRecord,
        action: ReviewAction,
        now: datetime,
    ) -> ReviewResult:
        """Mark as needing source clarification."""
        record.status = "needs_clarification"
        record.reviewed_at = now
        record.reviewed_by = action.reviewer
        record.review_action = action.action
        record.review_note = action.reason

        self.db.flush()

        return ReviewResult(
            record_id=record.id,
            action=action.action,
            status="success",
            message="Marked as needs clarification",
        )

    def _ignore(
        self,
        record: UnmatchedServiceRecord,
        action: ReviewAction,
        now: datetime,
    ) -> ReviewResult:
        """Ignore with reason without deleting audit history."""
        record.status = "ignored"
        record.reviewed_at = now
        record.reviewed_by = action.reviewer
        record.review_action = action.action
        record.review_note = action.reason or "Ignored"

        self.db.flush()

        return ReviewResult(
            record_id=record.id,
            action=action.action,
            status="success",
            message="Record ignored",
        )

    def _update_affected_services(
        self,
        record: UnmatchedServiceRecord,
        target_service: NormalizedService,
    ) -> int:
        """Update source services that match this unmatched record."""
        if not record.service_id:
            return 0

        service = self.db.get(Service, record.service_id)
        if not service:
            return 0

        service.normalized_service_id = target_service.id
        service.normalization_status = "matched"
        service.normalization_confidence = Decimal("1.0")

        return 1

    def get_stats(self) -> UnmatchedServiceStats:
        """Get statistics for unmatched services."""
        total = self.db.scalar(select(func.count()).select_from(UnmatchedServiceRecord)) or 0
        open_count = self.db.scalar(
            select(func.count()).select_from(UnmatchedServiceRecord).where(
                UnmatchedServiceRecord.status == "open"
            )
        ) or 0
        approved = self.db.scalar(
            select(func.count()).select_from(UnmatchedServiceRecord).where(
                UnmatchedServiceRecord.status == "approved"
            )
        ) or 0
        rejected = self.db.scalar(
            select(func.count()).select_from(UnmatchedServiceRecord).where(
                UnmatchedServiceRecord.status == "rejected"
            )
        ) or 0
        needs_clarification = self.db.scalar(
            select(func.count()).select_from(UnmatchedServiceRecord).where(
                UnmatchedServiceRecord.status == "needs_clarification"
            )
        ) or 0
        ignored = self.db.scalar(
            select(func.count()).select_from(UnmatchedServiceRecord).where(
                UnmatchedServiceRecord.status == "ignored"
            )
        ) or 0

        return UnmatchedServiceStats(
            total=total,
            open=open_count,
            approved=approved,
            rejected=rejected,
            needs_clarification=needs_clarification,
            ignored=ignored,
        )
