from datetime import UTC, date, datetime, timedelta

from app.services.freshness_service import price_freshness


NOW = datetime(2026, 6, 26, 12, 0, tzinfo=UTC)


def test_freshness_is_fresh_through_thirty_days() -> None:
    """Fresh: 0-30 days (updated contract)."""
    assert price_freshness(NOW, now=NOW).state == "fresh"

    thirty_days_old = price_freshness(NOW - timedelta(days=30), now=NOW)

    assert thirty_days_old.state == "fresh"
    assert thirty_days_old.age_days == 30


def test_freshness_is_stale_from_thirty_one_through_ninety_days() -> None:
    """Stale: 31-90 days (updated contract)."""
    thirty_one_days_old = price_freshness(NOW - timedelta(days=31), now=NOW)
    ninety_days_old = price_freshness(NOW - timedelta(days=90), now=NOW)

    assert thirty_one_days_old.state == "stale"
    assert thirty_one_days_old.age_days == 31
    assert ninety_days_old.state == "stale"
    assert ninety_days_old.age_days == 90


def test_freshness_is_expired_after_ninety_days() -> None:
    """Expired: >90 days (updated contract)."""
    result = price_freshness(NOW - timedelta(days=91), now=NOW)

    assert result.state == "expired"
    assert result.age_days == 91


def test_freshness_is_unknown_without_any_timestamp() -> None:
    result = price_freshness(None, None, now=NOW)

    assert result.state == "unknown"
    assert result.age_days is None


def test_freshness_falls_back_to_updated_at_when_parse_time_is_missing() -> None:
    result = price_freshness(None, date(2026, 6, 20), now=NOW)

    assert result.state == "fresh"
    assert result.age_days == 6
