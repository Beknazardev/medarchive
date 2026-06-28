from __future__ import annotations

import hashlib
import ipaddress
import random
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Protocol
from urllib.parse import unquote, urljoin, urlparse

import httpx

from app.ingestion.contracts import ParserStage, SourceConfig, SourceDocument, SourceFormat
from app.ingestion.rate_limit import HostRateLimiter
from app.ingestion.registry import (
    SourceExecutionBlockedError,
    SourceRegistry,
)
from app.ingestion.robots import (
    RobotsPolicyCache,
    RobotsPolicyError,
    RobotsResponse,
)
from app.ingestion.storage import RawDocumentStorage, RawStorageError
from app.models import DataSource, ParserRun
from app.services.parser_audit_service import ParserAuditService


SAFE_TRANSIENT_STATUSES = frozenset({408, 425, 500, 502, 503, 504})
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
METADATA_SERVICE_ADDRESSES = frozenset(
    {
        "169.254.169.254",
        "100.100.100.200",
        "168.63.129.16",
        "fd00:ec2::254",
    }
)
AUDIT_HEADER_NAMES = frozenset(
    {
        "cache-control",
        "content-length",
        "content-type",
        "etag",
        "last-modified",
    }
)


class DNSResolver(Protocol):
    def resolve(self, host: str) -> tuple[str, ...]: ...


class FetchProtocol(Protocol):
    def fetch(
        self,
        source_id: str,
        url: str,
        *,
        conditional: ConditionalRequest | None = None,
        data_source: DataSource | None = None,
        parser_run: ParserRun | None = None,
    ) -> FetchOutcome: ...


class SocketDNSResolver:
    def resolve(self, host: str) -> tuple[str, ...]:
        records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return tuple(dict.fromkeys(record[4][0] for record in records))


@dataclass(frozen=True)
class FetchLimits:
    timeout_seconds: float = 15
    max_redirects: int = 3
    max_retries: int = 2
    retry_base_seconds: float = 0.5
    retry_jitter_seconds: float = 0.25
    robots_max_bytes: int = 512_000


@dataclass(frozen=True)
class ConditionalRequest:
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True)
class FetchOutcome:
    document: SourceDocument | None
    not_modified: bool
    etag: str | None
    last_modified: str | None
    attempts: int


@dataclass(frozen=True)
class FetchRequest:
    source_id: str
    url: str
    conditional: ConditionalRequest | None = None
    data_source: DataSource | None = None
    parser_run: ParserRun | None = None


@dataclass(frozen=True)
class FetchTaskResult:
    source_id: str
    url: str
    outcome: FetchOutcome | None = None
    error: FetchFailure | None = None


@dataclass(frozen=True)
class _HttpPayload:
    url: str
    status_code: int
    headers: httpx.Headers
    body: bytes


