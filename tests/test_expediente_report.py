from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.report_generator import generate_expediente_pdf


def test_generate_expediente_pdf_from_site_context(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(
        title="Reforma local",
        address="Calle Mayor 1, Madrid",
        municipality="Madrid",
        province="Madrid",
        latitude=40.4168,
        longitude=-3.7038,
        cadastral_ref="7537903VK4873N0001OU",
    )
    exp.site_context = json.dumps(
        {
            "municipality": "Madrid",
            "province": "Madrid",
            "cadastral_ref": "7537903VK4873N0001OU",
            "cadastral_address": "CL MAYOR 1, MADRID",
            "parcel_detail": {
                "surface_m2": 120,
                "construction_year": 1975,
                "use_detail": "Residencial",
                "floors_above": 4,
            },
            "legal_checks": [
                {
                    "title": "Identificación catastral",
                    "status": "ready",
                    "detail": "Referencia localizada.",
                    "recommended_action": "Usar en expediente.",
                },
                {
                    "title": "Ordenanza y zona de parcela",
                    "status": "conditional",
                    "detail": "Lectura textual preliminar.",
                    "recommended_action": "Confirmar en planos.",
                },
            ],
        },
        ensure_ascii=False,
    )
    exp.analysis_result = json.dumps(
        {
            "verdict": "condicionado",
            "summary": "Expediente condicionado a confirmar ordenanza.",
            "annotations": [
                {
                    "status": "warning",
                    "description": "Ordenanza pendiente de confirmación.",
                    "recommendation": "Consultar visor municipal.",
                }
            ],
            "next_steps": ["Confirmar ordenanza en planos de ordenación."],
        },
        ensure_ascii=False,
    )

    output = generate_expediente_pdf(
        expediente=exp,
        output_path=tmp_path / "informe.pdf",
    )

    assert output.exists()
    assert output.stat().st_size > 1000


def test_expediente_store_migrates_existing_minimal_table(tmp_path: Path) -> None:
    db_path = tmp_path / "expedientes.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE expedientes (id TEXT PRIMARY KEY, title TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO expedientes (id, title) VALUES (?, ?)",
        ("exp-1", "Expediente antiguo"),
    )
    conn.commit()
    conn.close()

    store = ExpedienteStore(db_path)
    exp = store.get("exp-1")

    assert exp is not None
    assert exp.title == "Expediente antiguo"
    assert exp.status == "borrador"
    assert exp.site_context == ""
    assert exp.quality_score is None
    assert exp.quality_result == ""
    assert exp.agent_history == ""
    assert exp.agent_step_reviews == ""
