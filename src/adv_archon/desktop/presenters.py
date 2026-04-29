from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def format_sources_summary(
    *,
    tool_names: Sequence[str],
    memory_hits: Sequence[str],
    knowledge_hits: Sequence[str],
) -> str:
    lines = ["Fuentes usadas:"]
    unique_tools = _merge_recent_items((), tool_names, limit=6)
    if unique_tools:
        lines.append("- herramientas: " + ", ".join(unique_tools))
    if memory_hits:
        lines.append("Memoria:")
        lines.extend(f"- {item}" for item in memory_hits[:4])
    if knowledge_hits:
        lines.append("Conocimiento local:")
        lines.extend(f"- {item}" for item in knowledge_hits[:4])
    if len(lines) == 1:
        lines.append("- todavía no hay evidencia visible en este turno")
    return "\n".join(lines)


def build_history_entry(
    prompt: str,
    *,
    attachments: Sequence[Path],
    response_text: str,
) -> str:
    prompt_snippet = _compact(prompt, limit=72)
    response_snippet = _compact(response_text, limit=72)
    lines = [prompt_snippet]
    if attachments:
        labels = ", ".join(path.name or str(path) for path in attachments[:3])
        lines.append(f"Adjuntos: {labels}")
    if response_snippet:
        lines.append(f"Respuesta: {response_snippet}")
    return " | ".join(lines)


def merge_recent_items(
    existing: Sequence[str],
    incoming: Sequence[str],
    *,
    limit: int = 8,
) -> list[str]:
    return _merge_recent_items(existing, incoming, limit=limit)


def _merge_recent_items(
    existing: Sequence[str],
    incoming: Sequence[str],
    *,
    limit: int,
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*incoming, *existing]:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
        if len(merged) >= limit:
            break
    return merged


def _compact(text: str, *, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + "…"

