from __future__ import annotations

from pathlib import Path

from adv_archon.core.geo_store import GeoStore
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.tools.geo_tools import GeoToolResult, GeoTools


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

    result = tools.site_compliance_context(36.5271, -6.2886)

    assert result.payload["pgou_indexed"] is False
    assert result.payload["legal_readiness"] == "pgou-pending"
    assert "falta indexar o revisar la normativa municipal" in result.payload["legal_summary"]
    checks = result.payload["legal_checks"]
    assert isinstance(checks, list)
    assert any(item["code"] == "coastal-domain" for item in checks)
    assert any(item["code"] == "cadastral-identification" for item in checks)


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

    result = tools.site_compliance_context(40.4168, -3.7038)

    assert result.payload["pgou_indexed"] is True
    assert result.payload["legal_readiness"] == "preliminary-ready"
    assert "base suficiente para un análisis preliminar" in result.payload["legal_summary"]
