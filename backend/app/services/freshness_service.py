"""Freshness service with updated 30/90-day contract."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Literal


FreshnessState = Literal["fresh", "stale", "expired", "unknown"]

FRESH_MAX_DAYS = 30
STALE_MAX_DAYS = 90


@dataclass(frozen=True)
class FreshnessInfo:
    state: FreshnessState
    age_days: int | None
    warning: str | None = None


def price_freshness(
    parsed_at: datetime | None,
    updated_at: date | None = None,
    now: datetime | None = None,
) -> FreshnessInfo:
    """Calculate price freshness based on updated 30/90-day contract.

    - fresh: 0-30 days
    - stale: 31-90 days
    - expired: >90 days
    - unknown: no trustworthy parsed_at
    """
    reference_at = _reference_datetime(parsed_at=parsed_at, updated_at=updated_at)
    if reference_at is None:
        return FreshnessInfo(state="unknown", age_days=None)

    current = _as_utc(now or datetime.now(UTC))
    age_days = max((current.date() - reference_at.date()).days, 0)

    if age_days <= FRESH_MAX_DAYS:
        return FreshnessInfo(state="fresh", age_days=age_days)

    if age_days <= STALE_MAX_DAYS:
        return FreshnessInfo(
            state="stale",
            age_days=age_days,
            warning="Price data is 31-90 days old; verify current accuracy",
        )

    return FreshnessInfo(
        state="expired",
        age_days=age_days,
        warning="Price data is over 90 days old; may not reflect current prices",
    )


def freshness_badge(state: FreshnessState) -> dict[str, str]:
    """Get display badge for freshness state."""
    badges = {
        "fresh": {"label": "Fresh", "color": "green"},
        "stale": {"label": "Stale", "color": "yellow"},
        "expired": {"label": "Expired", "color": "red"},
        "unknown": {"label": "Unknown", "color": "gray"},
    }
    return badges.get(state, badges["unknown"])


def _reference_datetime(parsed_at: datetime | None, updated_at: date | None) -> datetime | None:
    if parsed_at is not None:
        return _as_utc(parsed_at)
    if updated_at is not None:
        return datetime.combine(updated_at, time.min, tzinfo=UTC)
    return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