class FetchFailure(RuntimeError):
    def __init__(
        self,
        *,
        stage: ParserStage,
        code: str,
        reason: str,
        url: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(reason)
        self.stage = stage
        self.code = code
        self.reason = reason
        self.url = url
        self.retryable = retryable


class DestinationGuard:
    def __init__(self, resolver: DNSResolver) -> None:
        self._resolver = resolver

    def validate(
        self,
        config: SourceConfig,
        url: str,
        *,
        policy_request: bool = False,
    ) -> None:
        parsed = urlparse(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise self._failure("INVALID_URL", "URL must be absolute HTTP(S) without credentials", url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise self._failure("INVALID_URL", f"Invalid URL port: {exc}", url) from exc
        if port not in {None, 80, 443}:
            raise self._failure("PORT_NOT_ALLOWED", "Only standard HTTP(S) ports are allowed", url)
        if parsed.query or parsed.fragment:
            raise self._failure("URL_COMPONENT_NOT_ALLOWED", "Query strings and fragments are blocked", url)

        host = parsed.hostname.lower().rstrip(".")
        if host not in config.allowed_hosts:
            raise self._failure("HOST_NOT_ALLOWED", f"Host {host} is not allowlisted", url)

        raw_path = parsed.path or "/"
        decoded_path = unquote(raw_path)
        if "\\" in decoded_path or any(segment in {".", ".."} for segment in decoded_path.split("/")):
            raise self._failure("INVALID_PATH", "Path traversal syntax is blocked", url)

        if not policy_request:
            if not _path_matches(raw_path, config.allowed_path_prefixes):
                raise self._failure("PATH_NOT_ALLOWED", "Path is outside the source allowlist", url)
            if _path_matches(raw_path, config.forbidden_path_prefixes):
                raise self._failure("FORBIDDEN_PATH", "Path matches the source denylist", url)
        elif raw_path != "/robots.txt":
            approved_robots = urlparse(config.policy.robots_url or "").path
            if raw_path != approved_robots:
                raise self._failure("POLICY_URL_NOT_ALLOWED", "Unapproved robots URL", url)

        try:
            addresses = self._resolver.resolve(host)
        except Exception as exc:
            raise self._failure(
                "DNS_RESOLUTION_FAILED",
                f"DNS resolution failed for {host}: {exc}",
                url,
            ) from exc
        if not addresses:
            raise self._failure("DNS_RESOLUTION_FAILED", f"DNS returned no addresses for {host}", url)
        for address in addresses:
            if not _is_public_address(address):
                raise self._failure(
                    "SSRF_BLOCKED",
                    f"Resolved destination {address} is not public",
                    url,
                )

    @staticmethod
    def _failure(code: str, reason: str, url: str) -> FetchFailure:
        return FetchFailure(
            stage=ParserStage.POLICY,
            code=code,
            reason=reason,
            url=url,
            retryable=False,
        )


class SafeHttpFetcher:
    def __init__(
        self,
        *,
        registry: SourceRegistry,
        client: httpx.Client,
        user_agent: str,
        storage: RawDocumentStorage,
        resolver: DNSResolver | None = None,
        robots: RobotsPolicyCache | None = None,
        rate_limiter: HostRateLimiter | None = None,
        limits: FetchLimits | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        audit_service: ParserAuditService | None = None,
    ) -> None:
        if not user_agent.strip() or (
            "mailto:" not in user_agent.lower() and "https://" not in user_agent.lower()
        ):
            raise ValueError("user_agent must identify MedPrice and include contact information")
        self.registry = registry
        self.client = client
        self.user_agent = user_agent.strip()
        self.guard = DestinationGuard(resolver or SocketDNSResolver())
        self.robots = robots or RobotsPolicyCache()
        self.rate_limiter = rate_limiter or HostRateLimiter()
        self.limits = limits or FetchLimits()
        self.sleeper = sleeper
        self.random_value = random_value
        self.now = now
        self.storage = storage
        self.audit_service = audit_service

    def fetch(
        self,
        source_id: str,
        url: str,
        *,
        conditional: ConditionalRequest | None = None,
        data_source: DataSource | None = None,
        parser_run: ParserRun | None = None,
    ) -> FetchOutcome:
        try:
            try:
                config = self.registry.require_live(source_id)
            except (KeyError, SourceExecutionBlockedError) as exc:
                raise FetchFailure(
                    stage=ParserStage.POLICY,
                    code="SOURCE_NOT_EXECUTABLE",
                    reason=str(exc),
                    url=url,
                    retryable=False,
                ) from exc
            self.guard.validate(config, url)
            outcome = self._fetch_with_retries(config, url, conditional)
            if outcome.document is not None:
                outcome = self._store_and_audit(
                    outcome,
                    data_source=data_source,
                    parser_run=parser_run,
                )
                self._validate_document_content(config, outcome.document)
            return outcome
        except FetchFailure as failure:
            self._audit_failure(failure, parser_run)
            raise

    def _fetch_with_retries(
        self,
        config: SourceConfig,
        requested_url: str,
        conditional: ConditionalRequest | None,
    ) -> FetchOutcome:
        for attempt in range(1, self.limits.max_retries + 2):
            try:
                payload = self._fetch_target_once(config, requested_url, conditional)
                if payload.status_code == 304:
                    return FetchOutcome(
                        document=None,
                        not_modified=True,
                        etag=payload.headers.get("etag"),
                        last_modified=payload.headers.get("last-modified"),
                        attempts=attempt,
                    )
                self._validate_status(payload)
                digest = hashlib.sha256(payload.body).hexdigest()
                document = SourceDocument(
                    source_id=config.source_id,
                    requested_url=requested_url,
                    final_url=payload.url,
                    content_type=payload.headers["content-type"],
                    status_code=payload.status_code,
                    headers_subset=tuple(
                        (name.lower(), value)
                        for name, value in payload.headers.items()
                        if name.lower() in AUDIT_HEADER_NAMES
                    ),
                    content_bytes=payload.body,
                    byte_size=len(payload.body),
                    content_sha256=digest,
                    captured_at=self.now(),
                )
                return FetchOutcome(
                    document=document,
                    not_modified=False,
                    etag=payload.headers.get("etag"),
                    last_modified=payload.headers.get("last-modified"),
                    attempts=attempt,
                )
            except FetchFailure as failure:
                if not failure.retryable or attempt > self.limits.max_retries:
                    raise
                self.sleeper(self._retry_delay(attempt))
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                failure = FetchFailure(
                    stage=ParserStage.FETCH,
                    code="FETCH_TIMEOUT" if isinstance(exc, httpx.TimeoutException) else "NETWORK_ERROR",
                    reason=str(exc),
                    url=requested_url,
                    retryable=True,
                )
                if attempt > self.limits.max_retries:
                    raise failure from exc
                self.sleeper(self._retry_delay(attempt))
        raise AssertionError("retry loop exhausted unexpectedly")

    def _fetch_target_once(
        self,
        config: SourceConfig,
        requested_url: str,
        conditional: ConditionalRequest | None,
    ) -> _HttpPayload:
        current_url = requested_url
        for redirect_count in range(self.limits.max_redirects + 1):
            self.guard.validate(config, current_url)
            self._check_robots(config, current_url)
            payload = self._request_once(
                config,
                current_url,
                headers=self._request_headers(conditional),
                max_bytes=config.max_document_bytes,
            )
            if payload.status_code not in REDIRECT_STATUSES:
                return payload
            if redirect_count >= self.limits.max_redirects:
                raise FetchFailure(
                    stage=ParserStage.FETCH,
                    code="TOO_MANY_REDIRECTS",
                    reason="Redirect limit exceeded",
                    url=current_url,
                    retryable=False,
                )
            location = payload.headers.get("location")
            if not location:
                raise FetchFailure(
                    stage=ParserStage.FETCH,
                    code="INVALID_REDIRECT",
                    reason="Redirect response has no Location header",
                    url=current_url,
                    retryable=False,
                )
            next_url = urljoin(current_url, location)
            if urlparse(current_url).scheme == "https" and urlparse(next_url).scheme != "https":
                raise FetchFailure(
                    stage=ParserStage.POLICY,
                    code="HTTPS_DOWNGRADE_BLOCKED",
                    reason="HTTPS redirects may not downgrade to HTTP",
                    url=next_url,
                    retryable=False,
                )
            self.guard.validate(config, next_url)
            current_url = next_url
        raise AssertionError("redirect loop exhausted unexpectedly")

    def _check_robots(self, config: SourceConfig, target_url: str) -> None:
        try:
            decision = self.robots.check(
                config,
                target_url,
                user_agent=self.user_agent,
                loader=lambda robots_url: self._load_robots(config, robots_url),
            )
        except RobotsPolicyError as exc:
            raise FetchFailure(
                stage=ParserStage.POLICY,
                code=exc.code,
                reason=str(exc),
                url=target_url,
                retryable=False,
            ) from exc
        if not decision.allowed:
            raise FetchFailure(
                stage=ParserStage.POLICY,
                code="ROBOTS_DISALLOWED",
                reason=f"robots.txt disallows {target_url}",
                url=target_url,
                retryable=False,
            )

    def _load_robots(self, config: SourceConfig, robots_url: str) -> RobotsResponse:
        current_url = robots_url
        for redirect_count in range(self.limits.max_redirects + 1):
            self.guard.validate(config, current_url, policy_request=True)
            payload = self._request_once(
                config,
                current_url,
                headers=self._request_headers(),
                max_bytes=self.limits.robots_max_bytes,
            )
            if payload.status_code not in REDIRECT_STATUSES:
                return RobotsResponse(
                    url=payload.url,
                    status_code=payload.status_code,
                    content_type=payload.headers.get("content-type", ""),
                    body=payload.body,
                )
            if redirect_count >= self.limits.max_redirects:
                raise RuntimeError("robots.txt redirect limit exceeded")
            location = payload.headers.get("location")
            if not location:
                raise RuntimeError("robots.txt redirect has no Location header")
            current_url = urljoin(current_url, location)
        raise AssertionError("robots redirect loop exhausted unexpectedly")

    def _request_once(
        self,
        config: SourceConfig,
        url: str,
        *,
        headers: dict[str, str],
        max_bytes: int,
    ) -> _HttpPayload:
        host = urlparse(url).hostname or ""
        with self.rate_limiter.slot(
            host,
            minimum_delay_seconds=float(config.minimum_delay_seconds),
            max_concurrency=config.max_concurrency,
        ):
            with self.client.stream(
                "GET",
                url,
                headers=headers,
                timeout=self.limits.timeout_seconds,
                follow_redirects=False,
            ) as response:
                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise FetchFailure(
                        stage=ParserStage.FETCH,
                        code="RESPONSE_TOO_LARGE",
                        reason=f"Content-Length exceeds {max_bytes} bytes",
                        url=url,
                        retryable=False,
                    )
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise FetchFailure(
                            stage=ParserStage.FETCH,
                            code="RESPONSE_TOO_LARGE",
                            reason=f"Response exceeds {max_bytes} bytes",
                            url=url,
                            retryable=False,
                        )
                return _HttpPayload(
                    url=str(response.url),
                    status_code=response.status_code,
                    headers=response.headers,
                    body=bytes(body),
                )

    def _validate_status(self, payload: _HttpPayload) -> None:
        if payload.status_code in SAFE_TRANSIENT_STATUSES:
            raise FetchFailure(
                stage=ParserStage.FETCH,
                code="TRANSIENT_HTTP_STATUS",
                reason=f"Transient HTTP status {payload.status_code}",
                url=payload.url,
                retryable=True,
            )
        if payload.status_code in {401, 403, 407, 429}:
            raise FetchFailure(
                stage=ParserStage.FETCH,
                code="AUTH_OR_BOT_BLOCKED",
                reason=f"HTTP status {payload.status_code} is not retryable",
                url=payload.url,
                retryable=False,
            )
        if not 200 <= payload.status_code < 300:
            raise FetchFailure(
                stage=ParserStage.FETCH,
                code="HTTP_ERROR",
                reason=f"Unexpected HTTP status {payload.status_code}",
                url=payload.url,
                retryable=False,
            )

    def _validate_document_content(
        self,
        config: SourceConfig,
        document: SourceDocument,
    ) -> None:
        media_type = document.content_type.partition(";")[0].strip().lower()
        if not _content_type_allowed(media_type, config.formats):
            raise FetchFailure(
                stage=ParserStage.VALIDATE,
                code="UNEXPECTED_CONTENT_TYPE",
                reason=f"Content type {media_type or 'missing'} is not allowed",
                url=document.final_url,
                retryable=False,
            )
        if media_type in {"text/html", "application/xhtml+xml"}:
            sample = (document.content_bytes or b"")[:128_000].lower()
            if b"captcha" in sample or b"cf-chl-" in sample:
                raise FetchFailure(
                    stage=ParserStage.POLICY,
                    code="CAPTCHA_DETECTED",
                    reason="CAPTCHA or challenge page detected",
                    url=document.final_url,
                    retryable=False,
                )

    def _store_and_audit(
        self,
        outcome: FetchOutcome,
        *,
        data_source: DataSource | None,
        parser_run: ParserRun | None,
    ) -> FetchOutcome:
        document = outcome.document
        if document is None:
            return outcome
        try:
            document = self.storage.store(document)
            if self.audit_service is not None and data_source is not None:
                self.audit_service.save_source_document(
                    data_source=data_source,
                    document=document,
                    parser_run=parser_run,
                )
        except (RawStorageError, OSError) as exc:
            raise FetchFailure(
                stage=ParserStage.STORAGE,
                code="RAW_STORAGE_FAILED",
                reason=str(exc),
                url=document.final_url,
                retryable=False,
            ) from exc
        return FetchOutcome(
            document=document,
            not_modified=outcome.not_modified,
            etag=outcome.etag,
            last_modified=outcome.last_modified,
            attempts=outcome.attempts,
        )

    def _audit_failure(self, failure: FetchFailure, parser_run: ParserRun | None) -> None:
        if self.audit_service is None or parser_run is None:
            return
        self.audit_service.save_stage_error(
            parser_run=parser_run,
            stage=failure.stage,
            code=failure.code,
            message=failure.reason,
            retryable=failure.retryable,
            source_url=failure.url,
        )

    def _request_headers(
        self,
        conditional: ConditionalRequest | None = None,
    ) -> dict[str, str]:
        headers = {
            "accept": "*/*",
            "user-agent": self.user_agent,
        }
        if conditional:
            if conditional.etag:
                headers["if-none-match"] = conditional.etag
            if conditional.last_modified:
                headers["if-modified-since"] = conditional.last_modified
        return headers

    def _retry_delay(self, attempt: int) -> float:
        exponential = self.limits.retry_base_seconds * (2 ** (attempt - 1))
        jitter = self.limits.retry_jitter_seconds * self.random_value()
        return exponential + jitter


class SafeFetchOrchestrator:
    """Runs bounded fetch tasks while isolating failures between sources."""

    def __init__(self, fetcher: SafeHttpFetcher) -> None:
        self.fetcher = fetcher

    def run(self, requests: tuple[FetchRequest, ...]) -> tuple[FetchTaskResult, ...]:
        results: list[FetchTaskResult] = []
        page_counts: dict[str, int] = {}
        for request in requests:
            page_counts[request.source_id] = page_counts.get(request.source_id, 0) + 1
            try:
                config = self.fetcher.registry.get(request.source_id)
                if page_counts[request.source_id] > config.max_pages_per_run:
                    raise FetchFailure(
                        stage=ParserStage.POLICY,
                        code="PAGE_LIMIT_EXCEEDED",
                        reason=f"Page cap exceeded for {request.source_id}",
                        url=request.url,
                        retryable=False,
                    )
                outcome = self.fetcher.fetch(
                    request.source_id,
                    request.url,
                    conditional=request.conditional,
                    data_source=request.data_source,
                    parser_run=request.parser_run,
                )
                results.append(
                    FetchTaskResult(
                        source_id=request.source_id,
                        url=request.url,
                        outcome=outcome,
                    )
                )
            except FetchFailure as failure:
                results.append(
                    FetchTaskResult(
                        source_id=request.source_id,
                        url=request.url,
                        error=failure,
                    )
                )
            except Exception as exc:
                failure = FetchFailure(
                    stage=ParserStage.FETCH,
                    code="UNEXPECTED_FETCH_ERROR",
                    reason=str(exc),
                    url=request.url,
                    retryable=False,
                )
                self.fetcher._audit_failure(failure, request.parser_run)
                results.append(
                    FetchTaskResult(
                        source_id=request.source_id,
                        url=request.url,
                        error=failure,
                    )
                )
        return tuple(results)


def build_user_agent(name: str, version: str, contact: str) -> str:
    cleaned_name = name.strip()
    cleaned_version = version.strip()
    cleaned_contact = contact.strip()
    if not cleaned_name or not cleaned_version:
        raise ValueError("user-agent name and version are required")
    if not (
        cleaned_contact.startswith("mailto:")
        or cleaned_contact.startswith("https://")
    ):
        raise ValueError("PARSER_CONTACT must be a mailto: or HTTPS contact")
    return f"{cleaned_name}/{cleaned_version} (+{cleaned_contact})"


def _is_public_address(value: str) -> bool:
    normalized = value.split("%", 1)[0]
    if normalized.lower() in METADATA_SERVICE_ADDRESSES:
        return False
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return address.is_global


def _path_matches(path: str, prefixes: tuple[str, ...]) -> bool:
    decoded_path = unquote(path)
    return any(
        _single_path_match(path, prefix)
        or _single_path_match(decoded_path, unquote(prefix))
        for prefix in prefixes
    )


def _single_path_match(path: str, prefix: str) -> bool:
    return prefix == "/" or path == prefix or path.startswith(f"{prefix}/")


def _content_type_allowed(
    media_type: str,
    formats: tuple[SourceFormat, ...],
) -> bool:
    allowed: set[str] = set()
    for source_format in formats:
        allowed.update(
            {
                SourceFormat.HTML: {"text/html", "application/xhtml+xml"},
                SourceFormat.PDF: {"application/pdf"},
                SourceFormat.DOCX: {
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                },
                SourceFormat.XLS: {
                    "application/vnd.ms-excel",
                    "application/octet-stream",
                },
                SourceFormat.XLSX: {
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                },
                SourceFormat.JSON: {"application/json"},
                SourceFormat.API: {"application/json"},
            }[source_format]
        )
    return media_type in allowed or (
        media_type.startswith("application/") and media_type.endswith("+json")
        and any(item in formats for item in (SourceFormat.JSON, SourceFormat.API))
    )
