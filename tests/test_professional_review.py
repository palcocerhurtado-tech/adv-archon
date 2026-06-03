from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from adv_archon.core.agent_plan import update_agent_step_review
from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.professional_review import (
    build_professional_review_dashboard,
    normalize_review_filter,
)


def test_professional_review_dashboard_summarizes_architect_decisions(
    tmp_path: Path,
) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    reviews = update_agent_step_review(
        "",
        step_code="pgou-normativa",
        action="validate",
        updated_at="2026-06-03T12:00:00+00:00",
    )
    reviews = update_agent_step_review(
        reviews,
        step_code="sectorial-sources",
        action="accept-warning",
        updated_at="2026-06-03T12:01:00+00:00",
    )
    reviews = update_agent_step_review(
        reviews,
        step_code="plan-document",
        action="exclude",
        updated_at="2026-06-03T12:02:00+00:00",
    )
    reviews = update_agent_step_review(
        reviews,
        step_code="preliminary-dictamen",
        action="repeat",
        updated_at="2026-06-03T12:03:00+00:00",
    )
    exp = store.create(
        title="Cambio de uso",
        address="Calle Mayor 24, Madrid",
        municipality="Madrid",
        cadastral_ref="2807901VK4720G0001ZX",
    )
    exp = replace(
        exp,
        site_context=json.dumps(
            {
                "municipality": "Madrid",
                "cadastral_ref": "2807901VK4720G0001ZX",
                "parcel_detail": {"surface_m2": 84},
                "flood_zone": {"in_flood_zone": False},
                "natura2000": {"in_protected_area": False},
                "costas": {"in_public_domain": False},
                "carreteras": {"in_affection_zone": False},
                "legal_checks": [{"title": "PGOU", "status": "ready"}],
            }
        ),
        agent_step_reviews=reviews,
    )

    dashboard = build_professional_review_dashboard([exp])

    assert dashboard.summary.expediente_count == 1
    assert dashboard.summary.total_steps == 7
    assert dashboard.summary.validated == 1
    assert dashboard.summary.accepted_warnings == 1
    assert dashboard.summary.excluded == 1
    assert dashboard.summary.repeat_requested == 1
    assert len(dashboard.filtered("warnings")) == 1
    assert dashboard.filtered("excluded")[0].include_in_report is False
    assert dashboard.filtered("repeat")[0].review_status == "requested_repeat"


def test_professional_review_dashboard_flags_missing_inputs(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    store.create(title="Sin datos", address="")

    dashboard = build_professional_review_dashboard(store.list_all())

    assert dashboard.summary.expediente_count == 1
    assert dashboard.summary.pending == 7
    assert dashboard.summary.needs_review >= 1
    assert any(step.step_status == "blocked" for step in dashboard.steps)
    assert dashboard.filtered("needs_review")


def test_professional_review_filter_normalization() -> None:
    assert normalize_review_filter("warnings") == "warnings"
    assert normalize_review_filter("NOPE") == "all"
    assert normalize_review_filter(None) == "all"
