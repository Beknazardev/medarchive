from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from app.ingestion.contracts import SourceConfig, SourceFormat, SourceMode, SourcePolicyMetadata
from app.ingestion.fetcher import (
    ConditionalRequest,
    FetchFailure,
    FetchLimits,
    FetchRequest,
    SafeFetchOrchestrator,
    SafeHttpFetcher,
    build_user_agent,
)
from app.ingestion.rate_limit import HostRateLimiter
from app.ingestion.registry import SourceRegistry
from app.ingestion.robots import RobotsPolicyCache
from app.ingestion.storage import FilesystemRawStorage, MemoryRawStorage
from app.models import DataSource, ParserErrorRecord, RawSourceSnapshot
from app.services.parser_audit_service import ParserAuditService


PUBLIC_IP = "93.184.216.34"
ROBOTS_URL = "https://prices.example.kz/robots.txt"
PRICE_URL = "https://prices.example.kz/prices"


class FakeResolver:
    def __init__(self, addresses: dict[str, tuple[str, ...]] | None = None) -> None:
        self.addresses = addresses or {"prices.example.kz": (PUBLIC_IP,)}
        self.calls: list[str] = []

    def resolve(self, host: str) -> tuple[str, ...]:
        self.calls.append(host)
        return self.addresses[host]


class NoWait:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_config(**updates) -> SourceConfig:
    values = {
        "source_id": "safe_source",
        "display_name": "Safe source",
        "source_type": "laboratory",
        "mode": SourceMode.LIVE,
        "priority": "P0",
        "formats": (SourceFormat.HTML,),
        "allowed_hosts": ("prices.example.kz",),
        "allowed_path_prefixes": ("/prices",),
        "forbidden_path_prefixes": ("/prices/login",),
        "start_urls": (PRICE_URL,),
        "city_scope": ("Астана",),
        "minimum_delay_seconds": 0,
        "max_concurrency": 1,
        "max_pages_per_run": 3,
        "max_document_bytes": 1024,
        "adapter_version": "0.1.0",
        "policy": SourcePolicyMetadata(
            robots_url=ROBOTS_URL,
            checked_at=datetime(2026, 6, 27, tzinfo=UTC),
            terms_review_status="reviewed",
            evidence_urls=(PRICE_URL,),
            notes="Test-only public fixture source.",
        ),
        "enabled": True,
    }
    values.update(updates)
    return SourceConfig.model_validate(values)


def make_fetcher(
    handler,
    *,
    config: SourceConfig | None = None,
    resolver: FakeResolver | None = None,
    limits: FetchLimits | None = None,
    storage=None,
    audit_service=None,
):
    fake_time = NoWait()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetcher = SafeHttpFetcher(
        registry=SourceRegistry((config or make_config(),)),
        client=client,
        user_agent="MedPriceBot/0.1.0 (+mailto:test@example.com)",
        resolver=resolver or FakeResolver(),
        robots=RobotsPolicyCache(now=lambda: datetime(2026, 6, 27, tzinfo=UTC)),
        rate_limiter=HostRateLimiter(clock=fake_time.clock, sleeper=fake_time.sleep),
        limits=limits or FetchLimits(max_retries=2, retry_base_seconds=0),
        sleeper=fake_time.sleep,
        random_value=lambda: 0,
        storage=storage or MemoryRawStorage(),
        audit_service=audit_service,
    )
    return fetcher, fake_time


def allow_robots(request: httpx.Request) -> httpx.Response | None:
    if str(request.url) == ROBOTS_URL:
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            text="User-agent: *\nAllow: /prices\n",
        )
    return None


def test_ssrf_private_dns_is_blocked_before_request():
    requests: list[str] = []

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "text/html"}, text="unused")

    fetcher, _ = make_fetcher(
        handler,
        resolver=FakeResolver({"prices.example.kz": ("127.0.0.1",)}),
    )

    with pytest.raises(FetchFailure) as exc_info:
        fetcher.fetch("safe_source", PRICE_URL)

    assert exc_info.value.code == "SSRF_BLOCKED"
    assert requests == []


def test_redirect_target_is_revalidated_and_private_destination_is_blocked():
    requested: list[str] = []
    config = make_config(
        allowed_hosts=("prices.example.kz", "redirect.example.kz"),
    )
    resolver = FakeResolver(
        {
            "prices.example.kz": (PUBLIC_IP,),
            "redirect.example.kz": ("169.254.169.254",),
        }
    )

    def handler(request):
        requested.append(str(request.url))
        robots = allow_robots(request)
        if robots:
            return robots
        return httpx.Response(302, headers={"location": "https://redirect.example.kz/prices"})

    fetcher, _ = make_fetcher(handler, config=config, resolver=resolver)

    with pytest.raises(FetchFailure) as exc_info:
        fetcher.fetch("safe_source", PRICE_URL)

    assert exc_info.value.code == "SSRF_BLOCKED"
    assert "https://redirect.example.kz/prices" not in requested


