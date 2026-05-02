from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 3
    base_delay_seconds: float = 0.6
    max_delay_seconds: float = 4.0
    jitter_seconds: float = 0.15


@dataclass(frozen=True, slots=True)
class ConcurrencyPolicy:
    max_concurrency: int = 2
    min_interval_seconds: float = 0.0


def default_retryable_error(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            TimeoutError,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
            httpx.WriteTimeout,
        ),
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status in {408, 409, 425, 429, 500, 502, 503, 504}
    lowered = str(exc).lower()
    transient_markers = (
        "429",
        "deadline exceeded",
        "temporarily unavailable",
        "timed out",
        "timeout",
        "try again",
        "rate limit",
        "connection reset",
        "service unavailable",
    )
    return any(marker in lowered for marker in transient_markers)


class OperationGate:
    def __init__(self, *, policy: ConcurrencyPolicy) -> None:
        self._policy = policy
        self._semaphore = threading.BoundedSemaphore(max(1, policy.max_concurrency))
        self._lock = threading.Lock()
        self._last_started_at = 0.0

    def run(self, fn: Callable[[], _T]) -> _T:
        with self._semaphore:
            self._respect_min_interval()
            return fn()

    def _respect_min_interval(self) -> None:
        minimum = max(0.0, self._policy.min_interval_seconds)
        if minimum <= 0:
            return
        while True:
            sleep_for = 0.0
            with self._lock:
                now = time.monotonic()
                delta = now - self._last_started_at
                if delta >= minimum:
                    self._last_started_at = now
                    return
                sleep_for = minimum - delta
            if sleep_for > 0:
                time.sleep(sleep_for)


class ResilientExecutor:
    def __init__(
        self,
        *,
        retry_policy: RetryPolicy | None = None,
        concurrency_policy: ConcurrencyPolicy | None = None,
        should_retry: Callable[[Exception], bool] | None = None,
    ) -> None:
        self._retry_policy = retry_policy or RetryPolicy()
        self._gate = OperationGate(policy=concurrency_policy or ConcurrencyPolicy())
        self._should_retry = should_retry or default_retryable_error

    def run(self, fn: Callable[[], _T]) -> _T:
        attempts = max(1, self._retry_policy.attempts)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return self._gate.run(fn)
            except Exception as exc:
                last_error = exc
                if attempt >= attempts or not self._should_retry(exc):
                    raise
                time.sleep(self._backoff_seconds(attempt))
        if last_error is not None:
            raise last_error
        raise RuntimeError("Executor finished without result.")

    def _backoff_seconds(self, attempt: int) -> float:
        raw_delay = self._retry_policy.base_delay_seconds * (2 ** max(0, attempt - 1))
        bounded = min(raw_delay, self._retry_policy.max_delay_seconds)
        jitter = float(random.uniform(0.0, max(0.0, self._retry_policy.jitter_seconds)))
        return float(bounded + jitter)
