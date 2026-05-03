"""Tests for preliminary parcel zoning extraction from indexed PGOU text."""
from __future__ import annotations

from pathlib import Path

from adv_archon.core.parcel_zoning import query_parcel_zoning
from adv_archon.core.pgou_store import PGOUStore

_ZONING_TEXT = """
Artículo 4. Ordenanza residencial ZR-1.

Clasificación del suelo: Suelo urbano consolidado.
Calificación urbanística: Residencial unifamiliar intensiva.
Ordenanza de aplicación: ZR-1 Residencial.
Uso principal: residencial vivienda.
Usos permitidos: residencial, dotacional y garaje.
Edificabilidad máxima: 1,20 m2/m2.
Ocupación máxima: 40%.
Altura máxima: 7 m y 2 plantas.
Retranqueos: 3 m a linderos y 5 m a vial.
"""


def test_query_parcel_zoning_extracts_pgou_clues(tmp_path: Path) -> None:
    store = PGOUStore(tmp_path / "pgou.db")
    store.index_text(_ZONING_TEXT, municipality="Madrid", source="PGOU test")

    result = query_parcel_zoning(store, "Madrid", pgou_indexed=True)

    assert result["queried"] is True
    assert result["available"] is True
    assert result["classification"] == "Suelo urbano consolidado"
    assert "Residencial" in result["zoning"]
    assert "ZR-1" in result["ordinance"]
    assert "residencial" in result["allowed_uses"]
    assert "1,20" in result["buildability"]
    assert "40%" in result["occupancy"]
    assert "7 m" in result["height"]
    assert "3 m" in result["setbacks"]
    assert result["confidence"] == "medium"
    assert result["excerpts"][0]["source"] == "PGOU test"


def test_query_parcel_zoning_requires_indexed_pgou(tmp_path: Path) -> None:
    store = PGOUStore(tmp_path / "pgou.db")

    result = query_parcel_zoning(store, "Madrid", pgou_indexed=False)

    assert result["queried"] is False
    assert result["available"] is False
    assert "no indexado" in result["error"]


def test_query_parcel_zoning_no_clear_signals(tmp_path: Path) -> None:
    store = PGOUStore(tmp_path / "pgou.db")
    store.index_text("Artículo 1. Disposiciones generales.", municipality="Madrid", source="test")

    result = query_parcel_zoning(store, "Madrid", pgou_indexed=True)

    assert result["queried"] is True
    assert result["available"] is False
    assert result["confidence"] == "low"
    assert "No se han encontrado" in result["error"]
