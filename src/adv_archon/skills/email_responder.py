"""Skill: Email responder.

Drafts professional email replies given an original email and instructions.
"""

from __future__ import annotations

from typing import Any

from adv_archon.skills.base import Skill, SkillResult
from adv_archon.skills.registry import registry

_SYSTEM = (
    "Eres un asistente de comunicación profesional. "
    "Redactas respuestas de email claras, concisas y apropiadas al contexto. "
    "Adaptas el tono según el estilo del email original."
)


class EmailResponderSkill(Skill):
    name = "email_responder"
    description = (
        "Redacta una respuesta profesional a un email dado. "
        "Acepta el email original y las instrucciones de respuesta."
    )
    args_schema = {
        "original_email": {
            "type": "string",
            "description": "Texto completo del email original al que responder.",
        },
        "instructions": {
            "type": "string",
            "description": "Instrucciones sobre qué incluir o el tono de la respuesta.",
        },
        "sender_name": {
            "type": "string",
            "description": "Tu nombre para firmar el email (opcional).",
        },
    }

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    def run(
        self,
        *,
        original_email: str,
        instructions: str,
        sender_name: str = "",
        **_: Any,
    ) -> SkillResult:
        signature = f"\n\nSaludos,\n{sender_name}" if sender_name else "\n\nSaludos,"

        if self._llm is None:
            draft = (
                f"[Borrador automático]\n\n"
                f"Respuesta a:\n{original_email[:500]}\n\n"
                f"Instrucciones: {instructions}\n"
                f"{signature}"
            )
            return SkillResult(success=True, output=draft)

        from adv_archon.core.llm_types import LLMMessage

        prompt = (
            f"Email original:\n\n{original_email}\n\n"
            f"Instrucciones para la respuesta: {instructions}\n\n"
            f"{'Firma con el nombre: ' + sender_name if sender_name else ''}\n\n"
            "Redacta la respuesta completa, lista para enviar."
        )
        resp = self._llm.complete(
            [LLMMessage(role="user", content=prompt)],
            system_prompt=_SYSTEM,
            task="fast",
        )
        return SkillResult(
            success=True,
            output=resp.text,
            artifacts={"draft": resp.text},
        )


registry.register(EmailResponderSkill())
