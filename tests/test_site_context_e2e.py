"""
End-to-end integration tests for the coordinates → parcel → flood → legal flow.

All external HTTP calls are mocked at the integration function level so these
run offline without credentials.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from adv_archon.core.geo_store import GeoStore
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.tools.geo_tools import GeoTools


# ── Shared return values ──────────────────────────────────────────────────────

_NOMINATIM_DATA = {
    "display_name": "Madrid, Comunidad de Madrid, España",
    "address": {
        "city": "Madrid",
        "state": "Comunidad de Madrid",
        "country": "España",
        "country_code": "es",
    },
    "lat": "40.4168",
    "lon": "-3.7038",
}

_CATASTRO_COORD = {
    "cadastral_ref": "7537903VK4873N0001OU",
    "address": "CL GRAN VIA 1, MADRID",
    "use": "Residencial",
    "catastro_municipality": "Madrid",
    "catastro_province": "Madrid",
    "raw_xml": "",
    "error": "",
}

_PARCEL_DETAIL = {
    "ref": "7537903VK4873N0001OU",
    "surface_m2": 245,
    "construction_year": 1965,
    "use_detail": "Residencial",
    "floors_above": 6,
    "floors_below": 1,
    "address": "CL GRAN VIA 1, MADRID",
    "municipality": "Madrid",
    "error": "",
}

_FLOOD_NONE = {
    "in_flood_zone": False,
    "periods": [],
    "source": "SNCZI/CNIG",
    "error": "",
}

_FLOOD_HIT = {
    "in_flood_zone": True,
    "periods": ["T100"],
    "source": "SNCZI/CNIG",
    "error": "",
}

_FLOOD_UNAVAILABLE = {
    "in_flood_zone": None,
    "periods": [],
    "source": "SNCZI/CNIG",
    "error": "connection timeout",
}


def _make_geo_tools(tmp_path: Path) -> GeoTools:
    return GeoTools(
        GeoStore(tmp_path / "geo.db"),
        PGOUStore(tmp_path / "pgou.db"),
    )


def _base_patches(flood_return: dict):
    """Return a list of context managers patching all three integrations."""
    return [
        patch(
            "adv_archon.integrations.nominatim.reverse_geocode",
            return_value=_NOMINATIM_DATA,
        ),
        patch(
            "adv_archon.integrations.catastro.get_cadastral_data",
            return_value=_CATASTRO_COORD,
        ),
        patch(
            "adv_archon.integrations.catastro.get_parcel_by_ref",
            return_value=_PARCEL_DETAIL,
        ),
        patch(
            "adv_archon.integrations.snczi.query_flood_zone",
            return_value=flood_return,
        ),
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_site_compliance_context_full_flow_no_flood(tmp_path: Path) -> None:
    """
    Full flow: resolve coords → Catastro parcel detail → SNCZI no flood → legal checks.
    Verifies parcel_detail and flood_zone are populated in the payload.
    """
    tools = _make_geo_tools(tmp_path)

    patches = _base_patches(_FLOOD_NONE)
    with patches[0], patches[1], patches[2], patches[3]:
        result = tools.site_compliance_context(40.4168, -3.7038)

    p = result.payload
    assert p["ok"] is True
    assert p["municipality"] == "Madrid"

    # Parcel detail from Catastro DNPRC
    pd = p["parcel_detail"]
    assert pd["surface_m2"] == 245
    assert pd["construction_year"] == 1965
    assert pd["floors_above"] == 6
    assert pd["use_detail"] == "Residencial"

    # SNCZI flood zone — queried, not flooded
    fz = p["flood_zone"]
    assert fz["queried"] is True
    assert fz["in_flood_zone"] is False
    assert fz["periods"] == []

    # Legal checks
    checks_by_code = {c["code"]: c for c in p["legal_checks"]}
    assert checks_by_code["hydraulic-domain"]["status"] == "ready"
    assert "aparece" in checks_by_code["hydraulic-domain"]["detail"].lower()
    assert checks_by_code["cadastral-identification"]["status"] == "ready"
    assert "245" in checks_by_code["cadastral-identification"]["detail"]


def test_site_compliance_context_flood_detected(tmp_path: Path) -> None:
    """When SNCZI returns features, flood check is 'conditional' with warning."""
    tools = _make_geo_tools(tmp_path)

    patches = _base_patches(_FLOOD_HIT)
    with patches[0], patches[1], patches[2], patches[3]:
        result = tools.site_compliance_context(40.4168, -3.7038)

    p = result.payload
    fz = p["flood_zone"]
    assert fz["in_flood_zone"] is True
    assert len(fz["periods"]) > 0

    checks_by_code = {c["code"]: c for c in p["legal_checks"]}
    assert checks_by_code["hydraulic-domain"]["status"] == "conditional"
    assert "⚠️" in checks_by_code["hydraulic-domain"]["detail"]


def test_site_compliance_context_snczi_unavailable(tmp_path: Path) -> None:
    """SNCZI timeout degrades to pending_review, does not crash."""
    tools = _make_geo_tools(tmp_path)

    patches = _base_patches(_FLOOD_UNAVAILABLE)
    with patches[0], patches[1], patches[2], patches[3]:
        result = tools.site_compliance_context(40.4168, -3.7038)

    p = result.payload
    fz = p["flood_zone"]
    assert fz["queried"] is True
    assert fz["in_flood_zone"] is None

    checks_by_code = {c["code"]: c for c in p["legal_checks"]}
    assert checks_by_code["hydraulic-domain"]["status"] == "pending_review"


def test_site_compliance_context_catastro_dnprc_unavailable(tmp_path: Path) -> None:
    """If DNPRC fails, parcel_detail is empty but flow continues."""
    tools = _make_geo_tools(tmp_path)

    with (
        patch(
            "adv_archon.integrations.nominatim.reverse_geocode",
            return_value=_NOMINATIM_DATA,
        ),
        patch(
            "adv_archon.integrations.catastro.get_cadastral_data",
            return_value=_CATASTRO_COORD,
        ),
        patch(
            "adv_archon.integrations.catastro.get_parcel_by_ref",
            side_effect=Exception("DNPRC unavailable"),
        ),
        patch(
            "adv_archon.integrations.snczi.query_flood_zone",
            return_value=_FLOOD_NONE,
        ),
    ):
        result = tools.site_compliance_context(40.4168, -3.7038)

    p = result.payload
    assert p["ok"] is True
    assert p["parcel_detail"] == {}   # graceful empty, not an error
    # Cadastral identification still ready (ref was obtained from coord query)
    checks_by_code = {c["code"]: c for c in p["legal_checks"]}
    assert checks_by_code["cadastral-identification"]["status"] == "ready"


def test_legal_readiness_with_pgou_indexed(tmp_path: Path) -> None:
    """When PGOU is indexed and cadastral ref found → preliminary-ready."""
    tools = _make_geo_tools(tmp_path)

    # Index a dummy municipality so pgou_indexed is True
    tools._pgou.index_text("normativa de prueba", municipality="Madrid", source="test")

    patches = _base_patches(_FLOOD_NONE)
    with patches[0], patches[1], patches[2], patches[3]:
        result = tools.site_compliance_context(40.4168, -3.7038)

    assert result.payload["pgou_indexed"] is True
    assert result.payload["legal_readiness"] == "preliminary-ready"
