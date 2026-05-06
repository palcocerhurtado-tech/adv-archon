from __future__ import annotations

from adv_archon.core.ttl_cache import TTLCache


def test_ttl_cache_returns_copy_and_expires() -> None:
    now = {"value": 100.0}
    cache = TTLCache(ttl_seconds=10.0, clock=lambda: now["value"])

    original = {"items": ["a"]}
    cache.set("key", original)
    original["items"].append("mutated")

    cached = cache.get("key")
    assert cached == {"items": ["a"]}
    cached["items"].append("local-change")

    assert cache.get("key") == {"items": ["a"]}

    now["value"] = 111.0
    assert cache.get("key") is None
