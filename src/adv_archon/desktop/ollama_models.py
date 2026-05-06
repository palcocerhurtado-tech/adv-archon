from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OllamaModelInfo:
    name: str
    size_bytes: int | None = None

    @property
    def display_label(self) -> str:
        if self.size_bytes is None:
            return self.name
        return f"{self.name} · {format_model_size(self.size_bytes)}"


def format_model_size(size_bytes: int | None) -> str:
    if size_bytes is None or size_bytes <= 0:
        return "tamaño desconocido"
    gb = size_bytes / (1024**3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    mb = size_bytes / (1024**2)
    return f"{mb:.0f} MB"


def parse_ollama_tags(payload: dict[str, Any]) -> list[OllamaModelInfo]:
    raw_models = payload.get("models", [])
    if not isinstance(raw_models, list):
        return []
    models: list[OllamaModelInfo] = []
    for raw in raw_models:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or raw.get("model") or "").strip()
        if not name:
            continue
        size = raw.get("size")
        models.append(
            OllamaModelInfo(
                name=name,
                size_bytes=size if isinstance(size, int) else None,
            )
        )
    return sorted(models, key=lambda item: item.name.lower())


def fetch_ollama_models(base_url: str, *, timeout: float = 3.0) -> list[OllamaModelInfo]:
    import httpx

    with httpx.Client(timeout=timeout) as client:
        response = client.get(f"{base_url.rstrip('/')}/api/tags")
        response.raise_for_status()
    return parse_ollama_tags(response.json())


__all__ = [
    "OllamaModelInfo",
    "fetch_ollama_models",
    "format_model_size",
    "parse_ollama_tags",
]
