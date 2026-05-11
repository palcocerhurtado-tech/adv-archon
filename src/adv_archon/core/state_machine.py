"""Agent state machine for plan-and-execute flow.

States: IDLE → PLANNING → AWAITING_HUMAN → EXECUTING → REFLECTING → DONE | ABORTED
"""

from __future__ import annotations

from enum import StrEnum


class AgentState(StrEnum):
    IDLE = "idle"
    PLANNING = "planning"
    AWAITING_HUMAN = "awaiting_human"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    DONE = "done"
    ABORTED = "aborted"


_VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.IDLE: {AgentState.PLANNING, AgentState.DONE},
    AgentState.PLANNING: {AgentState.AWAITING_HUMAN, AgentState.ABORTED},
    AgentState.AWAITING_HUMAN: {AgentState.EXECUTING, AgentState.ABORTED},
    AgentState.EXECUTING: {AgentState.REFLECTING, AgentState.ABORTED},
    AgentState.REFLECTING: {AgentState.DONE, AgentState.ABORTED, AgentState.EXECUTING},
    AgentState.DONE: {AgentState.IDLE},
    AgentState.ABORTED: {AgentState.IDLE},
}


class StateMachineError(RuntimeError):
    pass


class AgentStateMachine:
    def __init__(self) -> None:
        self._state = AgentState.IDLE

    @property
    def state(self) -> AgentState:
        return self._state

    def transition(self, new_state: AgentState) -> None:
        allowed = _VALID_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            raise StateMachineError(
                f"Transición inválida: {self._state.value} → {new_state.value}"
            )
        self._state = new_state

    def reset(self) -> None:
        self._state = AgentState.IDLE

    def is_terminal(self) -> bool:
        return self._state in (AgentState.DONE, AgentState.ABORTED)
