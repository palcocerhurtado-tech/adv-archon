from __future__ import annotations

import json
import random
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from adv_archon.core.llm_types import LLMMessage

REQUIRED_OUTPUT_FIELDS = ("verdict", "summary", "annotations", "next_steps")

DATASET_SYSTEM_PROMPT = (
    "Eres experto en urbanismo español y revisión preliminar de cumplimiento. "
    "Generas respuestas sintéticas para entrenar un asistente local de arquitectura. "
    "No inventes seguridad jurídica definitiva: separa dato, inferencia y validación pendiente. "
    "Responde solo JSON válido."
)


class LocalChatClient(Protocol):
    def complete(
        self,
        messages: Iterable[LLMMessage],
        *,
        system_prompt: str,
        response_mime_type: str | None = None,
    ) -> tuple[str, Any]: ...


@dataclass(frozen=True, slots=True)
class SyntheticCase:
    template_id: str
    title: str
    municipality: str
    case_type: str
    context: str


@dataclass(frozen=True, slots=True)
class TrainingExample:
    instruction: str
    input: str
    output: str
    template_id: str

    def to_alpaca(self) -> dict[str, str]:
        return {
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
        }


def load_case_templates(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("El fichero de plantillas debe contener una lista JSON.")
    templates = [item for item in data if isinstance(item, dict)]
    if not templates:
        raise ValueError("No hay plantillas válidas para generar dataset.")
    return templates


def instantiate_case(template: dict[str, Any], rng: random.Random) -> SyntheticCase:
    variables = {
        name: _sample_value(spec, rng)
        for name, spec in dict(template.get("variables") or {}).items()
    }
    municipality = str(_sample_value(template.get("municipality", "Madrid"), rng))
    case_type = str(template.get("case_type") or "expediente urbanístico")
    title = str(template.get("title") or template.get("id") or "Caso sintético")
    values = {
        **variables,
        "municipality": municipality,
        "case_type": case_type,
        "title": title,
    }
    scenario = str(template.get("scenario") or "").format(**values)
    official_context = str(template.get("official_context") or "").format(**values)
    risk_hint = str(template.get("risk_hint") or "").format(**values)
    context_parts = [
        f"Municipio: {municipality}",
        f"Tipo de actuación: {case_type}",
        f"Caso: {title}",
        f"Descripción: {scenario}",
    ]
    if official_context:
        context_parts.append(f"Contexto normativo/sectorial disponible: {official_context}")
    if risk_hint:
        context_parts.append(f"Riesgo esperado: {risk_hint}")
    return SyntheticCase(
        template_id=str(template.get("id") or title),
        title=title,
        municipality=municipality,
        case_type=case_type,
        context="\n".join(context_parts),
    )


def build_generation_prompt(case: SyntheticCase) -> str:
    return (
        "Analiza el cumplimiento urbanístico preliminar del siguiente caso. "
        "Devuelve un JSON con campos: verdict, summary, annotations, next_steps, confidence. "
        "Usa verdict como uno de: VIABLE, CONDICIONADO, REVISAR, NO_RECOMENDABLE. "
        "Cada annotation debe incluir status, description y recommendation.\n\n"
        f"{case.context}"
    )


def generate_training_examples(
    *,
    templates: Sequence[dict[str, Any]],
    client: LocalChatClient,
    count: int,
    seed: int = 42,
    max_attempts_factor: int = 4,
) -> list[TrainingExample]:
    rng = random.Random(seed)
    target = max(0, int(count))
    attempts = max(target, 1) * max(1, int(max_attempts_factor))
    examples: list[TrainingExample] = []
    for _ in range(attempts):
        if len(examples) >= target:
            break
        template = rng.choice(list(templates))
        case = instantiate_case(template, rng)
        prompt = build_generation_prompt(case)
        text, _usage = client.complete(
            [LLMMessage(role="user", content=prompt)],
            system_prompt=DATASET_SYSTEM_PROMPT,
            response_mime_type="application/json",
        )
        parsed = parse_model_json(text)
        if not is_valid_analysis(parsed):
            continue
        examples.append(
            TrainingExample(
                instruction="Analiza el cumplimiento urbanístico:",
                input=case.context,
                output=json.dumps(parsed, ensure_ascii=False, sort_keys=True),
                template_id=case.template_id,
            )
        )
    return examples


def write_jsonl(examples: Sequence[TrainingExample], output_path: Path) -> None:
    output_path = output_path.expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example.to_alpaca(), ensure_ascii=False) + "\n")


def parse_model_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match is None:
                return {}
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
    return data if isinstance(data, dict) else {}


def is_valid_analysis(data: dict[str, Any]) -> bool:
    if not all(field in data for field in REQUIRED_OUTPUT_FIELDS):
        return False
    if not isinstance(data.get("summary"), str) or not str(data["summary"]).strip():
        return False
    if not isinstance(data.get("annotations"), list):
        return False
    if not isinstance(data.get("next_steps"), list):
        return False
    return str(data.get("verdict") or "").upper() in {
        "VIABLE",
        "CONDICIONADO",
        "REVISAR",
        "NO_RECOMENDABLE",
    }


def _sample_value(spec: object, rng: random.Random) -> object:
    if isinstance(spec, list):
        if not spec:
            return ""
        return rng.choice(spec)
    if isinstance(spec, dict):
        if "choices" in spec and isinstance(spec["choices"], list):
            return rng.choice(spec["choices"]) if spec["choices"] else ""
        minimum = spec.get("min")
        maximum = spec.get("max")
        if isinstance(minimum, int) and isinstance(maximum, int):
            return rng.randint(minimum, maximum)
        if isinstance(minimum, int | float) and isinstance(maximum, int | float):
            decimals = int(spec.get("decimals", 2)) if isinstance(spec.get("decimals"), int) else 2
            return round(rng.uniform(float(minimum), float(maximum)), decimals)
    return spec


__all__ = [
    "DATASET_SYSTEM_PROMPT",
    "SyntheticCase",
    "TrainingExample",
    "build_generation_prompt",
    "generate_training_examples",
    "instantiate_case",
    "is_valid_analysis",
    "load_case_templates",
    "parse_model_json",
    "write_jsonl",
]
