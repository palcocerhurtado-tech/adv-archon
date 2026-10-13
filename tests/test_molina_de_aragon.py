from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from adv_archon.core.demo import DEMO_NOTES_MOLINA, create_molina_de_aragon_demo
from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.municipal_planning import (
    MOLINA_DE_ARAGON_ID,
    MOLINA_DE_ARAGON_NAME,
    MOLINA_DE_ARAGON_SOURCE_URL,
    seed_molina_de_aragon_planning,
    write_molina_de_aragon_catalog,
)
from adv_archon.core.parcel_zoning import query_parcel_zoning
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.core.studio import city_pack_for, load_studio_client_config
from adv_archon.tools.pgou_scraper import SOURCES


def test_seed_molina_planning_indexes_normas_subsidiarias(tmp_path: Path) -> None:
    store = PGOUStore(tmp_path / "pgou.db")

    chunks = seed_molina_de_aragon_planning(store)
    municipality = store.get_municipality(MOLINA_DE_ARAGON_NAME)

    assert chunks > 0
    assert municipality is not None
    assert municipality.name == MOLINA_DE_ARAGON_NAME
    assert municipality.planning_type == "normas_subsidiarias"
    assert municipality.status == "preliminar"
    assert municipality.province == "Guadalajara"
    assert municipality.autonomous_community == "Castilla-La Mancha"
    assert municipality.source_url == MOLINA_DE_ARAGON_SOURCE_URL


def test_molina_zoning_returns_preliminary_warning(tmp_path: Path) -> None:
    store = PGOUStore(tmp_path / "pgou.db")
    seed_molina_de_aragon_planning(store)

    result = query_parcel_zoning(store, MOLINA_DE_ARAGON_NAME, pgou_indexed=True)

    assert result["queried"] is True
    assert result["available"] is True
    assert "07" in result["ordinance"]
    assert "Residencial" in result["ordinance"]
    assert result["requires_map_crossing"] is True
    assert result["confidence"] in {"low", "medium"}
    assert result["source"] == MOLINA_DE_ARAGON_SOURCE_URL


def test_molina_catalog_files_are_written(tmp_path: Path) -> None:
    catalog = write_molina_de_aragon_catalog(tmp_path)

    assert catalog == tmp_path / "pgou" / MOLINA_DE_ARAGON_ID / "catalogo.json"
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    assert payload["municipio_id"] == MOLINA_DE_ARAGON_ID
    assert payload["planning_type"] == "normas_subsidiarias"
    assert "Ayuntamiento" in payload["legal_warning"]
    assert (catalog.parent / "zonificacion.json").exists()
    assert (catalog.parent / "texto_extraido" / "normas_subsidiarias_preliminar.txt").exists()


def test_molina_is_available_as_studio_pack_and_catalog_source(tmp_path: Path) -> None:
    pack = city_pack_for(MOLINA_DE_ARAGON_NAME)
    cfg = load_studio_client_config(tmp_path)

    assert pack is not None
    assert pack.status == "preliminar"
    assert "Normas Subsidiarias" in pack.label
    assert MOLINA_DE_ARAGON_NAME in cfg.included_municipalities
    assert any(source.name == MOLINA_DE_ARAGON_NAME for source in SOURCES)


def test_molina_demo_generates_report_with_planning_section(tmp_path: Path) -> None:
    expediente_store = ExpedienteStore(tmp_path / "expedientes.db")
    pgou_store = PGOUStore(tmp_path / "pgou.db")

    exp = create_molina_de_aragon_demo(
        expediente_store,
        data_dir=tmp_path,
        pgou_store=pgou_store,
    )

    assert exp.notes == DEMO_NOTES_MOLINA
    assert exp.status == "informe_listo"
    assert exp.municipality == MOLINA_DE_ARAGON_NAME
    assert Path(exp.plan_path).exists()
    assert Path(exp.report_path).exists()

    site_context = json.loads(exp.site_context)
    assert site_context["planning"]["planning_type"] == "normas_subsidiarias"
    assert site_context["parcel_zoning"]["requires_map_crossing"] is True

    text = "\n".join(page.extract_text() or "" for page in PdfReader(exp.report_path).pages)
    assert "PLANEAMIENTO APLICABLE" in text
    normalized_text = _without_accents(text).lower()
    assert "molina de aragon" in normalized_text
    assert "normas subsidiarias" in normalized_text
    assert "cruce con planos" in normalized_text


def _without_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
