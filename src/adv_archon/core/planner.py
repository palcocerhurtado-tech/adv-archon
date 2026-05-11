"""LLM-based plan generator for ADV ARCHON.

Generates a structured Plan from a natural-language objective.
"""

from __future__ import annotations

import json
import re

from adv_archon.core.llm import LLMRouter
from adv_archon.core.llm_types import LLMMessage
from adv_archon.core.plan_schema import Plan, RiskLevel, Step

_SYSTEM_PROMPT = """\
Eres un planificador de tareas para el agente ADV ARCHON.
Dado un objetivo en lenguaje natural, genera un plan de ejecución estructurado.

REGLAS:
- Descompón el objetivo en pasos concretos y mínimos.
- Para cada paso indica: intent (qué hace), tool (herramienta a usar),
  arguments (dict JSON), risk (low|medium|high|critical), reversible (bool).
- Sé conservador con el riesgo: cualquier escritura de archivo = high,
  red = medium, lectura = low.
- Devuelve SOLO JSON válido con esta estructura:

{
  "objective": "...",
  "steps": [
    {
      "index": 1,
      "intent": "Descripción breve",
      "tool": "nombre_herramienta",
      "arguments": {},
      "risk": "low",
      "reversible": true
    }
  ]
}
"""


def _parse_plan(raw: str, objective: str) -> Plan:
    """Extract JSON from LLM output and build a Plan."""
    # Strip markdown fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    json_str = match.group(1) if match else raw

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: single-step plan that just delegates to the LLM
        return Plan(
            objective=objective,
            steps=[
                Step(
                    index=1,
                    intent="Ejecutar objetivo sin plan estructurado",
                    tool="assistant",
                    arguments={"prompt": objective},
                    risk=RiskLevel.LOW,
                    reversible=True,
                )
            ],
        )

    steps: list[Step] = []
    for raw_step in data.get("steps", []):
        risk_str = raw_step.get("risk", "low")
        try:
            risk = RiskLevel(risk_str)
        except ValueError:
            risk = RiskLevel.MEDIUM
        steps.append(
            Step(
                index=raw_step.get("index", len(steps) + 1),
                intent=raw_step.get("intent", ""),
                tool=raw_step.get("tool", "assistant"),
                arguments=raw_step.get("arguments", {}),
                risk=risk,
                reversible=bool(raw_step.get("reversible", True)),
            )
        )

    return Plan(objective=data.get("objective", objective), steps=steps)


def generate_plan(objective: str, *, llm: LLMRouter) -> Plan:
    """Call the LLM to generate a Plan for the given objective."""
    messages = [LLMMessage(role="user", content=f"Objetivo: {objective}")]
    response = llm.complete(messages, system_prompt=_SYSTEM_PROMPT, task="planner")
    return _parse_plan(response.text, objective)
