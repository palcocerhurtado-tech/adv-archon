from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.expediente_quality import (
    evaluate_expediente_quality,
    review_state_json,
)


def test_expediente_quality_detects_missing_core_inputs(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(title="Parcela sin datos", address="Calle sin resolver")

    quality = evaluate_expediente_quality(exp)

    assert quality.completeness == "incompleto"
    assert quality.risk_level == "alto"
    assert {issue.code for issue in quality.missing_items} >= {
        "plan",
        "cadastral_ref",
        "site_context",
        "legal_checks",
    }
    assert quality.sources_consulted_ok is False


def test_expediente_quality_reports_validated_pack_and_traceability(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(
        title="Cambio de uso",
        address="Calle Mayor 24, Madrid",
        municipality="Madrid",
        province="Madrid",
        cadastral_ref="2807901VK4720G0001ZX",
    )
    site_context = {
        "municipality": "Madrid",
        "cadastral_ref": "2807901VK4720G0001ZX",
        "parcel_detail": {"surface_m2": 84, "use_detail": "Comercial"},
        "parcel_zoning": {"summary": "Suelo urbano consolidado"},
        "flood_zone": {"in_flood_zone": False, "source": "SNCZI/CNIG"},
        "natura2000": {"in_protected_area": False, "source": "Red Natura/CNIG"},
        "costas": {"in_public_domain": False, "source": "SIGCOSTAS/MITECO"},
        "carreteras": {
            "in_affection_zone": False,
            "source": "Transportes INSPIRE/CNIG",
        },
        "legal_checks": [
            {"status": "ready", "title": "Catastro"},
            {"status": "ready", "title": "PGOU"},
            {"status": "ready", "title": "SNCZI"},
        ],
    }
    exp = replace(
        exp,
        plan_path=str(Path("/tmp/plano.pdf")),
        site_context=json.dumps(site_context),
        review_state=review_state_json("", action="confirmed", note="Revisado."),
    )

    quality = evaluate_expediente_quality(exp)

    assert quality.completeness == "completo"
    assert quality.risk_level == "bajo"
    assert quality.normative_pack is not None
    assert quality.normative_pack.status == "validado"
    assert quality.architect_review.status == "confirmed"
    assert len(quality.source_traces) == 6
    assert quality.source_traces[1].name == "PGOU municipal"


def test_review_state_can_exclude_report_and_preserve_note() -> None:
    state = review_state_json("", action="excluded", note="No usar hasta corregir PGOU.")
    parsed = json.loads(state)

    assert parsed["status"] == "excluded"
    assert parsed["include_in_report"] is False
    assert "corregir PGOU" in parsed["note"]
