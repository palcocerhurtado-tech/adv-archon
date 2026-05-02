from __future__ import annotations

from dataclasses import dataclass

from adv_archon.core.knowledge import KnowledgeSearchResult


@dataclass(slots=True)
class KnowledgeRetrievalEval:
    confidence: str
    result_count: int
    candidate_count: int
    top_score: float
    max_term_coverage: float
    avg_term_coverage: float
    rationale: tuple[str, ...]


@dataclass(slots=True)
class ResponseConfidence:
    level: str
    rationale: tuple[str, ...]


def evaluate_knowledge_retrieval(
    search_result: KnowledgeSearchResult | None,
) -> KnowledgeRetrievalEval | None:
    if search_result is None:
        return None
    if not search_result.records:
        return KnowledgeRetrievalEval(
            confidence="low",
            result_count=0,
            candidate_count=search_result.candidate_count,
            top_score=0.0,
            max_term_coverage=0.0,
            avg_term_coverage=0.0,
            rationale=("sin resultados locales relevantes",),
        )

    coverages = [record.term_coverage for record in search_result.records]
    scores = [float(record.score or 0.0) for record in search_result.records]
    max_coverage = max(coverages, default=0.0)
    avg_coverage = sum(coverages) / len(coverages)
    top_score = max(scores, default=0.0)
    rationale: list[str] = [
        f"{len(search_result.records)} resultados locales",
        f"cobertura maxima {max_coverage:.0%}",
    ]
    if search_result.candidate_count:
        rationale.append(f"{search_result.candidate_count} candidatos analizados")

    if max_coverage >= 0.75 or (max_coverage >= 0.5 and top_score >= 0.85):
        confidence = "high"
    elif max_coverage >= 0.34 or top_score >= 0.6:
        confidence = "medium"
    else:
        confidence = "low"

    return KnowledgeRetrievalEval(
        confidence=confidence,
        result_count=len(search_result.records),
        candidate_count=search_result.candidate_count,
        top_score=round(top_score, 4),
        max_term_coverage=round(max_coverage, 4),
        avg_term_coverage=round(avg_coverage, 4),
        rationale=tuple(rationale),
    )


def summarize_response_confidence(
    *,
    knowledge_eval: KnowledgeRetrievalEval | None,
    successful_tools: int,
    failed_tools: int,
    used_local_knowledge: bool,
) -> ResponseConfidence:
    rationale: list[str] = []
    score = 0

    if successful_tools > 0:
        score += 2
        rationale.append(f"{successful_tools} tools utiles")
    if successful_tools >= 2:
        score += 1
        rationale.append("varias fuentes o herramientas utiles")
    if failed_tools > 0:
        score -= 1
        rationale.append(f"{failed_tools} tools con error")
    if used_local_knowledge:
        score += 1
        rationale.append("apoyo en conocimiento local")
    if knowledge_eval is not None:
        if knowledge_eval.confidence == "high":
            score += 2
            rationale.append("recuperacion local fuerte")
        elif knowledge_eval.confidence == "medium":
            score += 1
            rationale.append("recuperacion local razonable")
        else:
            rationale.append("recuperacion local debil")

    if score >= 4:
        level = "alta"
    elif score >= 2:
        level = "media"
    else:
        level = "baja"

    return ResponseConfidence(level=level, rationale=tuple(rationale))
