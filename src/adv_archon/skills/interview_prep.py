"""Skill: Interview preparation.

Generates tailored interview questions and model answers for a given role/topic.
"""

from __future__ import annotations

from typing import Any

from adv_archon.skills.base import Skill, SkillResult
from adv_archon.skills.registry import registry

_SYSTEM = (
    "Eres un experto en reclutamiento técnico y coaching de carreras. "
    "Generas preguntas de entrevista relevantes con respuestas modelo detalladas."
)


class InterviewPrepSkill(Skill):
    name = "interview_prep"
    description = (
        "Genera preguntas de entrevista y respuestas modelo para un puesto o tema dado. "
        "Útil para preparar entrevistas técnicas o de comportamiento."
    )
    args_schema = {
        "role": {
            "type": "string",
            "description": "Puesto o área (ej: 'arquitecto software', 'data scientist').",
        },
        "focus": {
            "type": "string",
            "description": "Áreas específicas a cubrir (ej: 'Python, diseño de sistemas, SOLID').",
        },
        "num_questions": {
            "type": "integer",
            "description": "Número de preguntas a generar (defecto: 5).",
        },
        "mode": {
            "type": "string",
            "description": (
                "'technical' para técnicas, 'behavioral' para comportamiento, "
                "'mixed' para ambas."
            ),
        },
    }

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    def run(  # type: ignore[override]
        self,
        *,
        role: str,
        focus: str = "",
        num_questions: int = 5,
        mode: str = "mixed",
        **_: Any,
    ) -> SkillResult:
        if self._llm is None:
            output = _fallback_questions(role, num_questions)
            return SkillResult(success=True, output=output)

        from adv_archon.core.llm_types import LLMMessage

        mode_desc = {
            "technical": "preguntas técnicas de conocimiento y resolución de problemas",
            "behavioral": "preguntas de comportamiento (STAR method)",
            "mixed": "mezcla de preguntas técnicas y de comportamiento",
        }.get(mode, "preguntas mixtas")

        focus_str = f"\nÁreas específicas: {focus}" if focus else ""

        prompt = (
            f"Genera {num_questions} {mode_desc} para el puesto de: {role}{focus_str}\n\n"
            "Para cada pregunta incluye:\n"
            "1. La pregunta\n"
            "2. Por qué se hace (qué evalúa)\n"
            "3. Respuesta modelo (concisa pero completa)\n\n"
            "Formatea con numeración clara."
        )
        resp = self._llm.complete(
            [LLMMessage(role="user", content=prompt)],
            system_prompt=_SYSTEM,
            task="reasoning",
        )
        return SkillResult(
            success=True,
            output=resp.text,
            artifacts={"role": role, "num_questions": num_questions, "mode": mode},
        )


def _fallback_questions(role: str, n: int) -> str:
    generic = [
        "¿Cuéntame sobre tu experiencia más relevante para este puesto?",
        "¿Cómo manejas situaciones de alta presión o plazos ajustados?",
        "¿Describe un proyecto técnico complejo que hayas liderado?",
        "¿Cómo priorizas cuando tienes múltiples tareas urgentes?",
        "¿Qué metodologías de desarrollo usas y por qué?",
    ]
    lines = [f"Preguntas de entrevista para: {role}\n"]
    for i, q in enumerate(generic[:n], 1):
        lines.append(f"{i}. {q}")
    return "\n".join(lines)


registry.register(InterviewPrepSkill())
