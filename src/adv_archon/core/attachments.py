from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def normalize_attachment_paths(paths: Sequence[Path | str]) -> list[Path]:
    normalized: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return normalized


def format_prompt_with_attachments(
    prompt: str,
    paths: Sequence[Path | str],
    *,
    label: str = "Adjuntos disponibles",
) -> str:
    normalized = normalize_attachment_paths(paths)
    if not normalized:
        return prompt
    referenced = "\n".join(f"- {path}" for path in normalized)
    return f"{prompt}\n\n{label}:\n{referenced}\n\nÁbrelos si resultan útiles."
