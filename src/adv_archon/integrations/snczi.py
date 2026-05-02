"""
SNCZI — Sistema Nacional de Cartografía de Zonas Inundables (MITECO).

Free, official Spanish government flood-zone data. No API key required.
Service: https://servicios.idee.es (CNIG INSPIRE WFS)

Returns flood zone presence for a coordinate point using the T10, T100 and
T500 return-period layers. T500 is the most commonly required in urban
planning compliance checks.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

# INSPIRE WFS published by CNIG (Centro Nacional de Información Geográfica)
# Zona Inundable layers: SNCZI_T10, SNCZI_T100, SNCZI_T500
_WFS_BASE = (
    "https://servicios.idee.es/wfs-inspire/riesgos-naturales"
)
_TIMEOUT = 12.0
_UA = "adv-archon-urban-compliance/1.0"

_PERIODS = {
    "T10":  "SNCZI_Zona_Inundable_T10",
    "T100": "SNCZI_Zona_Inundable_T100",
    "T500": "SNCZI_Zona_Inundable_T500",
}


def query_flood_zone(lat: float, lon: float) -> dict[str, Any]:
    """
    Check whether (lat, lon) falls inside a SNCZI flood zone.

    Returns::

        {
          "in_flood_zone": bool,
          "periods": ["T100", "T500"],   # which return periods include this point
          "source": "SNCZI/CNIG",
          "error": ""                    # non-empty if service unavailable
        }
    """
    result: dict[str, Any] = {
        "in_flood_zone": False,
        "periods": [],
        "source": "SNCZI/CNIG",
        "error": "",
    }
    matched: list[str] = []
    errors: list[str] = []

    for period, typename in _PERIODS.items():
        try:
            hit = _query_layer(typename, lat=lat, lon=lon)
            if hit:
                matched.append(period)
        except Exception as exc:
            errors.append(f"{period}: {exc}")

    if errors and not matched and len(errors) == len(_PERIODS):
        result["error"] = "; ".join(errors[:2])
        return result

    result["in_flood_zone"] = bool(matched)
    result["periods"] = matched
    if errors:
        log.debug("SNCZI partial errors: %s", errors)
    return result


def _query_layer(typename: str, *, lat: float, lon: float) -> bool:
    """Return True if the WFS layer contains a feature at this point."""
    # Small bounding box (~5m) around the point to do an INTERSECTS query.
    delta = 0.00005
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
