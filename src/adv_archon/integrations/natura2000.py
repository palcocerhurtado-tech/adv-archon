"""
Red Natura 2000 — INSPIRE WFS (CNIG / MITECO).

Free, official Spanish government data. No API key required.
Queries ZEC (Zonas de Especial Conservación) and ZEPA (Zonas de Especial
Protección para las Aves) layers for a coordinate point.

Service: https://servicios.idee.es (CNIG INSPIRE WFS)
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from adv_archon.core.ttl_cache import TTLCache

log = logging.getLogger(__name__)

_WFS_BASE = "https://servicios.idee.es/wfs-inspire/espacios-naturales"
_TIMEOUT = 12.0
_UA = "adv-archon-urban-compliance/1.0"
_CACHE = TTLCache(ttl_seconds=3600.0)

# Typename → human label for each Natura 2000 layer
_LAYERS: dict[str, str] = {
    "RN2000_ZEC":  "ZEC (hábitats)",
    "RN2000_ZEPA": "ZEPA (aves)",
}


def query_protected_area(lat: float, lon: float) -> dict[str, Any]:
    """
    Check whether (lat, lon) falls inside a Red Natura 2000 protected area.

    Returns::

        {
          "in_protected_area": bool | None,   # None → service unavailable
          "zones": ["ZEC (hábitats)"],        # matched zone labels
          "source": "Red Natura 2000 / CNIG",
          "error": ""
        }
    """
    key = ("natura2000", round(lat, 7), round(lon, 7), id(httpx.get))
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached

    result: dict[str, Any] = {
        "in_protected_area": False,
        "zones": [],
        "source": "Red Natura 2000 / CNIG",
        "error": "",
    }
    matched: list[str] = []
    errors: list[str] = []

    for typename, label in _LAYERS.items():
        try:
            if _query_layer(typename, lat=lat, lon=lon):
                matched.append(label)
        except Exception as exc:
            errors.append(f"{typename}: {exc}")

    if errors and not matched and len(errors) == len(_LAYERS):
        result["in_protected_area"] = None   # service unavailable
        result["error"] = "; ".join(errors[:2])
        _CACHE.set(key, result)
        return result

    result["in_protected_area"] = bool(matched)
    result["zones"] = matched
    if errors:
        log.debug("Natura 2000 partial errors: %s", errors)
    _CACHE.set(key, result)
    return result


def clear_cache() -> None:
    _CACHE.clear()


def _query_layer(typename: str, *, lat: float, lon: float) -> bool:
    """Return True if the WFS layer contains a feature at this point."""
    delta = 0.00005  # ~5 m bounding box
    bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta},EPSG:4326"
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": typename,
        "SRSNAME": "EPSG:4326",
        "BBOX": bbox,
        "COUNT": "1",
        "OUTPUTFORMAT": "application/json",
    }
    resp = httpx.get(
        _WFS_BASE,
        params=params,
        headers={"User-Agent": _UA, "Accept": "application/json"},
        timeout=_TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    features = data.get("features") or data.get("numberReturned", 0)
    if isinstance(features, list):
        return len(features) > 0
    return int(features) > 0
