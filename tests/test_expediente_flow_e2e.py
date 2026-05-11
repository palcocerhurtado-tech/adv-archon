from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.geo_store import GeoStore
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.core.report_generator import generate_expediente_pdf
from adv_archon.tools.geo_tools import GeoTools


def test_expediente_complete_flow_resolves_analyzes_and_exports_pdf(tmp_path: Path) -> None:
    """Create expediente -> resolve parcel context -> store analysis -> export report."""
    store = ExpedienteStore(tmp_path / "expedientes.db")
    pgou_store = PGOUStore(tmp_path / "pgou.db")
    pgou_store.index_text(
        """
        Artículo 4. Ordenanza residencial ZR-1.
        Clasificación del suelo: Suelo urbano consolidado.
        Calificación urbanística: Residencial colectiva.
        Uso principal: residencial vivienda.
        Edificabilidad máxima: 1,20 m2/m2.
        """,
        municipality="Madrid",
        source="fixture-pgou",
    )
    geo_tools = GeoTools(GeoStore(tmp_path / "geo.db"), pgou_store)

    exp = store.create(
        title="Expediente QA Gran Vía",
        address="Gran Vía 1, Madrid",
        municipality="",
        province="",
        latitude=40.4168,
        longitude=-3.7038,
        cadastral_ref="",
        notes="Fixture e2e offline.",
    )

    with ExitStack() as stack:
        for ctx in _offline_geo_patches():
            stack.enter_context(ctx)
        site_context = geo_tools.site_compliance_context(40.4168, -3.7038).payload

    assert site_context["ok"] is True
    assert site_context["municipality"] == "Madrid"
    assert site_context["cadastral_ref"] == "7537903VK4873N0001OU"
    assert site_context["parcel_detail"]["surface_m2"] == 245
    assert site_context["flood_zone"]["in_flood_zone"] is False
    assert site_context["carreteras"]["in_affection_zone"] is False
    assert site_context["parcel_zoning"]["queried"] is True

    exp.municipality = str(site_context["municipality"])
    exp.province = str(site_context["province"])
    exp.cadastral_ref = str(site_context["cadastral_ref"])
    exp.site_context = json.dumps(site_context, ensure_ascii=False)
    exp.status = "geocodificado"
    store.update(exp)

    analysis = {
        "verdict": "condicionado",
        "summary": "Viabilidad preliminar condicionada a confirmar ordenanza en planos.",
        "annotations": [
            {
                "status": "warning",
                "description": "La zonificación procede de lectura textual preliminar del PGOU.",
                "recommendation": "Contrastar con visor o planos municipales.",
            }
        ],
        "next_steps": [
            "Confirmar alineaciones y ordenanza en el plano municipal.",
            "Revisar parámetros urbanísticos antes de presentar licencia.",
        ],
        "confidence": "media",
    }
    exp.analysis_result = json.dumps(analysis, ensure_ascii=False)
    exp.status = "analizado"
    store.update(exp)

    output_path = tmp_path / "informe-expediente.pdf"
    report_path = generate_expediente_pdf(exp, output_path=output_path)
    exp.report_path = str(report_path)
    exp.status = "informe_generado"
    store.update(exp)

    saved = store.get(exp.id)
    assert saved is not None
    assert saved.status == "informe_generado"
    assert saved.report_path == str(report_path)
    assert report_path.exists()
    assert report_path.stat().st_size > 1000


def _offline_geo_patches():
    return [
        patch(
            "adv_archon.integrations.nominatim.reverse_geocode",
            return_value={
                "display_name": "Madrid, Comunidad de Madrid, España",
                "address": {
                    "city": "Madrid",
                    "state": "Comunidad de Madrid",
                    "country": "España",
                    "country_code": "es",
                },
            },
        ),
        patch(
            "adv_archon.integrations.catastro.get_cadastral_data",
            return_value={
                "cadastral_ref": "7537903VK4873N0001OU",
                "address": "CL GRAN VIA 1, MADRID",
                "use": "Residencial",
                "catastro_municipality": "Madrid",
                "catastro_province": "Madrid",
                "raw_xml": "",
                "error": "",
            },
        ),
        patch(
            "adv_archon.integrations.catastro.get_parcel_by_ref",
            return_value={
                "ref": "7537903VK4873N0001OU",
                "surface_m2": 245,
                "construction_year": 1965,
                "use_detail": "Residencial",
                "floors_above": 6,
                "floors_below": 1,
                "address": "CL GRAN VIA 1, MADRID",
                "municipality": "Madrid",
                "error": "",
            },
        ),
        patch(
            "adv_archon.integrations.snczi.query_flood_zone",
            return_value={
                "in_flood_zone": False,
                "periods": [],
                "source": "SNCZI/CNIG",
                "error": "",
            },
        ),
        patch(
            "adv_archon.integrations.natura2000.query_protected_area",
            return_value={
                "in_protected_area": False,
                "zones": [],
                "source": "Red Natura 2000 / CNIG",
                "error": "",
            },
        ),
        patch(
            "adv_archon.integrations.costas.query_coastal_zone",
            return_value={
                "in_dpmt": False,
                "in_protection_zone": False,
                "in_influence_zone": False,
                "zones": [],
                "source": "SIGCOSTAS / MITECO",
                "error": "",
            },
        ),
        patch(
            "adv_archon.integrations.carreteras.query_road_zone",
            return_value={
                "in_domain_zone": False,
                "in_servitude_zone": False,
                "in_affection_zone": False,
                "zones": [],
                "source": "Transportes INSPIRE / CNIG",
                "method": "cribado geométrico por proximidad a eje viario oficial",
                "nearest_distance_m": None,
                "error": "",
            },
        ),
    ]
