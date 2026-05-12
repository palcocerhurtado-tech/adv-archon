from __future__ import annotations

from pathlib import Path

from adv_archon.core.demo import DEMO_NOTES, DEMO_TITLE, create_demo_expediente
from adv_archon.core.expediente import ExpedienteStore


def test_create_demo_expediente_generates_plan_and_report(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")

    exp = create_demo_expediente(store, data_dir=tmp_path)

    assert exp.title == DEMO_TITLE
    assert exp.notes == DEMO_NOTES
    assert exp.status == "informe_listo"
    assert exp.municipality == "Madrid"
    assert Path(exp.plan_path).exists()
    assert Path(exp.report_path).exists()
    assert Path(exp.report_path).stat().st_size > 2000
    assert '"demo": true' in exp.site_context


def test_create_demo_expediente_reuses_existing_demo_record(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")

    first = create_demo_expediente(store, data_dir=tmp_path)
    second = create_demo_expediente(store, data_dir=tmp_path)

    assert second.id == first.id
    assert len([exp for exp in store.list_all() if exp.notes == DEMO_NOTES]) == 1
