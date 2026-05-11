"""Plan executor for ADV ARCHON.

Walks Plan steps sequentially, applying the reflector on each tool call.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from adv_archon.core.plan_schema import Plan, RiskLevel, Step
from adv_archon.core.reflector import Verdict, reflect
from adv_archon.core.state_machine import AgentState, AgentStateMachine

ToolFn = Callable[..., Any]
ConfirmFn = Callable[[str], bool]   # returns True = user approved


def _risk_label(risk: RiskLevel) -> str:
    colours = {
        RiskLevel.LOW: "\033[32m",      # green
        RiskLevel.MEDIUM: "\033[33m",   # yellow
        RiskLevel.HIGH: "\033[31m",     # red
        RiskLevel.CRITICAL: "\033[35m", # magenta
    }
    reset = "\033[0m"
    return f"{colours.get(risk, '')}[{risk.value.upper()}]{reset}"


class PlanExecutor:
    def __init__(
        self,
        *,
        tool_registry: dict[str, ToolFn],
        confirm: ConfirmFn,
        on_step_start: Callable[[Step], None] | None = None,
        on_step_done: Callable[[Step, str | None], None] | None = None,
    ) -> None:
        self._tools = tool_registry
        self._confirm = confirm
        self._on_step_start = on_step_start
        self._on_step_done = on_step_done
        self._sm = AgentStateMachine()

    def execute(self, plan: Plan) -> str:
        """Execute all pending steps in the plan. Returns a summary string."""
        if not plan.approved:
            return "Plan no aprobado — ejecución cancelada."

        self._sm.transition(AgentState.EXECUTING)
        results: list[str] = []

        for step in plan.pending_steps():
            if self._on_step_start:
                self._on_step_start(step)

            label = _risk_label(step.risk)

            # HIGH/CRITICAL steps require explicit confirmation
            if step.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                msg = (
                    f"{label} Paso {step.index}: {step.intent}\n"
                    f"  Herramienta: {step.tool}\n"
                    f"  Argumentos: {step.arguments}\n"
                    "¿Aprobar? [s/n]: "
                )
                if not self._confirm(msg):
                    step.skipped = True
                    results.append(f"Paso {step.index} omitido por usuario.")
                    if self._on_step_done:
                        self._on_step_done(step, None)
                    continue

            fn = self._tools.get(step.tool)
            if fn is None:
                step.skipped = True
                results.append(
                    f"Paso {step.index} omitido — herramienta '{step.tool}' no disponible."
                )
                if self._on_step_done:
                    self._on_step_done(step, None)
                continue

            self._sm.transition(AgentState.REFLECTING)
            verdict, reason, result = reflect(step.tool, fn, step.arguments)
            self._sm.transition(AgentState.EXECUTING)

            if verdict == Verdict.BLOCK:
                step.skipped = True
                msg = f"Paso {step.index} bloqueado por reflector: {reason}"
                results.append(msg)
            else:
                step.completed = True
                step.result = str(result) if result is not None else ""
                results.append(f"Paso {step.index} completado: {step.intent}")

            if self._on_step_done:
                self._on_step_done(step, step.result)

        self._sm.transition(AgentState.DONE)
        self._sm.transition(AgentState.IDLE)

        return "\n".join(results) if results else "Sin pasos que ejecutar."
