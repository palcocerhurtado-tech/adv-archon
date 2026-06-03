from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from adv_archon.core.agent_plan import load_agent_history
from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.expediente_autopilot import (
    PERMISSION_BLOCKED,
    PERMISSION_CONFIRM,
    AutopilotStore,
    append_autopilot_checkpoint,
    build_expediente_autopilot,
    build_office_memory,
)


def test_autopilot_detects_missing_inputs_and_permissions(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(title="Sin datos", address="")

    autopilot = build_expediente_autopilot(exp)

    assert autopilot.verdict == "blocked"
    assert autopilot.progress_percent < 50
    assert autopilot.next_task is not None
    assert any(signal.code == "plan" and signal.status == "missing"
               for signal in autopilot.signals)
    assert any(item.code == "attach-plan" for item in autopilot.inbox)
    assert any(rule.level == PERMISSION_BLOCKED for rule in autopilot.permissions)
    assert any("Inventar normativa" in rule.examples for rule in autopilot.permissions)


def test_autopilot_builds_report_confirmation_task(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(
        title="Cambio de uso",
        address="Calle Mayor 24, Madrid",
        municipality="Madrid",
        cadastral_ref="2807901VK4720G0001ZX",
    )
    site_context = {
        "municipality": "Madrid",
        "cadastral_ref": "2807901VK4720G0001ZX",
        "parcel_detail": {"surface_m2": 84},
        "flood_zone": {"in_flood_zone": False},
        "natura2000": {"in_protected_area": False},
        "costas": {"in_public_domain": False},
        "carreteras": {"in_affection_zone": False},
        "legal_checks": [{"title": "PGOU", "status": "ready"}],
    }
    exp = replace(
        exp,
        plan_path=str(tmp_path / "plano.pdf"),
        site_context=json.dumps(site_context),
        analysis_result=json.dumps({"verdict": "viable", "summary": "OK"}),
        quality_score=82,
        quality_result=json.dumps({"verdict": "APTO"}),
        status="analizado",
    )

    autopilot = build_expediente_autopilot(exp)
    report_task = next(task for task in autopilot.tasks if task.code == "prepare-report")
    quality_task = next(task for task in autopilot.tasks if task.code == "quality-judge")

    assert autopilot.progress_percent >= 60
    assert report_task.permission == PERMISSION_CONFIRM
    assert report_task.status == "pending"
    assert quality_task.status == "completed"
    assert quality_task.evidence == "Score 82/100."


def test_autopilot_checkpoint_and_store_persist_objectives(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(title="Autopilot", address="Calle Mayor 24, Zaragoza")
    autopilot = build_expediente_autopilot(exp)

    history = append_autopilot_checkpoint("", autopilot, run_id="run-1")
    events = load_agent_history(history)
    autopilot_store = AutopilotStore(tmp_path / "autopilot.db")
    record = autopilot_store.save_run(autopilot, run_id="run-1")
    latest = autopilot_store.latest(exp.id)

    assert events[-1].step_code == "autopilot-objectives"
    assert "Autopilot iniciado" in events[-1].message
    assert record.id == "run-1"
    assert latest is not None
    assert latest.payload["expediente_id"] == exp.id
    assert latest.summary == autopilot.summary


def test_office_memory_summarizes_municipalities_and_warnings(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    madrid = store.create(title="Madrid", address="Calle 1", municipality="Madrid")
    zaragoza = store.create(title="Zaragoza", address="Calle 2", municipality="Zaragoza")
    madrid = replace(
        madrid,
        site_context=json.dumps(
            {
                "legal_checks": [
                    {"title": "Inundabilidad", "status": "conditional"},
                    {"title": "PGOU", "status": "pending_review"},
                ]
            }
        ),
    )
    zaragoza = replace(
        zaragoza,
        site_context=json.dumps(
            {"legal_checks": [{"title": "Inundabilidad", "status": "conditional"}]}
        ),
    )

    memory = build_office_memory([madrid, zaragoza])

    assert memory.municipalities == ("Madrid", "Zaragoza")
    assert memory.recurring_warnings[0] == "Inundabilidad"
