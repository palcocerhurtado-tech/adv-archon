from __future__ import annotations

from adv_archon.core.benchmark import (
    BenchmarkCase,
    BenchmarkEvidence,
    BenchmarkRunner,
    evaluate_benchmark_case,
    extract_confidence_citations,
    has_confidence_block,
    run_benchmarks,
    score_grounding,
)
from adv_archon.core.evals import KnowledgeRetrievalEval
from adv_archon.core.llm_types import LLMResponse, LLMUsage


def _high_confidence_eval() -> KnowledgeRetrievalEval:
    return KnowledgeRetrievalEval(
        confidence="high",
        result_count=2,
        candidate_count=8,
        top_score=0.92,
        max_term_coverage=1.0,
        avg_term_coverage=0.76,
        rationale=("conocimiento local fuerte",),
    )


def _clock(values: list[float]):
    iterator = iter(values)
    return lambda: next(iterator)


def test_extract_confidence_citations_parses_agent_style_block() -> None:
    response = """
    Resumen del roadmap.

    Base y confianza:
    - conocimiento local: roadmap-acme.md | /tmp/docs/roadmap-acme.md
    - read_file: /tmp/docs/roadmap-acme.md
    - confianza: alta
    - motivo: recuperacion local fuerte
    """.strip()

    assert has_confidence_block(response) is True
    assert extract_confidence_citations(response) == (
        "conocimiento local: roadmap-acme.md | /tmp/docs/roadmap-acme.md",
        "read_file: /tmp/docs/roadmap-acme.md",
    )


def test_score_grounding_penalizes_missing_and_forbidden_facts() -> None:
    case = BenchmarkCase(
        case_id="grounding-mismatch",
        prompt="resume el estado",
        expected_facts=("alpha", "beta"),
        forbidden_facts=("hallucinacion",),
    )
    evidence = BenchmarkEvidence(response_text="Alpha presente con una hallucinacion clara.")

    metric = score_grounding(case, evidence)

    assert metric.score == 0.0
    assert metric.passed is False
    assert "hechos cubiertos 1/2" in metric.details
    assert any("incluye prohibidos" in detail for detail in metric.details)


def test_evaluate_benchmark_case_rewards_local_grounding_and_citations() -> None:
    case = BenchmarkCase(
        case_id="local-roadmap",
        prompt="resume el roadmap acme",
        expected_facts=("roadmap acme", "prioriza q2"),
        expected_citation_hints=("roadmap-acme.md",),
        require_local_knowledge=True,
        require_confidence_block=True,
    )
    evidence = BenchmarkEvidence(
        response_text=(
            "El roadmap ACME prioriza Q2 para cerrar la integracion.\n\n"
            "Base y confianza:\n"
            "- conocimiento local: roadmap-acme.md | /tmp/docs/roadmap-acme.md\n"
            "- confianza: alta\n"
            "- motivo: recuperacion local fuerte"
        ),
        used_local_knowledge=True,
        local_knowledge_hits=("roadmap-acme.md",),
        knowledge_eval=_high_confidence_eval(),
    )

    result = evaluate_benchmark_case(case, evidence, duration_seconds=1.25)

    assert result.passed is True
    assert result.grounding.score == 1.0
    assert result.local_knowledge.score == 1.0
    assert result.confidence_citations.score == 1.0
    assert result.confidence_block_present is True
    assert result.citations == (
        "conocimiento local: roadmap-acme.md | /tmp/docs/roadmap-acme.md",
    )
    assert result.duration_seconds == 1.25


def test_benchmark_runner_builds_summary_and_captures_failures() -> None:
    cases = (
        BenchmarkCase(
            case_id="ok",
            prompt="dime alpha",
            expected_facts=("alpha",),
        ),
        BenchmarkCase(
            case_id="boom",
            prompt="dime beta",
            expected_facts=("beta",),
        ),
    )

    def executor(case: BenchmarkCase) -> BenchmarkEvidence | LLMResponse | str:
        if case.case_id == "ok":
            return LLMResponse(
                text="Alpha confirmado.",
                usage=LLMUsage(total_tokens=12),
                provider="fake",
                model="local-test",
            )
        raise RuntimeError("boom")

    runner = BenchmarkRunner(executor, clock=_clock([0.0, 0.2, 0.2, 0.6]))
    summary = runner.run(cases)

    assert summary.total_cases == 2
    assert summary.passed_cases == 1
    assert summary.failed_cases == 1
    assert summary.pass_rate == 0.5
    assert summary.average_score == 0.5
    assert summary.total_duration_seconds == 0.6
    assert summary.average_duration_seconds == 0.3
    assert summary.results[0].provider == "fake"
    assert summary.results[0].model == "local-test"
    assert summary.results[0].duration_seconds == 0.2
    assert summary.results[1].error == "RuntimeError: boom"
    assert summary.results[1].overall_score == 0.0


def test_run_benchmarks_wraps_runner() -> None:
    cases = (
        BenchmarkCase(
            case_id="plain",
            prompt="saluda",
            expected_facts=("hola",),
        ),
    )

    summary = run_benchmarks(
        cases,
        executor=lambda _case: "Hola desde benchmark.",
        clock=_clock([0.0, 0.4]),
    )

    assert summary.total_cases == 1
    assert summary.passed_cases == 1
    assert summary.results[0].response_text == "Hola desde benchmark."
    assert summary.results[0].duration_seconds == 0.4
