from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OnboardingCard:
    title: str
    body: str
    prompt: str


def recommended_window_size(
    available_width: int,
    available_height: int,
) -> tuple[int, int]:
    width = min(1460, max(1180, int(available_width * 0.9)))
    height = min(940, max(760, int(available_height * 0.84)))
    width = min(width, max(980, available_width - 40))
    height = min(height, max(680, available_height - 40))
    return width, height


def onboarding_cards() -> tuple[OnboardingCard, ...]:
    return (
        OnboardingCard(
            title="Briefing ejecutivo",
            body="Cruza agenda, Gmail, Drive, notas y pendientes para arrancar el día con foco.",
            prompt="dame un briefing ejecutivo del día",
        ),
        OnboardingCard(
            title="Study partner",
            body=(
                "Convierte libros y PDFs en resúmenes, preguntas, planes de "
                "repaso y notas útiles."
            ),
            prompt=(
                "actúa como study partner sobre el último documento relevante y "
                "prepárame un repaso breve"
            ),
        ),
        OnboardingCard(
            title="Operaciones personales",
            body=(
                "Usa memoria, recordatorios, automatizaciones y contexto local "
                "desde lenguaje natural."
            ),
            prompt=(
                "qué debería hacer hoy mezclando agenda, tareas, recordatorios y notas"
            ),
        ),
    )


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


__all__ = [
    "OnboardingCard",
    "build_history_entry",
    "format_sources_summary",
    "merge_recent_items",
    "onboarding_cards",
    "recommended_window_size",
]
