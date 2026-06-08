"""
Extract structured urbanistic parameters from PGOU text using a local LLM.
Returns a canonical dict suitable for expediente.extracted_params.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from adv_archon.core.llm_types import LLMMessage

log = logging.getLogger(__name__)

_SYSTEM = (
    "Eres un técnico urbanista español experto en lectura de planeamiento. "
    "Extrae parámetros urbanísticos de los fragmentos de PGOU proporcionados. "
    "Responde SOLO con JSON válido y sin comentarios adicionales."
)

_PROMPT = """
MUNICIPIO: {municipality}
CASO: {case_description}

FRAGMENTOS DE PGOU:
{chunks_text}

Extrae los parámetros urbanísticos aplicables. Responde EXACTAMENTE con este JSON:
{{
  "uso_principal": "<uso o vacío>",
  "clasificacion": "<suelo urbano/urbanizable/no urbanizable o vacío>",
  "calificacion": "<zona/ordenanza o vacío>",
  "edificabilidad_m2m2": <número o null>,
  "ocupacion_pct": <número o null>,
  "altura_maxima_m": <número o null>,
  "num_plantas": <número o null>,
  "retranqueos_m": "<descripción o vacío>",
  "usos_permitidos": ["<uso1>", "<uso2>"],
  "usos_prohibidos": ["<uso1>"],
  "condiciones_especiales": "<texto libre o vacío>",
  "articulos_referencia": ["<art.X>"],
  "confianza": "<alta|media|baja>"
}}
""".strip()


class ParamExtractor:
    """Extract structured urban params from PGOU chunks via local LLM."""

    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client

    def extract(
        self,
        chunks: list[str],
        *,
        municipality: str = "",
        case_description: str = "",
    ) -> dict[str, Any]:
        """Return a canonical param dict; never raises."""
        if not chunks:
            return _empty_params()
        chunks_text = "\n\n---\n\n".join(chunks[:6])
        prompt = _PROMPT.format(
            municipality=municipality or "No indicado",
            case_description=case_description or "Análisis urbanístico general",
            chunks_text=chunks_text,
        )
        try:
            raw = self._llm.complete_text(
                [LLMMessage(role="system", content=_SYSTEM),
                 LLMMessage(role="user", content=prompt)]
            )
            return _normalise(_parse_json_block(raw))
        except Exception as exc:
            log.debug("param_extractor failed: %s", exc)
            return _empty_params()


def _empty_params() -> dict[str, Any]:
    return {
        "uso_principal": "",
        "clasificacion": "",
        "calificacion": "",
        "edificabilidad_m2m2": None,
        "ocupacion_pct": None,
        "altura_maxima_m": None,
        "num_plantas": None,
        "retranqueos_m": "",
        "usos_permitidos": [],
        "usos_prohibidos": [],
        "condiciones_especiales": "",
        "articulos_referencia": [],
        "confianza": "baja",
    }


def _parse_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _normalise(raw: dict[str, Any]) -> dict[str, Any]:
    base = _empty_params()
    for key in base:
        if key in raw and raw[key] is not None:
            base[key] = raw[key]
    if not isinstance(base["usos_permitidos"], list):
        base["usos_permitidos"] = []
    if not isinstance(base["usos_prohibidos"], list):
        base["usos_prohibidos"] = []
    if not isinstance(base["articulos_referencia"], list):
        base["articulos_referencia"] = []
    if base["confianza"] not in ("alta", "media", "baja"):
        base["confianza"] = "baja"
    return base
