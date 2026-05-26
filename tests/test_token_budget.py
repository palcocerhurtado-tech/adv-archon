from __future__ import annotations

from adv_archon.core.token_budget import CHARS_PER_TOKEN, TRUNCATION_MARKER, TokenBudget


def test_estimate_uses_spanish_legal_text_heuristic() -> None:
    budget = TokenBudget(max_tokens=2048)
    text = "Normativa urbanística española" * 10

    assert budget.estimate(text) == max(1, int(len(text) / CHARS_PER_TOKEN))


def test_empty_text_has_minimum_cost() -> None:
    budget = TokenBudget(max_tokens=2048)

    assert budget.estimate("") == 1
    budget.add("empty", "", priority=5)

    assert budget.build() == {"empty": ""}


def test_build_without_overflow_keeps_all_slots_by_priority_order() -> None:
    budget = TokenBudget(max_tokens=1200, reserved_output=200)
    budget.add("pgou_chunks", "PGOU", priority=7)
    budget.add("system_prompt", "Sistema", priority=10)
    budget.add("site_context", "Catastro", priority=9)
    budget.add("notas", "Notas", priority=3)

    result = budget.build()

    assert list(result) == ["system_prompt", "site_context", "pgou_chunks", "notas"]
    assert result["pgou_chunks"] == "PGOU"


def test_build_with_overflow_drops_low_priority_slots() -> None:
    budget = TokenBudget(max_tokens=520, reserved_output=320)
    budget.add("system_prompt", "s" * 100, priority=10)
    budget.add("site_context", "c" * 100, priority=9)
    budget.add("plan_summary", "p" * 100, priority=8)
    budget.add("pgou_chunks", "n" * 2000, priority=7)
    budget.add("notas", "low priority", priority=3)

    result = budget.build()

    assert "system_prompt" in result
    assert "site_context" in result
    assert "plan_summary" in result
    assert "pgou_chunks" not in result
    assert "notas" not in result


def test_build_truncates_when_remaining_budget_is_useful() -> None:
    budget = TokenBudget(max_tokens=900, reserved_output=300)
    budget.add("system_prompt", "s" * 300, priority=10)
    budget.add("site_context", "c" * 300, priority=9)
    budget.add("pgou_chunks", "n" * 5000, priority=7)

    result = budget.build()

    assert "pgou_chunks" in result
    assert result["pgou_chunks"].endswith(TRUNCATION_MARKER)
    assert len(result["pgou_chunks"]) < 5000


def test_utilization_reports_total_requested_budget() -> None:
    budget = TokenBudget(max_tokens=1000, reserved_output=500)
    budget.add("one", "a" * 950, priority=5)
    budget.add("two", "b" * 950, priority=4)

    assert budget.utilization > 0.9
