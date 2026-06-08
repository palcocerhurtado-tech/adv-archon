"""Tests for integrations/resilient.py — cache, circuit breaker, resilient_call."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from adv_archon.integrations.resilient import (
    _CLOSED,
    _HALF_OPEN,
    _OPEN,
    CircuitBreaker,
    PersistentAPICache,
    init_cache,
    resilient_call,
)

# ── PersistentAPICache ────────────────────────────────────────────────────────


def test_cache_set_and_get(tmp_path: Path) -> None:
    cache = PersistentAPICache(tmp_path / "cache.db")
    key = cache.make_key("ep", {"q": 1})
    cache.set(key, "ep", {"answer": 42})
    result = cache.get(key)
    assert result == {"answer": 42}


def test_cache_miss_returns_none(tmp_path: Path) -> None:
    cache = PersistentAPICache(tmp_path / "cache.db")
    assert cache.get("nonexistent_key") is None


def test_cache_expired_returns_none(tmp_path: Path) -> None:
    cache = PersistentAPICache(tmp_path / "cache.db")
    key = cache.make_key("ep", "x")
    cache.set(key, "ep", {"v": 1}, ttl_days=-1.0)  # already expired
    assert cache.get(key) is None


def test_cache_purge_expired(tmp_path: Path) -> None:
    cache = PersistentAPICache(tmp_path / "cache.db")
    k1 = cache.make_key("ep", "a")
    k2 = cache.make_key("ep", "b")
    cache.set(k1, "ep", {"x": 1}, ttl_days=-1.0)
    cache.set(k2, "ep", {"x": 2}, ttl_days=1.0)
    removed = cache.purge_expired()
    assert removed == 1
    assert cache.get(k2) == {"x": 2}


def test_cache_make_key_is_deterministic() -> None:
    k1 = PersistentAPICache.make_key("ep", {"a": 1, "b": 2})
    k2 = PersistentAPICache.make_key("ep", {"b": 2, "a": 1})
    assert k1 == k2


# ── CircuitBreaker ────────────────────────────────────────────────────────────


def test_circuit_starts_closed() -> None:
    cb = CircuitBreaker(name="test")
    assert cb.state == _CLOSED
    assert not cb.is_open()


def test_circuit_opens_after_threshold() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=2)
    cb.record_failure()
    assert cb.state == _CLOSED
    cb.record_failure()
    assert cb.state == _OPEN
    assert cb.is_open()


def test_circuit_resets_to_closed_on_success() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=2)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == _OPEN
    cb.record_success()
    assert cb.state == _CLOSED
    assert not cb.is_open()


def test_circuit_transitions_to_half_open_after_timeout() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=1, reset_timeout_seconds=0.01)
    cb.record_failure()
    assert cb.state == _OPEN
    time.sleep(0.02)
    assert not cb.is_open()
    assert cb.state == _HALF_OPEN


def test_circuit_half_open_failure_reopens() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=1, reset_timeout_seconds=0.01)
    cb.record_failure()
    time.sleep(0.02)
    cb.is_open()  # transition to half-open
    cb.record_failure()
    assert cb.state == _OPEN


def test_circuit_thread_safety() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=10)
    errors: list[Exception] = []

    def _worker() -> None:
        try:
            for _ in range(5):
                cb.record_failure()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors


# ── resilient_call ────────────────────────────────────────────────────────────


def test_resilient_call_returns_live_result() -> None:
    result = resilient_call("test_ep", lambda: {"ok": True})
    assert result.ok
    assert result.data == {"ok": True}
    assert result.source == "live"


def test_resilient_call_returns_default_on_failure() -> None:
    def _fail() -> None:
        raise RuntimeError("boom")

    result = resilient_call("test_fail", _fail, default={"fallback": True})
    assert not result.ok
    assert result.degraded
    assert result.data == {"fallback": True}
    assert "boom" in result.error


def test_resilient_call_uses_cache(tmp_path: Path) -> None:
    import adv_archon.integrations.resilient as _mod

    original = _mod._cache
    try:
        init_cache(tmp_path / "rc_test.db")
        call_count = {"n": 0}

        def _fn() -> dict:
            call_count["n"] += 1
            return {"result": 1}

        params = {"q": "test_rc"}
        r1 = resilient_call("ep_cache", _fn, cache_params=params)
        r2 = resilient_call("ep_cache", _fn, cache_params=params)
        assert r1.data == r2.data == {"result": 1}
        assert call_count["n"] == 1
        assert r2.source == "cache"
    finally:
        _mod._cache = original


def test_resilient_call_circuit_open_returns_degraded() -> None:
    import adv_archon.integrations.resilient as _mod

    original = _mod._breakers.copy()
    try:
        cb = CircuitBreaker(name="ep_open", failure_threshold=1)
        cb.record_failure()
        _mod._breakers["ep_open"] = cb

        result = resilient_call("ep_open", lambda: {"x": 1}, default={"x": 0})
        assert not result.ok
        assert result.degraded
        assert result.source == "circuit_open"
    finally:
        _mod._breakers = original
