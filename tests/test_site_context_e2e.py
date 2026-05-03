"""
End-to-end integration tests for the coordinates → parcel → flood → legal flow.

All external HTTP calls are mocked at the integration function level so these
run offline without credentials.
"""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

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

_NATURA_NONE = {
    "in_protected_area": False,
    "zones": [],
    "source": "Red Natura 2000 / CNIG",
    "error": "",
}

_COSTAS_NONE = {
    "in_dpmt": False,
    "in_protection_zone": False,
    "in_influence_zone": False,
    "zones": [],
    "source": "SIGCOSTAS / MITECO",
    "error": "",
}

_ROAD_NONE = {
    "in_domain_zone": False,
    "in_servitude_zone": False,
    "in_affection_zone": False,
    "zones": [],
    "source": "Transportes INSPIRE / CNIG",
    "method": "cribado geométrico por proximidad a eje viario oficial",
    "nearest_distance_m": None,
    "error": "",
}

_ROAD_HIT = {
    "in_domain_zone": False,
    "in_servitude_zone": True,
    "in_affection_zone": True,
    "zones": [
        "Posible zona de servidumbre viaria",
        "Posible zona de afección viaria",
    ],
    "source": "Transportes INSPIRE / CNIG",
    "method": "cribado geométrico por proximidad a eje viario oficial",
    "nearest_distance_m": 18.4,
    "error": "",
}

_ROAD_UNAVAILABLE = {
    "in_domain_zone": None,
    "in_servitude_zone": None,
    "in_affection_zone": None,
    "zones": [],
    "source": "Transportes INSPIRE / CNIG",
    "method": "cribado geométrico por proximidad a eje viario oficial",
    "nearest_distance_m": None,
    "error": "connection timeout",
}

_ZONING_TEXT = """
Artículo 4. Ordenanza residencial ZR-1.

Clasificación del suelo: Suelo urbano consolidado.
Calificación urbanística: Residencial colectiva.
Ordenanza de aplicación: ZR-1 Residencial.
Uso principal: residencial vivienda.
Edificabilidad máxima: 1,20 m2/m2.
Ocupación máxima: 40%.
Altura máxima: 7 m y 2 plantas.
Retranqueos: 3 m a linderos.
"""


def _make_geo_tools(tmp_path: Path) -> GeoTools:
    return GeoTools(
        GeoStore(tmp_path / "geo.db"),
        PGOUStore(tmp_path / "pgou.db"),
    )


def _base_patches(flood_return: dict, road_return: dict | None = None):
    """Return context managers patching external integrations at function level."""
    road_payload = road_return or _ROAD_NONE
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
        patch(
            "adv_archon.integrations.natura2000.query_protected_area",
            return_value=_NATURA_NONE,
        ),
        patch(
            "adv_archon.integrations.costas.query_coastal_zone",
            return_value=_COSTAS_NONE,
        ),
        patch(
            "adv_archon.integrations.carreteras.query_road_zone",
            return_value=road_payload,
        ),
    ]


def _run_with_patches(
    tools: GeoTools,
    flood_return: dict,
    road_return: dict | None = None,
):
    with ExitStack() as stack:
        for ctx in _base_patches(flood_return, road_return):
            stack.enter_context(ctx)
        return tools.site_compliance_context(40.4168, -3.7038)


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_site_compliance_context_full_flow_no_flood(tmp_path: Path) -> None:
    """
    Full flow: resolve coords → Catastro parcel detail → SNCZI no flood → legal checks.
    Verifies parcel_detail and flood_zone are populated in the payload.
    """
    tools = _make_geo_tools(tmp_path)

    result = _run_with_patches(tools, _FLOOD_NONE)

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

    roads = p["carreteras"]
    assert roads["queried"] is True
    assert roads["in_affection_zone"] is False
    assert p["parcel_zoning"]["queried"] is False

    # Legal checks
    checks_by_code = {c["code"]: c for c in p["legal_checks"]}
    assert checks_by_code["hydraulic-domain"]["status"] == "ready"
    assert checks_by_code["roads-servitudes"]["status"] == "ready"
    assert checks_by_code["parcel-zoning"]["status"] == "pending_review"
    assert "aparece" in checks_by_code["hydraulic-domain"]["detail"].lower()
    assert checks_by_code["cadastral-identification"]["status"] == "ready"
    assert "245" in checks_by_code["cadastral-identification"]["detail"]


def test_site_compliance_context_flood_detected(tmp_path: Path) -> None:
    """When SNCZI returns features, flood check is 'conditional' with warning."""
    tools = _make_geo_tools(tmp_path)

    result = _run_with_patches(tools, _FLOOD_HIT)

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

    result = _run_with_patches(tools, _FLOOD_UNAVAILABLE)

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
        patch(
            "adv_archon.integrations.natura2000.query_protected_area",
            return_value=_NATURA_NONE,
        ),
        patch(
            "adv_archon.integrations.costas.query_coastal_zone",
            return_value=_COSTAS_NONE,
        ),
        patch(
            "adv_archon.integrations.carreteras.query_road_zone",
            return_value=_ROAD_NONE,
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

    result = _run_with_patches(tools, _FLOOD_NONE)

    assert result.payload["pgou_indexed"] is True
    assert result.payload["legal_readiness"] == "preliminary-ready"


def test_site_compliance_context_pgou_zoning_textual_clues(tmp_path: Path) -> None:
    """Indexed PGOU zoning text is exposed but remains a preliminary check."""
    tools = _make_geo_tools(tmp_path)
    tools._pgou.index_text(_ZONING_TEXT, municipality="Madrid", source="PGOU test")

    result = _run_with_patches(tools, _FLOOD_NONE)

    zoning = result.payload["parcel_zoning"]
    assert zoning["queried"] is True
    assert zoning["available"] is True
    assert zoning["classification"] == "Suelo urbano consolidado"
    assert "ZR-1" in zoning["ordinance"]

    checks_by_code = {c["code"]: c for c in result.payload["legal_checks"]}
    zoning_check = checks_by_code["parcel-zoning"]
    assert zoning_check["status"] == "conditional"
    assert "lectura normativa preliminar" in zoning_check["detail"]
    assert "no cruza la parcela con planos" in zoning_check["detail"]


def test_site_compliance_context_roads_detected(tmp_path: Path) -> None:
    """Road screening hit is carried into payload and legal checklist."""
    tools = _make_geo_tools(tmp_path)

    result = _run_with_patches(tools, _FLOOD_NONE, _ROAD_HIT)

    roads = result.payload["carreteras"]
    assert roads["queried"] is True
    assert roads["in_servitude_zone"] is True
    assert roads["nearest_distance_m"] == 18.4

    checks_by_code = {c["code"]: c for c in result.payload["legal_checks"]}
    roads_check = checks_by_code["roads-servitudes"]
    assert roads_check["status"] == "conditional"
    assert "cribado geométrico" in roads_check["detail"]
    assert "no delimita" in roads_check["detail"]


def test_site_compliance_context_roads_unavailable(tmp_path: Path) -> None:
    """Road WFS outage degrades to pending review without breaking site context."""
    tools = _make_geo_tools(tmp_path)

    result = _run_with_patches(tools, _FLOOD_NONE, _ROAD_UNAVAILABLE)

    assert result.payload["carreteras"]["in_affection_zone"] is None
    checks_by_code = {c["code"]: c for c in result.payload["legal_checks"]}
    assert checks_by_code["roads-servitudes"]["status"] == "pending_review"
