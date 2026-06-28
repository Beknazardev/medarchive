from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator


@dataclass
class _HostState:
    semaphore: threading.BoundedSemaphore
    timing_lock: threading.Lock
    max_concurrency: int
    last_started_at: float | None = None


class HostRateLimiter:
    """Thread-safe per-host concurrency and request-start delay limiter."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._clock = clock
        self._sleeper = sleeper
        self._states: dict[str, _HostState] = {}
        self._states_lock = threading.Lock()

    @contextmanager
    def slot(
        self,
        host: str,
        *,
        minimum_delay_seconds: float,
        max_concurrency: int,
    ) -> Iterator[None]:
        state = self._state(host, max_concurrency)
        state.semaphore.acquire()
        try:
            with state.timing_lock:
                now = self._clock()
                if state.last_started_at is not None:
                    wait_seconds = minimum_delay_seconds - (now - state.last_started_at)
                    if wait_seconds > 0:
                        self._sleeper(wait_seconds)
                state.last_started_at = self._clock()
            yield
        finally:
            state.semaphore.release()

    def _state(self, host: str, max_concurrency: int) -> _HostState:
        key = host.lower()
        with self._states_lock:
            state = self._states.get(key)
            if state is None:
                state = _HostState(
                    semaphore=threading.BoundedSemaphore(max_concurrency),
                    timing_lock=threading.Lock(),
                    max_concurrency=max_concurrency,
                )
                self._states[key] = state
            elif max_concurrency < state.max_concurrency:
                raise ValueError(
                    "cannot lower concurrency for an already active host limiter"
                )
            return state
