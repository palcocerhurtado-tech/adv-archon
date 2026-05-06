from __future__ import annotations

from adv_archon.desktop.ollama_models import (
    format_model_size,
    parse_ollama_tags,
)


def test_parse_ollama_tags_sorts_and_formats_models() -> None:
    models = parse_ollama_tags(
        {
            "models": [
                {"name": "zeta:latest", "size": 2 * 1024**3},
                {"model": "alpha:7b", "size": 5 * 1024**3},
                {"name": ""},
            ]
        }
    )

    assert [model.name for model in models] == ["alpha:7b", "zeta:latest"]
    assert models[0].display_label == "alpha:7b · 5.0 GB"


def test_format_model_size_handles_unknown_and_small_models() -> None:
    assert format_model_size(None) == "tamaño desconocido"
    assert format_model_size(512 * 1024**2) == "512 MB"
