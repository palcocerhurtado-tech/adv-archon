from __future__ import annotations

import json
import random
from pathlib import Path

from adv_archon.core.training_data import (
    generate_training_examples,
    instantiate_case,
    is_valid_analysis,
    load_case_templates,
    parse_model_json,
    write_jsonl,
)


class _FakeLocalClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls = 0

    def complete(self, *_args, **_kwargs):
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response, object()


def test_case_templates_file_contains_twenty_templates() -> None:
    templates = load_case_templates(Path("data/case_templates.json"))

    assert len(templates) == 20
    assert all(template.get("id") for template in templates)


def test_instantiate_case_renders_variables() -> None:
    templates = load_case_templates(Path("data/case_templates.json"))

    case = instantiate_case(templates[0], random.Random(1))

    assert case.template_id
    assert "Municipio:" in case.context
    assert "Tipo de actuación:" in case.context
    assert "{" not in case.context


def test_parse_model_json_accepts_code_fence() -> None:
    parsed = parse_model_json(
        """```json
        {"verdict": "VIABLE", "summary": "ok", "annotations": [], "next_steps": []}
        ```"""
    )

    assert parsed["verdict"] == "VIABLE"
    assert is_valid_analysis(parsed) is True


def test_generate_training_examples_filters_invalid_responses(tmp_path: Path) -> None:
    templates = load_case_templates(Path("data/case_templates.json"))
    valid = json.dumps(
        {
            "verdict": "CONDICIONADO",
            "summary": "Requiere confirmar ordenanza y habitabilidad.",
            "annotations": [
                {
                    "status": "warning",
                    "description": "Uso residencial pendiente.",
                    "recommendation": "Consultar PGOU y visor municipal.",
                }
            ],
            "next_steps": ["Confirmar ordenanza aplicable."],
            "confidence": "media",
        },
        ensure_ascii=False,
    )
    client = _FakeLocalClient(["no json", valid])

    examples = generate_training_examples(
        templates=templates,
        client=client,
        count=1,
        seed=7,
    )
    output = tmp_path / "dataset.jsonl"
    write_jsonl(examples, output)

    assert len(examples) == 1
    assert client.calls == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["instruction"] == "Analiza el cumplimiento urbanístico:"
    assert "CONDICIONADO" in payload["output"]
