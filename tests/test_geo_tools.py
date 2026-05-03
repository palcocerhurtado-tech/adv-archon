from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from adv_archon.core.geo_store import GeoStore
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.tools.geo_tools import GeoToolResult, GeoTools

_PARCEL_DETAIL = {
    "ref": "1101201QA4410S0001ZZ",
    "surface_m2": 120,
    "construction_year": 1990,
    "use_detail": "Residencial",
    "floors_above": 2,
    "floors_below": 0,
    "address": "Parcela 1",
    "municipality": "Cádiz",
    "error": "",
}

_FLOOD_NONE = {
    "in_flood_zone": False,
    "periods": [],
    "source": "SNCZI/CNIG",
    "error": "",
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


class _StubGeoTools(GeoTools):
    def __init__(self, tmp_path: Path, payload: dict[str, object]) -> None:
        self._payload = payload
        super().__init__(GeoStore(tmp_path / "geo.db"), PGOUStore(tmp_path / "pgou.db"))

    def resolve_coordinates(
        self,
        latitude: float,
        longitude: float,
        *,
        refresh: bool = False,
    ) -> GeoToolResult:
        return GeoToolResult(
            name="resolve_coordinates",
            payload={
                "ok": True,
                "latitude": latitude,
                "longitude": longitude,
                "from_cache": refresh,
                **self._payload,
            },
        )


def _site_context_with_offline_sectorials(
    tools: GeoTools,
    latitude: float,
    longitude: float,
) -> GeoToolResult:
    patches = [
        patch("adv_archon.integrations.catastro.get_parcel_by_ref", return_value=_PARCEL_DETAIL),
        patch("adv_archon.integrations.snczi.query_flood_zone", return_value=_FLOOD_NONE),
        patch("adv_archon.integrations.natura2000.query_protected_area", return_value=_NATURA_NONE),
        patch("adv_archon.integrations.costas.query_coastal_zone", return_value=_COSTAS_NONE),
        patch("adv_archon.integrations.carreteras.query_road_zone", return_value=_ROAD_NONE),
    ]
    with ExitStack() as stack:
        for ctx in patches:
            stack.enter_context(ctx)
        return tools.site_compliance_context(latitude, longitude)


def test_site_compliance_context_adds_legal_checks_and_summary(tmp_path: Path) -> None:
    tools = _StubGeoTools(
        tmp_path,
        {
            "municipality": "Cádiz",
            "province": "Cádiz",
            "autonomous_community": "Andalucía",
            "display_location": "Cádiz, Andalucía",
            "cadastral_ref": "1101201QA4410S0001ZZ",
            "cadastral_address": "Parcela 1",
            "cadastral_use": "Residencial",
            "resolution": "catastro",
            "confidence": "high",
            "reasons": ["Referencia catastral obtenida."],
        },
    )

    result = _site_context_with_offline_sectorials(tools, 36.5271, -6.2886)

    assert result.payload["pgou_indexed"] is False
    assert result.payload["carreteras"]["queried"] is True
    assert result.payload["legal_readiness"] == "pgou-pending"
    assert "falta indexar o revisar la normativa municipal" in result.payload["legal_summary"]
    checks = result.payload["legal_checks"]
    assert isinstance(checks, list)
    assert any(item["code"] == "coastal-domain" for item in checks)
    assert any(item["code"] == "cadastral-identification" for item in checks)
    assert any(
        item["code"] == "roads-servitudes" and item["status"] == "ready"
        for item in checks
    )


def test_site_compliance_context_marks_pgou_ready_when_indexed(tmp_path: Path) -> None:
    tools = _StubGeoTools(
        tmp_path,
        {
            "municipality": "Madrid",
            "province": "Madrid",
            "autonomous_community": "Comunidad de Madrid",
            "display_location": "Madrid, Comunidad de Madrid",
            "cadastral_ref": "1234567VK4713S0001AB",
            "cadastral_address": "Calle Mayor 1",
            "cadastral_use": "Residencial",
            "resolution": "nominatim",
            "confidence": "high",
            "reasons": ["Municipio resuelto por Nominatim: Madrid"],
        },
    )
    tools._pgou.index_text(
        "Artículo 1. Uso residencial. Artículo 2. Alturas máximas.",
        municipality="Madrid",
        source="test",
    )

    result = _site_context_with_offline_sectorials(tools, 40.4168, -3.7038)

    assert result.payload["pgou_indexed"] is True
    assert result.payload["legal_readiness"] == "preliminary-ready"
    assert "base suficiente para un análisis preliminar" in result.payload["legal_summary"]
