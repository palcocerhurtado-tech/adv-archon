from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ToolObservation:
    name: str
    summary: str
    success: bool
    citations: tuple[str, ...] = ()


@dataclass(slots=True)
class ContextPacket:
    task: str
    intent: str
    profile: str
    execution_mode: str
    checkpoint: str
    reasons: tuple[str, ...]
    runtime_block: str | None
    memory_items: tuple[str, ...]
    knowledge_items: tuple[str, ...]
    tool_items: tuple[str, ...]
    confidence_hint: str | None = None

    def render_for_model(self) -> str:
        lines = [
            "Task context packet:",
            f"- Task: {self.task}",
            f"- Intent: {self.intent}",
            f"- Profile: {self.profile}",
            f"- Mode: {self.execution_mode}",
            f"- Checkpoint: {self.checkpoint}",
        ]
        if self.reasons:
            lines.append(f"- Signals: {', '.join(self.reasons)}")
        if self.confidence_hint:
            lines.append(f"- Confidence hint: {self.confidence_hint}")
        if self.runtime_block:
            lines.append("")
            lines.append(self.runtime_block)
        if self.memory_items:
            lines.append("")
            lines.append("Relevant long-term memory:")
            lines.extend(f"- {item}" for item in self.memory_items)
        if self.knowledge_items:
            lines.append("")
            lines.append("Local knowledge evidence:")
            lines.extend(f"- {item}" for item in self.knowledge_items)
        if self.tool_items:
            lines.append("")
            lines.append("Tool observations:")
            lines.extend(f"- {item}" for item in self.tool_items)
        return "\n".join(lines)
