from adv_archon.core.costs import UsageLedger
from adv_archon.core.llm_types import LLMResponse, LLMUsage


def test_usage_ledger_accumulates_usage() -> None:
    ledger = UsageLedger()

    ledger.record(
        "planner",
        LLMResponse(
            text="{}",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=4, total_tokens=14),
            provider="ollama",
            model="llama3.1:8b",
        ),
    )
    ledger.record(
        "assistant",
        LLMResponse(
            text="hola",
            usage=LLMUsage(
                prompt_tokens=20,
                completion_tokens=8,
                total_tokens=28,
                estimated_cost_usd=0.0001,
            ),
            provider="gemini",
            model="gemini-2.5-flash",
            redaction_applied=True,
            redaction_items=2,
        ),
    )

    summary = ledger.summary()

    assert summary.total_calls == 2
    assert summary.planner_calls == 1
    assert summary.assistant_calls == 1
    assert summary.total_tokens == 42
    assert summary.estimated_cost_usd == 0.0001
    assert summary.redacted_calls == 1
    assert summary.redacted_items == 2
    assert len(summary.breakdowns) == 2
