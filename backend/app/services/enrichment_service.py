"""Google Places API enrichment service."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Clinic, ClinicBranch

logger = logging.getLogger(__name__)


class EnrichmentConfig(BaseModel):
    """Configuration for map enrichment."""

    enabled: bool = False
    api_key: str | None = None
    budget_daily_usd: float = Field(default=5.0, ge=0)
    timeout_seconds: int = Field(default=10, ge=1, le=30)
    max_retries: int = Field(default=2, ge=0, le=5)
    cache_ttl_days: int = Field(default=30, ge=1, le=365)


class EnrichmentField(BaseModel):
    """A field to enrich from the API."""

    field_name: str
    api_field: str
    cost_sku: str | None = None
    required: bool = False


class EnrichmentResult(BaseModel):
    """Result of an enrichment operation."""

    clinic_id: int
    branch_id: int | None
    provider: str
    fields_updated: list[str]
    fields_skipped: list[str]
    conflicts: list[str]
    timestamp: datetime


class EnrichmentService:
    """Service for enriching clinic/branch data from Google Places API."""

    FIELDS = [
        EnrichmentField(field_name="address", api_field="formattedAddress", cost_sku="basic"),
        EnrichmentField(field_name="phone", api_field="internationalPhoneNumber", cost_sku="contact"),
        EnrichmentField(field_name="website", api_field="websiteUri", cost_sku="contact"),
        EnrichmentField(field_name="latitude", api_field="location.latitude", cost_sku="basic"),
        EnrichmentField(field_name="longitude", api_field="location.longitude", cost_sku="basic"),
        EnrichmentField(field_name="working_hours", api_field="regularOpeningHours", cost_sku="contact"),
        EnrichmentField(field_name="rating", api_field="rating", cost_sku="advanced"),
    ]

    def __init__(
        self,
        db: Session,
        config: EnrichmentConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.db = db
        self.config = config or EnrichmentConfig()
        self.client = client

    def enrich_clinic(
        self,
        clinic_id: int,
        place_id: str,
        *,
        fields: list[str] | None = None,
        dry_run: bool = False,
    ) -> EnrichmentResult | None:
        """Enrich a clinic with data from Google Places API."""
        if not self.config.enabled or not self.config.api_key:
            logger.info("Enrichment disabled; skipping")
            return None

        clinic = self.db.get(Clinic, clinic_id)
        if not clinic:
            return None

        place_data = self._fetch_place(place_id)
        if not place_data:
            return None

        fields_to_enrich = fields or [f.field_name for f in self.FIELDS]
        fields_updated: list[str] = []
        fields_skipped: list[str] = []
        conflicts: list[str] = []

        for field_name in fields_to_enrich:
            api_value = self._extract_field(place_data, field_name)
            if api_value is None:
                fields_skipped.append(field_name)
                continue

            current_value = getattr(clinic, field_name, None)
            if current_value and str(current_value) == str(api_value):
                fields_skipped.append(field_name)
                continue

            if current_value and str(current_value) != str(api_value):
                conflicts.append(field_name)
                logger.warning(
                    f"Conflict on {field_name}: current='{current_value}' vs api='{api_value}'"
                )
                continue

            if not dry_run:
                setattr(clinic, field_name, api_value)

            fields_updated.append(field_name)

        if not dry_run and fields_updated:
            self.db.flush()

        return EnrichmentResult(
            clinic_id=clinic_id,
            branch_id=None,
            provider="google_places",
            fields_updated=fields_updated,
            fields_skipped=fields_skipped,
            conflicts=conflicts,
            timestamp=datetime.now(UTC),
        )

    def enrich_branch(
        self,
        branch_id: int,
        place_id: str,
        *,
        fields: list[str] | None = None,
        dry_run: bool = False,
    ) -> EnrichmentResult | None:
        """Enrich a branch with data from Google Places API."""
        if not self.config.enabled or not self.config.api_key:
            logger.info("Enrichment disabled; skipping")
            return None

        branch = self.db.get(ClinicBranch, branch_id)
        if not branch:
            return None

        place_data = self._fetch_place(place_id)
        if not place_data:
            return None

        fields_to_enrich = fields or [f.field_name for f in self.FIELDS]
        fields_updated: list[str] = []
        fields_skipped: list[str] = []
        conflicts: list[str] = []

        for field_name in fields_to_enrich:
            api_value = self._extract_field(place_data, field_name)
            if api_value is None:
                fields_skipped.append(field_name)
                continue

            current_value = getattr(branch, field_name, None)
            if current_value and str(current_value) == str(api_value):
                fields_skipped.append(field_name)
                continue

            if current_value and str(current_value) != str(api_value):
                conflicts.append(field_name)
                logger.warning(
                    f"Conflict on {field_name}: current='{current_value}' vs api='{api_value}'"
                )
                continue

            if not dry_run:
                setattr(branch, field_name, api_value)

            fields_updated.append(field_name)

        if not dry_run and fields_updated:
            self.db.flush()

        return EnrichmentResult(
            clinic_id=branch.clinic_id,
            branch_id=branch_id,
            provider="google_places",
            fields_updated=fields_updated,
            fields_skipped=fields_skipped,
            conflicts=conflicts,
            timestamp=datetime.now(UTC),
        )

    def _fetch_place(self, place_id: str) -> dict[str, Any] | None:
        """Fetch place data from Google Places API."""
        if not self.config.api_key:
            return None

        url = f"https://places.googleapis.com/v1/places/{place_id}"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.config.api_key,
            "X-Goog-FieldMask": ",".join(f.api_field for f in self.FIELDS),
        }

        for attempt in range(self.config.max_retries + 1):
            try:
                response = httpx.get(
                    url,
                    headers=headers,
                    timeout=self.config.timeout_seconds,
                )
                if response.status_code == 200:
                    return response.json()
                logger.warning(f"API error {response.status_code}: {response.text}")
                return None
            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1}")
                time.sleep(1 * (attempt + 1))
            except Exception as exc:
                logger.error(f"Error fetching place: {exc}")
                return None

        return None

    def _extract_field(self, place_data: dict[str, Any], field_name: str) -> Any:
        """Extract a field from place data."""
        field_map = {
            "address": lambda d: d.get("formattedAddress"),
            "phone": lambda d: d.get("internationalPhoneNumber"),
            "website": lambda d: d.get("websiteUri"),
            "latitude": lambda d: d.get("location", {}).get("latitude"),
            "longitude": lambda d: d.get("location", {}).get("longitude"),
            "working_hours": lambda d: self._format_hours(d.get("regularOpeningHours")),
            "rating": lambda d: d.get("rating"),
        }

        extractor = field_map.get(field_name)
        if extractor:
            return extractor(place_data)
        return None

    def _format_hours(self, hours_data: dict[str, Any] | None) -> str | None:
        """Format opening hours into a readable string."""
        if not hours_data or "weekdayDescriptions" not in hours_data:
            return None

        descriptions = hours_data["weekdayDescriptions"]
        return "; ".join(descriptions[:7])


@dataclass(frozen=True)
class EnrichmentBudget:
    """Track daily enrichment budget."""

    daily_requests: int = 0
    daily_cost_usd: float = 0.0
    last_reset: datetime | None = None

    def can_make_request(self, config: EnrichmentConfig) -> bool:
        """Check if we can make another request within budget."""
        if self.last_reset is None:
            return True
        if (datetime.now(UTC) - self.last_reset).days >= 1:
            return True
        return self.daily_cost_usd < config.budget_daily_usd
