from __future__ import annotations

from pathlib import Path

from adv_archon.core.office_memory import (
    OfficeMemoryStore,
    build_office_memory_context,
)


def test_office_memory_store_records_and_summarizes_decisions(tmp_path: Path) -> None:
    store = OfficeMemoryStore(tmp_path / "office_memory.db")
    try:
        store.record_step_decision(
            municipality="Madrid",
            step_code="pgou-normativa",
            action="validate",
            label="Paso validado por arquitecto.",
        )
        store.record_step_decision(
            municipality="Madrid",
            step_code="sectorial-sources",
            action="accept-warning",
            label="Advertencia aceptada por arquitecto.",
        )

        snapshot = store.snapshot()
    finally:
        store.close()

    policy = snapshot.policy_for("Madrid")

    assert snapshot.validated_decisions == 1
    assert snapshot.recurring_warnings == ("sectorial-sources",)
    assert policy is not None
    assert policy.validated_pgou is True
    assert policy.accepted_warnings == ("sectorial-sources",)


def test_office_memory_context_is_prompt_ready(tmp_path: Path) -> None:
    store = OfficeMemoryStore(tmp_path / "office_memory.db")
    try:
        store.record_step_decision(
            municipality="Zaragoza",
            step_code="pgou-normativa",
            action="validated",
            label="Validado",
        )
        snapshot = store.snapshot()
    finally:
        store.close()

    context = build_office_memory_context(snapshot)

    assert "Office Memory" in context
    assert "Zaragoza" in context
    assert "PGOU validated by office review" in context