def test_forbidden_path_is_blocked_before_request():
    requested: list[str] = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "text/html"}, text="unused")

    fetcher, _ = make_fetcher(handler)

    with pytest.raises(FetchFailure) as exc_info:
        fetcher.fetch("safe_source", "https://prices.example.kz/prices/login")

    assert exc_info.value.code == "FORBIDDEN_PATH"
    assert requested == []


def test_percent_encoded_forbidden_path_is_blocked_before_request():
    requested: list[str] = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "text/html"}, text="unused")

    fetcher, _ = make_fetcher(handler)

    with pytest.raises(FetchFailure) as exc_info:
        fetcher.fetch("safe_source", "https://prices.example.kz/prices/%6cogin")

    assert exc_info.value.code == "FORBIDDEN_PATH"
    assert requested == []


def test_robots_disallow_fails_closed_before_content_request():
    requested: list[str] = []

    def handler(request):
        requested.append(str(request.url))
        if str(request.url) == ROBOTS_URL:
            return httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                text="User-agent: *\nDisallow: /prices\n",
            )
        return httpx.Response(200, headers={"content-type": "text/html"}, text="not reached")

    fetcher, _ = make_fetcher(handler)

    with pytest.raises(FetchFailure) as exc_info:
        fetcher.fetch("safe_source", PRICE_URL)

    assert exc_info.value.code == "ROBOTS_DISALLOWED"
    assert requested == [ROBOTS_URL]


def test_robots_unavailable_fails_closed():
    def handler(request):
        raise httpx.ReadTimeout("robots timeout", request=request)

    fetcher, _ = make_fetcher(handler)

    with pytest.raises(FetchFailure) as exc_info:
        fetcher.fetch("safe_source", PRICE_URL)

    assert exc_info.value.code == "ROBOTS_UNAVAILABLE"
    assert exc_info.value.retryable is False


def test_robots_policy_is_cached_for_repeated_fetches():
    robots_calls = 0

    def handler(request):
        nonlocal robots_calls
        robots = allow_robots(request)
        if robots:
            robots_calls += 1
            return robots
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html/>")

    fetcher, _ = make_fetcher(handler)

    fetcher.fetch("safe_source", PRICE_URL)
    fetcher.fetch("safe_source", PRICE_URL)

    assert robots_calls == 1


def test_oversized_body_is_rejected():
    config = make_config(max_document_bytes=5)

    def handler(request):
        robots = allow_robots(request)
        if robots:
            return robots
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"123456")

    fetcher, _ = make_fetcher(handler, config=config)

    with pytest.raises(FetchFailure) as exc_info:
        fetcher.fetch("safe_source", PRICE_URL)

    assert exc_info.value.code == "RESPONSE_TOO_LARGE"


def test_wrong_content_type_is_rejected_without_retry():
    calls = 0
    storage = MemoryRawStorage()

    def handler(request):
        nonlocal calls
        robots = allow_robots(request)
        if robots:
            return robots
        calls += 1
        return httpx.Response(200, headers={"content-type": "application/zip"}, content=b"zip")

    fetcher, fake_time = make_fetcher(handler, storage=storage)

    with pytest.raises(FetchFailure) as exc_info:
        fetcher.fetch("safe_source", PRICE_URL)

    assert exc_info.value.code == "UNEXPECTED_CONTENT_TYPE"
    assert calls == 1
    assert fake_time.sleeps == []
    assert tuple(storage.documents.values()) == (b"zip",)


@pytest.mark.parametrize(
    ("status_code", "body", "expected_code"),
    [
        (403, b"forbidden", "AUTH_OR_BOT_BLOCKED"),
        (200, b"<html><title>CAPTCHA</title></html>", "CAPTCHA_DETECTED"),
    ],
)
def test_auth_and_captcha_failures_are_not_retried(status_code, body, expected_code):
    calls = 0

    def handler(request):
        nonlocal calls
        robots = allow_robots(request)
        if robots:
            return robots
        calls += 1
        return httpx.Response(
            status_code,
            headers={"content-type": "text/html"},
            content=body,
        )

    fetcher, fake_time = make_fetcher(handler)

    with pytest.raises(FetchFailure) as exc_info:
        fetcher.fetch("safe_source", PRICE_URL)

    assert exc_info.value.code == expected_code
    assert calls == 1
    assert fake_time.sleeps == []


def test_timeout_is_bounded_and_retried_then_succeeds():
    target_calls = 0

    def handler(request):
        nonlocal target_calls
        robots = allow_robots(request)
        if robots:
            return robots
        target_calls += 1
        if target_calls < 3:
            raise httpx.ReadTimeout("temporary timeout", request=request)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<table/>")

    fetcher, fake_time = make_fetcher(handler)

    outcome = fetcher.fetch("safe_source", PRICE_URL)

    assert outcome.document is not None
    assert outcome.attempts == 3
    assert target_calls == 3
    assert len(fake_time.sleeps) == 2


