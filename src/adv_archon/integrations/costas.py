"""
Costas del Estado — SIGCOSTAS / MITECO INSPIRE WFS.

Free, official Spanish government data. No API key required.
Queries Dominio Público Marítimo-Terrestre (DPMT) and its protection
servitudes for a coordinate point.

Service docs:
  https://www.miteco.gob.es/es/costas/servicios/sigcostas.html
  https://servicios.idee.es  (CNIG INSPIRE catalogue)

Layer hierarchy (Ley de Costas 22/1988 + Reglamento):
  DPMT                  — absolute public domain, zero buildable
  Servidumbre tránsito  — 6 m strip (public passage)
  Servidumbre protección— 100 m (urban) / 20 m (non-urban), strict limits
  Zona de influencia    — 500 m, urban planning must consider coastal character
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Primary INSPIRE WFS published by MITECO / CNIG
# To verify available typenames:
#   GET https://servicios.idee.es/wfs-inspire/costas?SERVICE=WFS&REQUEST=GetCapabilities
_WFS_BASE = "https://servicios.idee.es/wfs-inspire/costas"
_TIMEOUT = 12.0
_UA = "adv-archon-urban-compliance/1.0"

# typename → (human label, zone_key stored in result)
# Order matters: from most restrictive to least
_LAYERS: dict[str, tuple[str, str]] = {
    "SIGCOSTAS_DPMT":                 ("DPMT (dominio público)",    "in_dpmt"),
    "SIGCOSTAS_ServidumbreProteccion": ("Servidumbre de protección", "in_protection_zone"),
    "SIGCOSTAS_ZonaInfluencia":        ("Zona de influencia 500 m",  "in_influence_zone"),
}


def query_coastal_zone(lat: float, lon: float) -> dict[str, Any]:
    """
    Check whether (lat, lon) falls inside a DPMT or coastal protection zone.

    Returns::

        {
          "in_dpmt":             bool | None,   # None → service unavailable
          "in_protection_zone":  bool | None,
          "in_influence_zone":   bool | None,
          "zones":               ["DPMT (dominio público)"],  # matched labels
          "source":              "SIGCOSTAS / MITECO",
          "error":               ""
        }
    """
    result: dict[str, Any] = {
        "in_dpmt": False,
        "in_protection_zone": False,
        "in_influence_zone": False,
        "zones": [],
        "source": "SIGCOSTAS / MITECO",
        "error": "",
    }
    matched: list[str] = []
    errors: list[str] = []

    for typename, (label, key) in _LAYERS.items():
        try:
            hit = _query_layer(typename, lat=lat, lon=lon)
            if hit:
                matched.append(label)
                result[key] = True
        except Exception as exc:
            errors.append(f"{typename}: {exc}")

    if errors and not matched and len(errors) == len(_LAYERS):
        # All layers failed → service unavailable, cannot determine
        for key in ("in_dpmt", "in_protection_zone", "in_influence_zone"):
            result[key] = None
        result["error"] = "; ".join(errors[:2])
        return result

    result["zones"] = matched
    if errors:
        log.debug("SIGCOSTAS partial errors: %s", errors)
    return result


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
