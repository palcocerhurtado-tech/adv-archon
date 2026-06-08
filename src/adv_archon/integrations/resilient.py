"""
Resilience primitives for external API integrations.

Provides:
  PersistentAPICache  — SQLite-backed cache that survives app restarts
  CircuitBreaker      — per-endpoint open/half-open/closed state machine
  resilient_call      — one-liner wrapper: cache → circuit → retry → degrade
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adv_archon.core.resilience import ResilientExecutor, RetryPolicy

log = logging.getLogger(__name__)

# ── Persistent cache ──────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key  TEXT PRIMARY KEY,
    endpoint   TEXT NOT NULL,
    data_json  TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    hit_count  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_api_cache_expires ON api_cache (expires_at);
"""


class PersistentAPICache:
    """Thread-safe SQLite cache for external API responses."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    # -- internal ------------------------------------------------------------ #

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    def _init_db(self) -> None:
        conn = self._conn()
        conn.executescript(_DDL)
        conn.commit()

    # -- public API ---------------------------------------------------------- #

    @staticmethod
    def make_key(endpoint: str, params: Any) -> str:
        raw = endpoint + "|" + json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        try:
            row = self._conn().execute(
                "SELECT data_json, expires_at FROM api_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            if time.time() > row["expires_at"]:
                self._conn().execute("DELETE FROM api_cache WHERE cache_key = ?", (key,))
                self._conn().commit()
                return None
            self._conn().execute(
                "UPDATE api_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                (key,),
            )
            self._conn().commit()
            return json.loads(row["data_json"])
        except Exception:
            return None

    def set(self, key: str, endpoint: str, data: Any, ttl_days: float = 7.0) -> None:
        try:
            now = time.time()
            self._conn().execute(
                """INSERT OR REPLACE INTO api_cache
                   (cache_key, endpoint, data_json, created_at, expires_at, hit_count)
                   VALUES (?,?,?,?,?,0)""",
                (key, endpoint, json.dumps(data, default=str), now, now + ttl_days * 86400),
            )
            self._conn().commit()
        except Exception as exc:
            log.debug("api_cache set failed: %s", exc)

    def purge_expired(self) -> int:
        try:
            cur = self._conn().execute(
                "DELETE FROM api_cache WHERE expires_at < ?", (time.time(),)
            )
            self._conn().commit()
            return cur.rowcount
        except Exception:
            return 0


# ── Circuit breaker ───────────────────────────────────────────────────────────

_CLOSED = "closed"
_OPEN = "open"
_HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """
    Per-endpoint circuit breaker.
    Opens after `failure_threshold` consecutive failures,
    tries again after `reset_timeout_seconds`.
    """

    name: str
    failure_threshold: int = 3
    reset_timeout_seconds: float = 120.0
    _state: str = field(default=_CLOSED, init=False, repr=False)
    _failures: int = field(default=0, init=False, repr=False)
    _opened_at: float = field(default=0.0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def is_open(self) -> bool:
        with self._lock:
            if self._state == _OPEN:
                if time.monotonic() - self._opened_at >= self.reset_timeout_seconds:
                    self._state = _HALF_OPEN
                    log.debug("circuit %s → half-open", self.name)
                    return False
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = _CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold or self._state == _HALF_OPEN:
                self._state = _OPEN
                self._opened_at = time.monotonic()
                log.warning("circuit %s OPENED after %d failures", self.name, self._failures)

    @property
    def state(self) -> str:
        return self._state


# ── Module-level registry (one breaker + cache per process) ──────────────────

_breakers: dict[str, CircuitBreaker] = {}
_breaker_lock = threading.Lock()
_cache: PersistentAPICache | None = None
_cache_lock = threading.Lock()


def _get_breaker(name: str) -> CircuitBreaker:
    with _breaker_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name=name)
        return _breakers[name]


def init_cache(db_path: Path) -> None:
    """Call once at app startup with the configured path."""
    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = PersistentAPICache(db_path)


def _get_cache() -> PersistentAPICache | None:
    return _cache


# ── Main helper ───────────────────────────────────────────────────────────────

@dataclass
class ResilientResult:
    data: Any
    ok: bool
    degraded: bool = False
    source: str = "live"  # "live" | "cache" | "circuit_open" | "error"
    error: str = ""


def resilient_call(
    endpoint: str,
    fn: Callable[[], Any],
    cache_params: Any = None,
    *,
    ttl_days: float = 7.0,
    default: Any = None,
) -> ResilientResult:
    """
    Execute `fn()` with:
      1. Persistent cache lookup (returns immediately on hit)
      2. Circuit breaker check (returns degraded result if open)
      3. Retry with exponential backoff (via ResilientExecutor)
      4. Graceful degradation (returns `default` on failure, never raises)

    Args:
        endpoint:     Name used for circuit breaker and cache namespacing.
        fn:           Zero-argument callable that performs the API call.
        cache_params: Hashable params used to build the cache key. If None,
                      caching is skipped for this call.
        ttl_days:     Cache TTL in days.
        default:      Value returned when the call fails (degraded mode).
    """
    cache = _get_cache()
    cache_key: str | None = None

    # 1. Cache lookup
    if cache is not None and cache_params is not None:
        cache_key = PersistentAPICache.make_key(endpoint, cache_params)
        cached = cache.get(cache_key)
        if cached is not None:
            return ResilientResult(data=cached, ok=True, source="cache")

    # 2. Circuit breaker
    breaker = _get_breaker(endpoint)
    if breaker.is_open():
        log.info("circuit open for %s — returning degraded result", endpoint)
        return ResilientResult(
            data=default, ok=False, degraded=True, source="circuit_open",
            error=f"Circuit breaker OPEN for {endpoint}",
        )

    # 3. Call with retry
    executor = ResilientExecutor(retry_policy=RetryPolicy(attempts=3, base_delay_seconds=1.0))
    try:
        result = executor.run(fn)
        breaker.record_success()
        if cache is not None and cache_key is not None:
            cache.set(cache_key, endpoint, result, ttl_days=ttl_days)
        return ResilientResult(data=result, ok=True, source="live")
    except Exception as exc:
        breaker.record_failure()
        log.warning("resilient_call %s failed: %s", endpoint, exc)
        return ResilientResult(
            data=default, ok=False, degraded=True, source="error",
            error=str(exc)[:200],
        )
