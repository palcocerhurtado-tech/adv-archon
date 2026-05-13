from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from adv_archon.core.demo import create_studio_demo_expedientes
from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.studio import build_studio_payload, city_pack_for, get_case_template


def test_studio_templates_cover_commercial_case_types() -> None:
    assert get_case_template("cambio_uso_vivienda").label == "Cambio de uso local a vivienda"
    assert get_case_template("vivienda_unifamiliar").base_hours_saved >= 10
    assert city_pack_for("Madrid") is not None
    assert city_pack_for("Madrid").status == "validado"  # type: ignore[union-attr]


def test_studio_payload_estimates_value_from_checks() -> None:
    payload = build_studio_payload(
        case_type="obra_nueva",
        municipality="Valencia",
        site_context={
            "cadastral_ref": "4625001YJ2742C0001SA",
            "parcel_detail": {"surface_m2": 970},
            "legal_checks": [
                {"status": "ready"},
                {"status": "pending_review"},
                {"status": "missing"},
            ],
        },
        analysis={"verdict": "revisar"},
    )

    assert payload["decision"] == "CONDICIONADO"
    assert payload["estimated_value"]["hours_saved"] >= 13
    assert payload["estimated_value"]["risks_detected"] == 2
    assert payload["city_pack"]["status"] == "pendiente"


def test_expediente_store_persists_case_type_and_migrates_old_db(tmp_path: Path) -> None:
    db_path = tmp_path / "expedientes.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE expedientes (id TEXT PRIMARY KEY, title TEXT NOT NULL)")
    conn.execute("INSERT INTO expedientes (id, title) VALUES (?, ?)", ("old", "Antiguo"))
    conn.commit()
    conn.close()

    store = ExpedienteStore(db_path)
    old = store.get("old")
    assert old is not None
    assert old.case_type == "cambio_uso_vivienda"

    exp = store.create(
        title="Parcela vivienda",
        address="40.4,-3.7",
        case_type="vivienda_unifamiliar",
    )
    saved = store.get(exp.id)
    assert saved is not None
    assert saved.case_type == "vivienda_unifamiliar"


def test_create_studio_demo_expedientes_generates_three_reports(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")

    demos = create_studio_demo_expedientes(store, data_dir=tmp_path)

    assert len(demos) == 3
    assert {demo.case_type for demo in demos} == {
        "cambio_uso_vivienda",
        "vivienda_unifamiliar",
        "obra_nueva",
    }
    for demo in demos:
        assert demo.status == "informe_listo"
        assert Path(demo.plan_path).exists()
        assert Path(demo.report_path).exists()
        assert json.loads(demo.site_context)["demo"] is True
