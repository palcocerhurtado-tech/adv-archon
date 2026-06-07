from __future__ import annotations

from dataclasses import dataclass

from adv_archon.core.architect_brain import build_architect_brain_section


@dataclass(frozen=True, slots=True)
class VoiceIntent:
    action: str
    spoken_summary: str
    detail_prompt: str = ""


def parse_live_turns(text: str, *, default: int = 3, maximum: int = 20) -> int | None:
    """Return the number of voice turns requested by a desktop /live command."""
    parts = text.strip().split()
    if not parts or parts[0].casefold() != "/live":
        return None
    if len(parts) == 1:
        return default
    if len(parts) > 2:
        raise ValueError("Uso: /live [número_de_turnos]")
    try:
        requested = int(parts[1])
    except ValueError as exc:
        raise ValueError("Uso: /live [número_de_turnos]") from exc
    return max(1, min(maximum, requested))


def classify_voice_intent(text: str) -> VoiceIntent | None:
    normalized = _normalize(text)
    if any(token in normalized for token in ("crea un expediente", "nuevo expediente")):
        return VoiceIntent(
            action="new_expediente",
            spoken_summary="Abro el flujo de expedientes para crear uno nuevo.",
        )
    if any(token in normalized for token in ("analiza este plano", "analiza el plano")):
        return VoiceIntent(
            action="analyze_plan",
            spoken_summary=(
                "Prepararé el análisis del expediente activo con el plano adjunto."
            ),
            detail_prompt=(
                "Analiza el expediente activo y su plano adjunto. Resume viabilidad, "
                "riesgos urbanísticos, fuentes y próximos pasos."
            ),
        )
    if any(token in normalized for token in ("exporta el informe", "abre el informe")):
        return VoiceIntent(
            action="export_report",
            spoken_summary="Busco el informe del expediente activo.",
        )
    if any(token in normalized for token in ("explicame los riesgos", "explícame los riesgos")):
        return VoiceIntent(
            action="explain_risks",
            spoken_summary="Te resumo los riesgos principales del expediente.",
            detail_prompt=(
                "Explica los riesgos principales del expediente activo en lenguaje de "
                "despacho: qué está condicionado, qué falta verificar y qué decisión "
                "preliminar tomarías."
            ),
        )
    if "que falta" in normalized and "viable" in normalized:
        return VoiceIntent(
            action="missing_viability",
            spoken_summary="Te indico qué falta para poder defender la viabilidad.",
            detail_prompt=(
                "Indica qué información falta para que el expediente activo pueda "
                "considerarse viable: ordenanza exacta, compatibilidad de uso, afecciones, "
                "plano, fuentes y próximos pasos."
            ),
        )
    return None


def build_voice_system_prompt(expediente_context: str = "") -> str:
    context = expediente_context.strip()
    architect_brain = build_architect_brain_section(compact=True)
    base = (
        "Eres ADV ARCHON en modo voz local dentro de una app de escritorio para "
        "despachos de arquitectura. Responde siempre en español, breve y con criterio. "
        "Si hay expediente activo, úsalo como contexto principal. "
        "Devuelve dos bloques: 'VOZ:' con una respuesta de una o dos frases para leer "
        "en alto, y 'DETALLE:' con los pasos, riesgos o fuentes útiles para pantalla."
    )
    base = f"{base}\n\n{architect_brain}"
    if not context:
        return base
    return f"{base}\n\nContexto del expediente activo:\n{context}"


def split_voice_response(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        return "", ""
    marker = "DETALLE:"
    upper = stripped.upper()
    detail_idx = upper.find(marker)
    if detail_idx < 0:
        voice = stripped
        if voice.upper().startswith("VOZ:"):
            voice = voice[4:].strip()
        return voice, stripped
    voice = stripped[:detail_idx].strip()
    detail = stripped[detail_idx + len(marker):].strip()
    if voice.upper().startswith("VOZ:"):
        voice = voice[4:].strip()
    screen = f"{voice}\n\nDetalle:\n{detail}".strip() if detail else voice
    return voice or detail, screen


def _normalize(text: str) -> str:
    table = str.maketrans("áéíóúüñ", "aeiouun")
    return " ".join(text.casefold().translate(table).split())
