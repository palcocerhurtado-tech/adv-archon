"""
LLM-based reranker for PGOU search results.
Scores each chunk 0-10 for relevance to the query, then sorts descending.
"""
from __future__ import annotations

import logging
from typing import Any

from adv_archon.core.llm_types import LLMMessage
from adv_archon.core.pgou_store import PGOUChunk

log = logging.getLogger(__name__)

_SYSTEM = (
    "Eres un técnico urbanista español. Tu tarea es valorar si un fragmento de PGOU "
    "es relevante para un caso concreto. Responde SOLO con un número entero de 0 a 10."
)

_PROMPT = """
CASO: {case}
FRAGMENTO: {chunk_text}

¿Cuánto de relevante es este fragmento para el caso? (0=nada útil, 10=muy relevante)
Responde SOLO con el número:""".strip()


class PGOUReranker:
    """Score and reorder PGOU chunks by LLM relevance."""

    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client

    def rerank(
        self,
        chunks: list[PGOUChunk],
        *,
        case_description: str,
        top_k: int = 5,
    ) -> list[PGOUChunk]:
        """Return up to top_k chunks sorted by LLM relevance score (descending)."""
        if not chunks:
            return []
        scored: list[tuple[float, PGOUChunk]] = []
        for chunk in chunks:
            score = self._score(chunk.text, case_description)
            scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    def _score(self, chunk_text: str, case: str) -> float:
        try:
            prompt = _PROMPT.format(
                case=case[:500],
                chunk_text=chunk_text[:800],
            )
            raw = self._llm.complete_text(
                [LLMMessage(role="system", content=_SYSTEM),
                 LLMMessage(role="user", content=prompt)]
            )
            for token in raw.strip().split():
                try:
                    return max(0.0, min(10.0, float(token)))
                except ValueError:
                    continue
        except Exception as exc:
            log.debug("pgou_reranker score failed: %s", exc)
        return 5.0
