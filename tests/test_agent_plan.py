from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from adv_archon.core.agent_plan import (
    append_agent_event,
    build_expediente_agent_plan,
    load_agent_history,
)
from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.expediente_quality import review_state_json


def test_agent_plan_blocks_empty_expediente(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(title="Sin datos", address="")

    plan = build_expediente_agent_plan(exp)

    assert plan.verdict == "blocked"
    assert plan.confidence == "baja"
    assert plan.steps[0].code == "resolve-location"
    assert plan.steps[0].status == "blocked"
    assert any(question.code == "continue-without-plan" for question in plan.questions)


def test_agent_history_appends_and_overlays_in_progress_step(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    history = append_agent_event(
        "",
        step_code="query-catastro",
        title="Consultar Catastro",
        status="in_progress",
        message="Consultando Catastro OVC…",
        run_id="run-1",
        created_at="2026-06-03T10:00:00+00:00",
    )
    exp = store.create(
        title="Con progreso",
        address="Calle Mayor 24, Madrid",
        municipality="Madrid",
    )
    exp = replace(exp, agent_history=history)

    loaded = load_agent_history(history)
    plan = build_expediente_agent_plan(exp)
    catastro = next(step for step in plan.steps if step.code == "query-catastro")

    assert len(loaded) == 1
    assert loaded[0].status_label == "En curso"
    assert catastro.status == "in_progress"
    assert "Catastro OVC" in catastro.recommended_action


def test_agent_plan_guides_complete_validated_expediente(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(
        title="Cambio de uso",
        address="Calle Mayor 24, Madrid",
        municipality="Madrid",
        province="Madrid",
        latitude=40.415363,
        longitude=-3.707398,
        cadastral_ref="2807901VK4720G0001ZX",
    )
    site_context = {
        "municipality": "Madrid",
        "province": "Madrid",
        "cadastral_ref": "2807901VK4720G0001ZX",
        "parcel_detail": {"surface_m2": 84, "use_detail": "Comercial"},
        "parcel_zoning": {"summary": "Suelo urbano consolidado"},
        "flood_zone": {"in_flood_zone": False},
        "natura2000": {"in_protected_area": False},
        "costas": {
            "in_public_domain": False,
            "in_protection_servitude": False,
        },
        "carreteras": {"in_affection_zone": False},
        "legal_checks": [
            {"title": "Catastro", "status": "ready"},
            {"title": "PGOU", "status": "ready"},
            {"title": "SNCZI", "status": "ready"},
            {"title": "Costas", "status": "not_applicable"},
        ],
    }
    analysis = {
        "verdict": "viable",
        "summary": "No se detectan bloqueos en el cribado preliminar.",
    }
    exp = replace(
        exp,
        plan_path=str(tmp_path / "plano.pdf"),
        site_context=json.dumps(site_context, ensure_ascii=False),
        analysis_result=json.dumps(analysis, ensure_ascii=False),
        review_state=review_state_json("", action="confirmed", note="Revisado."),
        status="analizado",
    )

    plan = build_expediente_agent_plan(exp)

    assert plan.verdict == "viable"
    assert plan.confidence == "alta"
    assert {step.status for step in plan.steps} == {"completed"}
    assert plan.questions == ()
    assert len(plan.source_log) == 6


def test_agent_plan_marks_preliminary_pgou_and_sectorial_warning(
    tmp_path: Path,
) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(
        title="Parcela con afección",
        address="Calle Río 1, Zaragoza",
        municipality="Zaragoza",
        province="Zaragoza",
        cadastral_ref="1234567XM7113S0001AB",
    )
    site_context = {
        "municipality": "Zaragoza",
        "cadastral_ref": "1234567XM7113S0001AB",
        "parcel_detail": {"surface_m2": 140},
        "parcel_zoning": {"summary": "Zona preliminar detectada textual"},
        "flood_zone": {"in_flood_zone": True},
        "natura2000": {"in_protected_area": False},
        "costas": {"in_public_domain": False},
        "carreteras": {"in_affection_zone": False},
        "legal_checks": [
            {"title": "Catastro", "status": "ready"},
            {"title": "Inundabilidad", "status": "conditional"},
            {"title": "PGOU", "status": "pending_review"},
        ],
    }
    exp = replace(exp, site_context=json.dumps(site_context, ensure_ascii=False))

    plan = build_expediente_agent_plan(exp)
    question_codes = {question.code for question in plan.questions}

    assert plan.verdict == "conditional"
    assert "continue-without-plan" in question_codes
    assert "pgou-preliminar" in question_codes
    assert "sectorial-warning" in question_codes
    assert any(step.code == "pgou-normativa" and step.status == "needs_review"
               for step in plan.steps)
