"""
Catastro de España (OVC) API — official, completely free, no API key.
Docs: https://ovc.catastro.meh.es/ovcservweb/OVCSWlocalizacionRC/OVCCoordenadas.asmx
"""
from __future__ import annotations

import re
from typing import Any

import httpx

_BASE = "https://ovc.catastro.meh.es/ovcservweb/OVCSWlocalizacionRC/OVCCoordenadas.asmx"
_TIMEOUT = 10
_USER_AGENT = "adv-archon-urban-compliance/1.0"


def get_cadastral_data(lat: float, lon: float) -> dict[str, Any]:
    """
    Query Catastro OVC with EPSG:4326 coordinates.
    Returns dict with keys: cadastral_ref, address, use, error.
    """
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
        return _parse_xml(resp.text)
    except Exception as exc:
        return {"error": str(exc)[:200], "raw_xml": ""}


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
