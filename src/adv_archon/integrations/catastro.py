"""
Catastro de España (OVC) API — official, completely free, no API key.
Docs: https://ovc.catastro.meh.es/ovcservweb/OVCSWlocalizacionRC/OVCCoordenadas.asmx
      https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx
"""
from __future__ import annotations

import re
from contextlib import suppress
from typing import Any

import httpx

from adv_archon.core.ttl_cache import TTLCache

_BASE = "https://ovc.catastro.meh.es/ovcservweb/OVCSWlocalizacionRC/OVCCoordenadas.asmx"
_BASE_RC = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx"
_TIMEOUT = 10
_USER_AGENT = "adv-archon-urban-compliance/1.0"
_CACHE = TTLCache(ttl_seconds=3600.0)


def get_cadastral_data(lat: float, lon: float) -> dict[str, Any]:
    """
    Query Catastro OVC with EPSG:4326 coordinates.
    Returns dict with keys: cadastral_ref, address, use, error.
    """
    key = ("rccoor", round(lat, 7), round(lon, 7), id(httpx.get))
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached

    url = f"{_BASE}/Consulta_RCCOOR"
    try:
        resp = httpx.get(
            url,
            params={
                "SRS": "EPSG:4326",
                "Coordenada_X": str(lon),   # Catastro uses X=longitude
                "Coordenada_Y": str(lat),
            },
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/xml, text/xml",
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        result = _parse_xml(resp.text)
    except Exception as exc:
        result = {"error": str(exc)[:200], "raw_xml": ""}
    _CACHE.set(key, result)
    return result


def get_parcel_by_ref(ref_cat: str) -> dict[str, Any]:
    """
    Fetch full parcel detail from Catastro by cadastral reference.

    Uses Consulta_DNPRC (Datos No Protegidos by RC) — free, no auth needed.
    Returns::

        {
          "ref": "7537903VK4873N0001OU",
          "surface_m2": 120,
          "construction_year": 1978,
          "use_detail": "Residencial",
          "floors_above": 4,
          "floors_below": 1,
          "address": "CL MAYOR 3 ES:1 PT:2",
          "municipality": "Madrid",
          "error": ""
        }
    """
    ref_cat = ref_cat.strip().upper()
    result: dict[str, Any] = {
        "ref": ref_cat,
        "surface_m2": None,
        "construction_year": None,
        "use_detail": "",
        "floors_above": None,
        "floors_below": None,
        "address": "",
        "municipality": "",
        "error": "",
    }
    if not ref_cat:
        result["error"] = "Referencia catastral vacía"
        return result
    key = ("dnprc", ref_cat, id(httpx.get))
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    try:
        resp = httpx.get(
            f"{_BASE_RC}/Consulta_DNPRC",
            params={"RC": ref_cat},
            headers={"User-Agent": _USER_AGENT, "Accept": "application/xml, text/xml"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        result = _parse_parcel_xml(resp.text, result)
    except Exception as exc:
        result["error"] = str(exc)[:200]
    _CACHE.set(key, result)
    return result


def get_coordinates_by_ref(
    ref_cat: str,
    *,
    province: str = "",
    municipality: str = "",
) -> dict[str, Any]:
    """
    Geocode a cadastral reference using Catastro OVC Consulta_CPMRC.

    Returns EPSG:4326 coordinates when Catastro publishes a centroid for the
    reference. This is enough to continue the same sectorial screening flow used
    for manually entered coordinates.
    """
    ref_cat = ref_cat.strip().upper()
    result: dict[str, Any] = {
        "cadastral_ref": ref_cat,
        "latitude": None,
        "longitude": None,
        "address": "",
        "municipality": "",
        "province": "",
        "error": "",
    }
    if not ref_cat:
        result["error"] = "Referencia catastral vacía"
        return result
    key = ("cpmrc", ref_cat, province.strip().upper(), municipality.strip().upper(), id(httpx.get))
    cached = _CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    try:
        resp = httpx.get(
            f"{_BASE}/Consulta_CPMRC",
            params={
                "RC": ref_cat,
                "SRS": "EPSG:4326",
                "Provincia": province,
                "Municipio": municipality,
            },
            headers={"User-Agent": _USER_AGENT, "Accept": "application/xml, text/xml"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        result = _parse_coordinates_by_ref_xml(resp.text, result)
    except Exception as exc:
        result["error"] = str(exc)[:200]
    _CACHE.set(key, result)
    return result


def clear_cache() -> None:
    _CACHE.clear()


def _parse_coordinates_by_ref_xml(xml: str, base: dict[str, Any]) -> dict[str, Any]:
    """Parse Consulta_CPMRC XML response."""
    err = re.search(r"<lerr>.*?<cod>(.*?)</cod>.*?<des>(.*?)</des>", xml, re.DOTALL)
    if err:
        base["error"] = err.group(2).strip() or f"Catastro error {err.group(1).strip()}"
        return base

    def _first(pattern: str) -> str:
        m = re.search(pattern, xml, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    xcoord = _first(r"<xcen>(.*?)</xcen>")
    ycoord = _first(r"<ycen>(.*?)</ycen>")
    if xcoord and ycoord:
        try:
            base["longitude"] = float(xcoord)
            base["latitude"] = float(ycoord)
        except ValueError:
            base["error"] = "Catastro devolvió coordenadas no numéricas"
            return base

    pc1 = _first(r"<pc1>(.*?)</pc1>")
    pc2 = _first(r"<pc2>(.*?)</pc2>")
    if pc1 or pc2:
        base["cadastral_ref"] = f"{pc1}{pc2}".strip()

    base["address"] = _first(r"<ldt>(.*?)</ldt>")
    base["municipality"] = _first(r"<lmun>(.*?)</lmun>")
    base["province"] = _first(r"<lprov>(.*?)</lprov>")
    if base["latitude"] is None or base["longitude"] is None:
        base["error"] = "Catastro no devolvió coordenadas para la referencia catastral"
    return base


def _parse_parcel_xml(xml: str, base: dict[str, Any]) -> dict[str, Any]:
    """Parse Consulta_DNPRC response XML."""
    err = re.search(r"<cod>(\d+)</cod>", xml)
    if err and err.group(1) != "0":
        desc = re.search(r"<des>(.*?)</des>", xml, re.DOTALL)
        base["error"] = desc.group(1).strip() if desc else f"Catastro error {err.group(1)}"
        return base

    def _first(pattern: str) -> str:
        m = re.search(pattern, xml, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    # Surface (sup total construida or superficie)
    sup = _first(r"<stotloc>(.*?)</stotloc>") or _first(r"<sfc>(.*?)</sfc>")
    if sup:
        with suppress(ValueError):
            base["surface_m2"] = int(float(sup))

    # Year of construction
    anyo = _first(r"<ant>(.*?)</ant>") or _first(r"<cpt>(.*?)</cpt>")
    if anyo and anyo.isdigit():
        base["construction_year"] = int(anyo)

    # Use
    uso = _first(r"<luso>(.*?)</luso>") or _first(r"<cn>(.*?)</cn>")
    if uso:
        base["use_detail"] = uso

    # Floors
    plt = _first(r"<plt>(.*?)</plt>")
    if plt and plt.isdigit():
        base["floors_above"] = int(plt)
    pls = _first(r"<pls>(.*?)</pls>")
    if pls and pls.isdigit():
        base["floors_below"] = int(pls)

    # Address
    ldt = _first(r"<ldt>(.*?)</ldt>")
    if ldt:
        base["address"] = ldt

    # Municipality
    lmun = _first(r"<lmun>(.*?)</lmun>")
    if lmun:
        base["municipality"] = lmun

    return base


def _parse_xml(xml: str) -> dict[str, Any]:
    """Extract cadastral reference and address from Catastro XML response."""
    result: dict[str, Any] = {"raw_xml": xml, "error": ""}

    # Catastro error code
    err_match = re.search(r"<cod>(\d+)</cod>", xml)
    if err_match and err_match.group(1) != "0":
        desc = re.search(r"<des>(.*?)</des>", xml, re.DOTALL)
        result["error"] = desc.group(1).strip() if desc else f"Error code {err_match.group(1)}"
        return result

    # Referencia catastral
    rc = re.search(r"<pc1>(.*?)</pc1>.*?<pc2>(.*?)</pc2>", xml, re.DOTALL)
    if rc:
        result["cadastral_ref"] = (rc.group(1) + rc.group(2)).strip()
    else:
        rc_direct = re.search(r"<rc>(.*?)</rc>", xml)
        result["cadastral_ref"] = rc_direct.group(1).strip() if rc_direct else ""

    # Address fields
    ldt = re.search(r"<ldt>(.*?)</ldt>", xml, re.DOTALL)
    result["address"] = ldt.group(1).strip() if ldt else ""

    # Use type (urban/rustic)
    luso = re.search(r"<luso>(.*?)</luso>", xml, re.DOTALL)
    result["use"] = luso.group(1).strip() if luso else ""

    # Municipality from Catastro
    lmun = re.search(r"<lmun>(.*?)</lmun>", xml, re.DOTALL)
    result["catastro_municipality"] = lmun.group(1).strip() if lmun else ""

    # Province
    lprov = re.search(r"<lprov>(.*?)</lprov>", xml, re.DOTALL)
    result["catastro_province"] = lprov.group(1).strip() if lprov else ""

    return result
