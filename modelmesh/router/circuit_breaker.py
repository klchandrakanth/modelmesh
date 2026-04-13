"""Simple async circuit breaker for provider calls.

States:
  CLOSED   — normal operation, calls pass through
  OPEN     — too many failures; calls are rejected immediately
  HALF_OPEN — recovery window; next call is a probe; success → CLOSED, failure → OPEN

Usage:
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
    try:
        result = await breaker.call(provider.chat(request))
    except RuntimeError:
        # circuit is open — skip this provider
        ...
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Coroutine, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        name: str = "unknown",
    ):
        self.name = name
        self._threshold = failure_threshold
        self._timeout = recovery_timeout
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._opened_at is not None and time.monotonic() - self._opened_at >= self._timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def failure_count(self) -> int:
        return self._failures

    def _on_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def _on_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    async def call(self, coro: Coroutine) -> T:
        if self.is_open:
            elapsed = time.monotonic() - (self._opened_at or 0)
            remaining = max(0.0, self._timeout - elapsed)
            raise RuntimeError(
                f"Circuit breaker '{self.name}' is OPEN "
                f"(resets in {remaining:.0f}s)"
            )
        try:
            result = await coro
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise
