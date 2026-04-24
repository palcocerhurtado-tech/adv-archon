from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, TypeAlias

from adv_archon.core.evals import KnowledgeRetrievalEval
from adv_archon.core.llm_types import LLMResponse, LLMUsage

CONFIDENCE_BLOCK_HEADER = "Base y confianza:"
LOCAL_CITATION_PREFIX = "conocimiento local:"
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class BenchmarkCase:
    case_id: str
    prompt: str
    expected_facts: tuple[str, ...] = ()
    forbidden_facts: tuple[str, ...] = ()
    expected_citation_hints: tuple[str, ...] = ()
    require_local_knowledge: bool = False
    require_confidence_block: bool = False
    pass_threshold: float = 0.7
    tags: tuple[str, ...] = ()


@dataclass(slots=True)
class BenchmarkEvidence:
    response_text: str
    knowledge_eval: KnowledgeRetrievalEval | None = None
    used_local_knowledge: bool = False
    local_knowledge_hits: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()
    provider: str | None = None
    model: str | None = None
    usage: LLMUsage | None = None


@dataclass(slots=True)
class BenchmarkMetric:
    name: str
    score: float
    passed: bool
    details: tuple[str, ...] = ()


@dataclass(slots=True)
class BenchmarkCaseResult:
    case: BenchmarkCase
    response_text: str
    grounding: BenchmarkMetric
    local_knowledge: BenchmarkMetric
    confidence_citations: BenchmarkMetric
    overall_score: float
    passed: bool
    duration_seconds: float
    confidence_block_present: bool
    citations: tuple[str, ...] = ()
    provider: str | None = None
    model: str | None = None
    usage: LLMUsage | None = None
    error: str | None = None


@dataclass(slots=True)
class BenchmarkSummary:
    results: tuple[BenchmarkCaseResult, ...]
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    average_score: float
    average_grounding: float
    average_local_knowledge: float
    average_confidence_citations: float
    total_duration_seconds: float
    average_duration_seconds: float


class BenchmarkExecutor(Protocol):
    def __call__(self, case: BenchmarkCase) -> BenchmarkExecution:
        ...


BenchmarkExecution: TypeAlias = BenchmarkEvidence | LLMResponse | str


class BenchmarkRunner:
    def __init__(
        self,
        executor: BenchmarkExecutor,
        *,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._executor = executor
        self._clock = clock

    def run_case(self, case: BenchmarkCase) -> BenchmarkCaseResult:
        started_at = self._clock()
        try:
            raw_result = self._executor(case)
        except Exception as exc:
            duration = round(max(0.0, self._clock() - started_at), 4)
            return _build_error_result(case, duration_seconds=duration, error=exc)

        duration = round(max(0.0, self._clock() - started_at), 4)
        evidence = _coerce_benchmark_evidence(raw_result)
        return evaluate_benchmark_case(case, evidence, duration_seconds=duration)

    def run(self, cases: Sequence[BenchmarkCase]) -> BenchmarkSummary:
        results = [self.run_case(case) for case in cases]
        return summarize_benchmark_results(results)


def run_benchmarks(
    cases: Sequence[BenchmarkCase],
    executor: BenchmarkExecutor,
    *,
    clock: Callable[[], float] = perf_counter,
) -> BenchmarkSummary:
    return BenchmarkRunner(executor, clock=clock).run(cases)


def evaluate_benchmark_case(
    case: BenchmarkCase,
    evidence: BenchmarkEvidence,
    *,
    duration_seconds: float = 0.0,
) -> BenchmarkCaseResult:
    threshold = _clamp_score(case.pass_threshold)
    confidence_block_present = has_confidence_block(evidence.response_text)
    citations = _collect_citations(evidence)
    grounding = score_grounding(case, evidence)
    local_knowledge = score_local_knowledge_usage(case, evidence)
    confidence_citations = score_confidence_citations(case, evidence)
    overall_score = round(
        (
            grounding.score
            + local_knowledge.score
            + confidence_citations.score
        )
        / 3,
        4,
    )
    passed = (
        overall_score >= threshold
        and grounding.passed
        and local_knowledge.passed
        and confidence_citations.passed
    )
    return BenchmarkCaseResult(
        case=case,
        response_text=evidence.response_text,
        grounding=grounding,
        local_knowledge=local_knowledge,
        confidence_citations=confidence_citations,
        overall_score=overall_score,
        passed=passed,
        duration_seconds=round(max(0.0, duration_seconds), 4),
        confidence_block_present=confidence_block_present,
        citations=citations,
        provider=evidence.provider,
        model=evidence.model,
        usage=evidence.usage,
    )


def summarize_benchmark_results(
    results: Sequence[BenchmarkCaseResult],
) -> BenchmarkSummary:
    collected = tuple(results)
    total_cases = len(collected)
    passed_cases = sum(1 for result in collected if result.passed)
    failed_cases = total_cases - passed_cases
    total_duration = round(sum(result.duration_seconds for result in collected), 4)
    average_duration = round(total_duration / total_cases, 4) if total_cases else 0.0
    average_score = _average(result.overall_score for result in collected)
    average_grounding = _average(result.grounding.score for result in collected)
    average_local_knowledge = _average(result.local_knowledge.score for result in collected)
    average_confidence_citations = _average(
        result.confidence_citations.score for result in collected
    )
    pass_rate = round(passed_cases / total_cases, 4) if total_cases else 0.0
    return BenchmarkSummary(
        results=collected,
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate=pass_rate,
        average_score=average_score,
        average_grounding=average_grounding,
        average_local_knowledge=average_local_knowledge,
        average_confidence_citations=average_confidence_citations,
        total_duration_seconds=total_duration,
        average_duration_seconds=average_duration,
    )


def score_grounding(
    case: BenchmarkCase,
    evidence: BenchmarkEvidence,
) -> BenchmarkMetric:
    threshold = _clamp_score(case.pass_threshold)
    normalized_response = _normalize_text(evidence.response_text)
    if not normalized_response:
        return BenchmarkMetric(
            name="grounding",
            score=0.0,
            passed=False,
            details=("respuesta vacia",),
        )

    matched = tuple(
        fact for fact in case.expected_facts if _normalized_contains(normalized_response, fact)
    )
    missing = tuple(fact for fact in case.expected_facts if fact not in matched)
    forbidden = tuple(
        fact for fact in case.forbidden_facts if _normalized_contains(normalized_response, fact)
    )

    coverage = 1.0 if not case.expected_facts else len(matched) / len(case.expected_facts)
    penalty = 0.0 if not case.forbidden_facts else len(forbidden) / len(case.forbidden_facts)
    score = round(_clamp_score(coverage - penalty), 4)

    details: list[str] = []
    if case.expected_facts:
        details.append(f"hechos cubiertos {len(matched)}/{len(case.expected_facts)}")
    else:
        details.append("sin hechos esperados explicitos")
    if missing:
        details.append(f"faltan: {', '.join(missing[:3])}")
    if forbidden:
        details.append(f"incluye prohibidos: {', '.join(forbidden[:3])}")

    return BenchmarkMetric(
        name="grounding",
        score=score,
        passed=score >= threshold,
        details=tuple(details),
    )


def score_local_knowledge_usage(
    case: BenchmarkCase,
    evidence: BenchmarkEvidence,
) -> BenchmarkMetric:
    if not case.require_local_knowledge:
        return BenchmarkMetric(
            name="local_knowledge",
            score=1.0,
            passed=True,
            details=("conocimiento local no requerido",),
        )

    threshold = _clamp_score(case.pass_threshold)
    local_citations = tuple(
        citation
        for citation in extract_confidence_citations(evidence.response_text)
        if _normalize_text(citation).startswith(_normalize_text(LOCAL_CITATION_PREFIX))
    )
    evidence_score = 0.0
    details: list[str] = []

    if evidence.used_local_knowledge:
        evidence_score += 0.3
        details.append("runner marco uso de conocimiento local")
    else:
        details.append("sin bandera explicita de uso local")

    if evidence.local_knowledge_hits or local_citations:
        evidence_score += 0.4
        visible_evidence = len(evidence.local_knowledge_hits) or len(local_citations)
        details.append(f"evidencia local visible {visible_evidence}")
    else:
        details.append("sin evidencia local visible")

    if evidence.knowledge_eval is not None:
        confidence_bonus = {
            "high": 0.3,
            "medium": 0.2,
            "low": 0.1,
        }.get(evidence.knowledge_eval.confidence, 0.0)
        evidence_score += confidence_bonus
        details.append(f"knowledge eval {evidence.knowledge_eval.confidence}")
    else:
        details.append("sin knowledge eval")

    score = round(_clamp_score(evidence_score), 4)
    return BenchmarkMetric(
        name="local_knowledge",
        score=score,
        passed=score >= threshold,
        details=tuple(details),
    )


def score_confidence_citations(
    case: BenchmarkCase,
    evidence: BenchmarkEvidence,
) -> BenchmarkMetric:
    if not case.require_confidence_block and not case.expected_citation_hints:
        return BenchmarkMetric(
            name="confidence_citations",
            score=1.0,
            passed=True,
            details=("bloque de confianza no requerido",),
        )

    threshold = _clamp_score(case.pass_threshold)
    block_present = has_confidence_block(evidence.response_text)
    citations = _collect_citations(evidence)
    score = 0.0
    details: list[str] = []

    if block_present:
        score += 0.5
        details.append("incluye bloque de confianza")
    elif case.require_confidence_block:
        details.append("falta bloque de confianza")

    if citations:
        score += 0.3
        details.append(f"citas detectadas {len(citations)}")
    else:
        details.append("sin citas detectadas")

    if case.expected_citation_hints:
        matched_hints = tuple(
            hint
            for hint in case.expected_citation_hints
            if any(_normalized_contains(citation, hint) for citation in citations)
        )
        score += 0.2 * (len(matched_hints) / len(case.expected_citation_hints))
        details.append(
            f"pistas de cita {len(matched_hints)}/{len(case.expected_citation_hints)}"
        )
        missing_hints = tuple(
            hint for hint in case.expected_citation_hints if hint not in matched_hints
        )
        if missing_hints:
            details.append(f"faltan pistas: {', '.join(missing_hints[:3])}")

    final_score = round(_clamp_score(score), 4)
    return BenchmarkMetric(
        name="confidence_citations",
        score=final_score,
        passed=final_score >= threshold,
        details=tuple(details),
    )


def has_confidence_block(response_text: str) -> bool:
    header = _normalize_text(CONFIDENCE_BLOCK_HEADER)
    return any(_normalize_text(line) == header for line in response_text.splitlines())


def extract_confidence_citations(response_text: str) -> tuple[str, ...]:
    header = _normalize_text(CONFIDENCE_BLOCK_HEADER)
    citations: list[str] = []
    in_block = False

    for line in response_text.splitlines():
        stripped = line.strip()
        normalized = _normalize_text(stripped)
        if not in_block:
            if normalized == header:
                in_block = True
            continue

        if not stripped:
            if citations:
                break
            continue
        if not stripped.startswith("-"):
            break

        content = stripped[1:].strip()
        normalized_content = _normalize_text(content)
        if normalized_content.startswith("confianza:"):
            continue
        if normalized_content.startswith("motivo:"):
            continue
        citations.append(content)

    return tuple(citations)


def _build_error_result(
    case: BenchmarkCase,
    *,
    duration_seconds: float,
    error: Exception,
) -> BenchmarkCaseResult:
    message = f"{type(error).__name__}: {error}"
    metric = BenchmarkMetric(
        name="benchmark_error",
        score=0.0,
        passed=False,
        details=(message,),
    )
    return BenchmarkCaseResult(
        case=case,
        response_text="",
        grounding=metric,
        local_knowledge=metric,
        confidence_citations=metric,
        overall_score=0.0,
        passed=False,
        duration_seconds=duration_seconds,
        confidence_block_present=False,
        error=message,
    )


def _coerce_benchmark_evidence(payload: BenchmarkExecution) -> BenchmarkEvidence:
    if isinstance(payload, BenchmarkEvidence):
        return payload
    if isinstance(payload, LLMResponse):
        return BenchmarkEvidence(
            response_text=payload.text,
            provider=payload.provider,
            model=payload.model,
            usage=payload.usage,
        )
    return BenchmarkEvidence(response_text=payload)


def _collect_citations(evidence: BenchmarkEvidence) -> tuple[str, ...]:
    return _dedupe_preserving_order(
        (*extract_confidence_citations(evidence.response_text), *evidence.citations)
    )


def _dedupe_preserving_order(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _average(values: Iterable[float]) -> float:
    collected = tuple(values)
    if not collected:
        return 0.0
    return round(sum(collected) / len(collected), 4)


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _WHITESPACE_RE.sub(" ", without_marks).strip()


def _normalized_contains(normalized_haystack: str, needle: str) -> bool:
    return _normalize_text(needle) in normalized_haystack


__all__ = [
    "BenchmarkCase",
    "BenchmarkCaseResult",
    "BenchmarkEvidence",
    "BenchmarkExecution",
    "BenchmarkExecutor",
    "BenchmarkMetric",
    "BenchmarkRunner",
    "BenchmarkSummary",
    "evaluate_benchmark_case",
    "extract_confidence_citations",
    "has_confidence_block",
    "run_benchmarks",
    "score_confidence_citations",
    "score_grounding",
    "score_local_knowledge_usage",
    "summarize_benchmark_results",
]
