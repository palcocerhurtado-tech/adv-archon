"""Nominatim (OpenStreetMap) reverse geocoding — free, no API key required."""
from __future__ import annotations

import time
from typing import Any, cast

import httpx

_BASE_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "adv-archon-urban-compliance/1.0 (contact: admin@adv-archon.com)"
_TIMEOUT = 10
_MIN_INTERVAL = 1.1   # Nominatim policy: max 1 req/s

_last_call: float = 0.0


def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    """
    Resolve (lat, lon) → address dict via Nominatim.
    Respects the 1 req/s rate limit.
    Returns the full JSON response dict, or {} on error.
    """
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    try:
        resp = httpx.get(
            _BASE_URL,
            params={
                "lat": lat,
                "lon": lon,
                "format": "jsonv2",
                "addressdetails": 1,
                "accept-language": "es",
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        _last_call = time.monotonic()
        return cast(dict[str, Any], resp.json())
    except Exception:
        return {}


def extract_municipality(data: dict[str, Any]) -> tuple[str, str, str]:
    """
    Parse Nominatim response → (municipality, province, autonomous_community).
    Returns ("", "", "") if not resolvable.
    """
    addr = data.get("address", {})

    municipality = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("municipality")
        or addr.get("county")
        or ""
    )

    province = (
        addr.get("county")
        or addr.get("state_district")
        or ""
    )

    autonomous_community = addr.get("state") or ""

    # Normalise: strip "Provincia de " prefix if present
    if province.lower().startswith("provincia de "):
        province = province[13:]

    return municipality.strip(), province.strip(), autonomous_community.strip()
