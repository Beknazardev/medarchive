from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import threading
from typing import Callable
from urllib.robotparser import RobotFileParser

from app.ingestion.contracts import SourceConfig


@dataclass(frozen=True)
class RobotsResponse:
    url: str
    status_code: int
    content_type: str
    body: bytes


@dataclass(frozen=True)
class RobotsDecision:
    source_id: str
    target_url: str
    robots_url: str
    allowed: bool
    checked_at: datetime
    evidence_urls: tuple[str, ...]


@dataclass(frozen=True)
class _CachedPolicy:
    parser: RobotFileParser
    checked_at: datetime
    expires_at: datetime
    robots_url: str


class RobotsPolicyError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RobotsPolicyCache:
    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(hours=24),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._ttl = ttl
        self._now = now
        self._cache: dict[tuple[str, str], _CachedPolicy] = {}
        self._lock = threading.Lock()

    def check(
        self,
        config: SourceConfig,
        target_url: str,
        *,
        user_agent: str,
        loader: Callable[[str], RobotsResponse],
    ) -> RobotsDecision:
        robots_url = config.policy.robots_url
        if not robots_url:
            raise RobotsPolicyError(
                "ROBOTS_UNAVAILABLE",
                f"{config.source_id} has no approved robots.txt URL",
            )

        cache_key = (config.source_id, robots_url)
        now = self._now()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is None or cached.expires_at <= now:
                cached = self._load_policy(config, robots_url, loader, now)
                self._cache[cache_key] = cached

        allowed = cached.parser.can_fetch(user_agent, target_url)
        return RobotsDecision(
            source_id=config.source_id,
            target_url=target_url,
            robots_url=robots_url,
            allowed=allowed,
            checked_at=cached.checked_at,
            evidence_urls=tuple(
                dict.fromkeys((*config.policy.evidence_urls, cached.robots_url))
            ),
        )

    def _load_policy(
        self,
        config: SourceConfig,
        robots_url: str,
        loader: Callable[[str], RobotsResponse],
        checked_at: datetime,
    ) -> _CachedPolicy:
        try:
            response = loader(robots_url)
        except Exception as exc:
            raise RobotsPolicyError(
                "ROBOTS_UNAVAILABLE",
                f"Could not evaluate robots.txt for {config.source_id}: {exc}",
            ) from exc

        media_type = response.content_type.partition(";")[0].strip().lower()
        if response.status_code != 200 or media_type not in {
            "text/plain",
            "text/robots",
        }:
            raise RobotsPolicyError(
                "ROBOTS_UNAVAILABLE",
                (
                    f"robots.txt for {config.source_id} returned "
                    f"{response.status_code} {media_type or 'unknown content type'}"
                ),
            )

        parser = RobotFileParser()
        parser.set_url(response.url)
        parser.parse(response.body.decode("utf-8", errors="replace").splitlines())
        return _CachedPolicy(
            parser=parser,
            checked_at=checked_at,
            expires_at=checked_at + self._ttl,
            robots_url=response.url,
        )