def test_conditional_get_returns_not_modified_without_raw_document():
    seen_headers: dict[str, str] = {}

    def handler(request):
        robots = allow_robots(request)
        if robots:
            return robots
        seen_headers.update(request.headers)
        return httpx.Response(304, headers={"etag": '"v2"'})

    fetcher, _ = make_fetcher(handler)

    outcome = fetcher.fetch(
        "safe_source",
        PRICE_URL,
        conditional=ConditionalRequest(
            etag='"v1"',
            last_modified="Fri, 26 Jun 2026 10:00:00 GMT",
        ),
    )

    assert outcome.not_modified is True
    assert outcome.document is None
    assert outcome.etag == '"v2"'
    assert seen_headers["if-none-match"] == '"v1"'
    assert seen_headers["if-modified-since"] == "Fri, 26 Jun 2026 10:00:00 GMT"


def test_response_is_hashed_stored_and_persisted_to_parser_audit(db_session, tmp_path):
    body = b"<html><table><tr><td>1000</td></tr></table></html>"
    data_source = DataSource(name="safe_source", type="laboratory", is_active=True)
    db_session.add(data_source)
    db_session.flush()
    audit = ParserAuditService(db_session)
    parser_run = audit.create_parser_run(data_source, source_url=PRICE_URL)

    def handler(request):
        robots = allow_robots(request)
        if robots:
            return robots
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html; charset=utf-8",
                "etag": '"fixture-v1"',
            },
            content=body,
        )

    storage = FilesystemRawStorage(tmp_path)
    fetcher, _ = make_fetcher(handler, storage=storage, audit_service=audit)

    outcome = fetcher.fetch(
        "safe_source",
        PRICE_URL,
        data_source=data_source,
        parser_run=parser_run,
    )

    assert outcome.document is not None
    assert outcome.document.storage_uri is not None
    stored_path = storage.path_for(outcome.document)
    assert stored_path.read_bytes() == body

    snapshot = db_session.scalar(select(RawSourceSnapshot))
    assert snapshot.content_sha256 == outcome.document.content_sha256
    assert snapshot.byte_size == len(body)
    assert snapshot.http_status == 200
    assert snapshot.storage_uri == outcome.document.storage_uri
    assert parser_run.raw_snapshot_count == 1


def test_final_fetch_failure_persists_stage_code_and_retryability(db_session):
    data_source = DataSource(name="safe_source", type="laboratory", is_active=True)
    db_session.add(data_source)
    db_session.flush()
    audit = ParserAuditService(db_session)
    parser_run = audit.create_parser_run(data_source, source_url=PRICE_URL)

    def handler(request):
        robots = allow_robots(request)
        if robots:
            return robots
        raise httpx.ReadTimeout("still unavailable", request=request)

    fetcher, _ = make_fetcher(handler, audit_service=audit)

    with pytest.raises(FetchFailure):
        fetcher.fetch(
            "safe_source",
            PRICE_URL,
            data_source=data_source,
            parser_run=parser_run,
        )

    error = db_session.scalar(select(ParserErrorRecord))
    assert error.stage == "fetch"
    assert error.code == "FETCH_TIMEOUT"
    assert error.retryable is True
    assert error.source_url == PRICE_URL
    assert parser_run.error_count == 1


def test_orchestrator_isolates_source_failures():
    def handler(request):
        robots = allow_robots(request)
        if robots:
            return robots
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html/>")

    fetcher, _ = make_fetcher(handler)
    orchestrator = SafeFetchOrchestrator(fetcher)

    results = orchestrator.run(
        (
            FetchRequest("unknown_source", "https://unknown.example.kz/prices"),
            FetchRequest("safe_source", "https://prices.example.kz/prices/login"),
            FetchRequest("safe_source", PRICE_URL),
        )
    )

    assert len(results) == 3
    assert results[0].error is not None
    assert results[0].error.code == "UNEXPECTED_FETCH_ERROR"
    assert results[1].error is not None
    assert results[2].outcome is not None


def test_orchestrator_enforces_per_source_page_cap():
    config = make_config(max_pages_per_run=1)

    def handler(request):
        robots = allow_robots(request)
        if robots:
            return robots
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html/>")

    fetcher, _ = make_fetcher(handler, config=config)
    results = SafeFetchOrchestrator(fetcher).run(
        (
            FetchRequest("safe_source", PRICE_URL),
            FetchRequest("safe_source", PRICE_URL),
        )
    )

    assert results[0].outcome is not None
    assert results[1].error is not None
    assert results[1].error.code == "PAGE_LIMIT_EXCEEDED"


def test_user_agent_builder_requires_contact_information():
    assert (
        build_user_agent("MedPriceBot", "0.1.0", "mailto:ops@example.com")
        == "MedPriceBot/0.1.0 (+mailto:ops@example.com)"
    )
    with pytest.raises(ValueError):
        build_user_agent("MedPriceBot", "0.1.0", "")
