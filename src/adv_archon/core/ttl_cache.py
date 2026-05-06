from __future__ import annotations

import copy
import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _CacheEntry:
    stored_at: float
    value: Any


class TTLCache:
    """Small in-memory TTL cache for short-lived official-source lookups."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._items: dict[Hashable, _CacheEntry] = {}

    def get(self, key: Hashable) -> Any | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if self._clock() - entry.stored_at > self._ttl_seconds:
            self._items.pop(key, None)
            return None
        return copy.deepcopy(entry.value)

    def set(self, key: Hashable, value: Any) -> None:
        self._items[key] = _CacheEntry(
            stored_at=self._clock(),
            value=copy.deepcopy(value),
        )

    def clear(self) -> None:
        self._items.clear()


__all__ = ["TTLCache"]
