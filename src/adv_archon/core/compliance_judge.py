from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from adv_archon.core.llm_types import LLMMessage

JUDGE_SYSTEM = (
    "Eres un auditor de informes de cumplimiento urbanístico español. "
    "Tu tarea es evaluar la calidad de un análisis generado por IA. "
    "Debes responder SOLO con JSON válido, sin explicaciones adicionales."
)

JUDGE_PROMPT_TEMPLATE = """
MUNICIPIO: {municipality}
RESUMEN DEL PLANO: {plan_summary}

ANÁLISIS GENERADO:
{analysis}

Evalúa el análisis anterior según estos criterios:
1. PRECISIÓN: ¿Las referencias normativas son plausibles para España? (0-25)
2. COMPLETITUD: ¿Se cubren altura, ocupación, retranqueos, usos? (0-25)
3. ESTRUCTURA: ¿Tiene veredicto claro (VIABLE/CONDICIONADO/REVISAR)? (0-25)
4. ACCIONABILIDAD: ¿Los next_steps son concretos y útiles? (0-25)

Responde EXACTAMENTE con este JSON:
{{
  "score": <0-100>,
  "breakdown": {{
    "precision": <0-25>,
    "completeness": <0-25>,
    "structure": <0-25>,
    "actionability": <0-25>
  }},
  "flags": ["<problema1>"],
  "verdict": "<APTO|REVISAR|RECHAZAR>"
}}
""".strip()


class ComplianceJudge:
    """Local LLM-as-judge for preliminary urban compliance reports."""

    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client

    def evaluate(self, municipality: str, plan_summary: str, analysis: str) -> dict[str, Any]:
        """Evaluate an analysis without raising; failures return score=None."""
        prompt = JUDGE_PROMPT_TEMPLATE.format(
            municipality=municipality or "No indicado",
            plan_summary=plan_summary or "No disponible",
            analysis=analysis or "",
        )
        try:
            text = self._complete_text([LLMMessage(role="user", content=prompt)])
            parsed = _parse_json_object(text)
            return _normalise_judge_result(parsed)
        except Exception as exc:
            return {
                "score": None,
                "breakdown": {},
                "flags": [f"No se pudo evaluar el análisis: {exc}"],
                "verdict": "REVISAR",
            }

    @staticmethod
    def is_reliable(result: dict[str, Any], threshold: int = 60) -> bool:
        return int(result.get("score") or 0) >= threshold

    def _complete_text(self, messages: Iterable[LLMMessage]) -> str:
        response = self._llm.complete(
            messages,
            system_prompt=JUDGE_SYSTEM,
            response_mime_type="application/json",
            task="fast",
            prefer_local=True,
        )
        return str(getattr(response, "text", response))


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match is None:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("La evaluación no devolvió un objeto JSON.")
    return data


def _normalise_judge_result(data: dict[str, Any]) -> dict[str, Any]:
    score = _clamp_int(data.get("score"), minimum=0, maximum=100)
    raw_breakdown = data.get("breakdown")
    breakdown = raw_breakdown if isinstance(raw_breakdown, dict) else {}
    flags = data.get("flags")
    verdict = str(data.get("verdict") or "REVISAR").upper()
    if verdict not in {"APTO", "REVISAR", "RECHAZAR"}:
        verdict = "REVISAR"
    return {
        "score": score,
        "breakdown": {
            "precision": _clamp_int(breakdown.get("precision"), minimum=0, maximum=25),
            "completeness": _clamp_int(
                breakdown.get("completeness"),
                minimum=0,
                maximum=25,
            ),
            "structure": _clamp_int(breakdown.get("structure"), minimum=0, maximum=25),
            "actionability": _clamp_int(
                breakdown.get("actionability"),
                minimum=0,
                maximum=25,
            ),
        },
        "flags": [str(flag) for flag in flags] if isinstance(flags, list) else [],
        "verdict": verdict,
    }


def _clamp_int(value: object, *, minimum: int, maximum: int) -> int:
    if not isinstance(value, (bool, int, float, str)):
        return minimum
    try:
        number = int(value)
    except ValueError:
        number = minimum
    return max(minimum, min(maximum, number))


__all__ = [
    "ComplianceJudge",
    "JUDGE_PROMPT_TEMPLATE",
    "JUDGE_SYSTEM",
]
