from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adv_archon.core.expediente import Expediente
    from adv_archon.core.knowledge import KnowledgeStore
    from adv_archon.core.llm import LLMRouter

_SECTIONS = [
    "1. OBJETO DE LA MEMORIA",
    "2. SITUACIÓN Y EMPLAZAMIENTO",
    "3. DESCRIPCIÓN URBANÍSTICA DE LA PARCELA",
    "4. NORMATIVA APLICABLE",
    "5. DESCRIPCIÓN DEL PROYECTO",
    "6. CUADRO DE SUPERFICIES",
    "7. CUMPLIMIENTO NORMATIVO",
    "8. CONCLUSIÓN",
]


def build_memoria_prompt(expediente: Expediente, normativa_context: str) -> str:
    """Build the structured LLM prompt to generate a memoria descriptiva."""
    try:
        ctx = json.loads(expediente.site_context) if expediente.site_context else {}
    except (TypeError, ValueError):
        ctx = {}

    checks = ctx.get("legal_checks", []) if isinstance(ctx, dict) else []
    checks_text = ""
    if checks:
        checks_text = "\n".join(
            f"- {c.get('check', '')}: {c.get('status', '')} — {c.get('note', '')}"
            for c in checks
            if isinstance(c, dict)
        )

    sections_list = "\n".join(f"  {s}" for s in _SECTIONS)
    coords = (
        f"{expediente.latitude}, {expediente.longitude}"
        if expediente.latitude
        else "no disponibles"
    )
    _no_pgou = (
        "No hay normativa PGOU indexada para este municipio. "
        "Indica en la sección 4 que debe consultarse el PGOU vigente."
    )
    normativa_block = normativa_context if normativa_context else _no_pgou

    return f"""Eres un arquitecto técnico español redactando una Memoria Descriptiva profesional.
Genera el documento completo con TODAS estas secciones:
{sections_list}

DATOS DEL EXPEDIENTE (usa estos datos exactos, no inventes nada):
- Título: {expediente.title}
- Dirección: {expediente.address}
- Municipio: {expediente.municipality} ({expediente.province})
- Referencia catastral: {expediente.cadastral_ref or "pendiente"}
- Coordenadas: {coords}
- Estado: {expediente.status}
- Notas del arquitecto: {expediente.notes or "ninguna"}
- Comprobaciones legales:{chr(10) + checks_text if checks_text else " pendientes"}

NORMATIVA INDEXADA DISPONIBLE:
{normativa_block}

INSTRUCCIONES:
- En la sección 4 cita artículos literales si están en la normativa disponible.
- En la sección 7 marca cada punto como CUMPLE / NO CUMPLE / PENDIENTE DE VERIFICAR.
- Tono profesional, primera persona del plural ("se proyecta", "la parcela dispone de").
- Si un dato no está disponible, escribe "Dato pendiente de aportación".
- Formato: cada sección con su título en mayúsculas, párrafos separados."""


def generar_memoria_descriptiva(
    expediente: Expediente,
    llm: LLMRouter,
    knowledge_store: KnowledgeStore | None = None,
) -> str:
    """Generate a full memoria descriptiva using the LLM.

    Searches the knowledge store for normativa of the municipality, then
    builds a grounded prompt and runs it through the LLM.
    Returns the full text of the memoria.
    """
    normativa_context = ""
    if knowledge_store is not None and expediente.municipality:
        try:
            hits = knowledge_store.search(
                f"normativa urbanística {expediente.municipality} PGOU",
                limit=6,
            )
            if hits:
                parts = [f"[{h.title}]\n{h.excerpt}" for h in hits]
                normativa_context = "\n\n---\n\n".join(parts)
        except Exception:
            pass

    prompt = build_memoria_prompt(expediente, normativa_context)

    response = llm.complete(
        [],
        system_prompt=prompt,
        task="document",
    )
    return response.text


# ── Tool wrapper ───────────────────────────────────────────────────────────────

class MemoriaDescriptivaTools:
    def __init__(
        self,
        llm: LLMRouter,
        knowledge_store: KnowledgeStore | None = None,
    ) -> None:
        self._llm = llm
        self._ks = knowledge_store
        self._expediente_store: Any = None

    def set_expediente_store(self, store: Any) -> None:
        self._expediente_store = store

    def redactar_memoria(
        self,
        expediente_id: str,
        guardar_en: str = "",
    ) -> dict[str, Any]:
        """Generate and optionally save a memoria descriptiva for an expediente."""
        if self._expediente_store is None:
            return {"ok": False, "error": "No hay ExpedienteStore configurado."}

        expediente = self._expediente_store.get(expediente_id)
        if expediente is None:
            return {"ok": False, "error": f"Expediente {expediente_id!r} no encontrado."}

        try:
            texto = generar_memoria_descriptiva(
                expediente,
                self._llm,
                knowledge_store=self._ks,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        saved_path = ""
        from pathlib import Path
        safe_title = expediente.title[:40].replace(" ", "_")
        out = (
            Path(guardar_en).expanduser()
            if guardar_en
            else Path.home() / "Desktop" / f"Memoria_{safe_title}.txt"
        )
        out.write_text(texto, encoding="utf-8")
        saved_path = str(out)

        return {
            "ok": True,
            "expediente": expediente.title,
            "memoria": texto,
            "guardada_en": saved_path,
        }
