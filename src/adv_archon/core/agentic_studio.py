from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgenticMode(StrEnum):
    EXPEDIENTE = "expediente"
    DEEP_RESEARCH = "deep_research"
    DOCUMENT = "document"
    PRESENTATION = "presentation"
    SPREADSHEET = "spreadsheet"
    BUDGET = "budget"
    OFFICE_OPS = "office_ops"
    CHAT = "chat"


@dataclass(frozen=True, slots=True)
class AgenticPlaybook:
    mode: AgenticMode
    label: str
    objective: str
    steps: tuple[str, ...]
    tools: tuple[str, ...]
    verification: tuple[str, ...]

    def as_prompt_block(self) -> str:
        return "\n".join(
            [
                f"### {self.label}",
                f"- Objective: {self.objective}",
                "- Steps: " + "; ".join(self.steps),
                "- Tools: " + "; ".join(self.tools),
                "- Verification: " + "; ".join(self.verification),
            ]
        )


PLAYBOOKS: dict[AgenticMode, AgenticPlaybook] = {
    AgenticMode.EXPEDIENTE: AgenticPlaybook(
        mode=AgenticMode.EXPEDIENTE,
        label="Expediente urbanistico",
        objective="Llevar un expediente desde datos iniciales hasta informe revisable.",
        steps=(
            "detectar faltas",
            "consultar fuentes oficiales",
            "analizar PGOU y afecciones",
            "pedir revision humana cuando proceda",
            "exportar informe",
        ),
        tools=(
            "GeoTools",
            "Catastro",
            "PGOU store",
            "Autopilot",
            "Compliance Judge",
            "PDF generator",
        ),
        verification=(
            "dato oficial separado de inferencia",
            "advertencias juridicas visibles",
            "fuentes trazables",
        ),
    ),
    AgenticMode.DEEP_RESEARCH: AgenticPlaybook(
        mode=AgenticMode.DEEP_RESEARCH,
        label="Investigacion profunda",
        objective="Resolver preguntas complejas con busqueda, lectura y sintesis trazable.",
        steps=(
            "descomponer subpreguntas",
            "buscar fuentes",
            "leer fuentes principales",
            "extraer evidencias",
            "comparar contradicciones",
            "sintetizar",
        ),
        tools=("web_search", "web_fetch", "knowledge_search", "read_file"),
        verification=(
            "fuentes citadas",
            "fecha y autoridad de fuente",
            "lagunas explicitas",
            "conclusiones no apoyadas marcadas",
        ),
    ),
    AgenticMode.DOCUMENT: AgenticPlaybook(
        mode=AgenticMode.DOCUMENT,
        label="Documento entregable",
        objective="Crear un documento maquetado a partir de archivos, investigacion o briefing.",
        steps=(
            "leer materiales",
            "crear indice",
            "redactar borrador",
            "maquetar",
            "revisar",
            "exportar",
        ),
        tools=("read_file", "web_search", "web_fetch", "python-docx", "PDF generator"),
        verification=("estructura completa", "ortografia", "fuentes", "formato de entrega"),
    ),
    AgenticMode.PRESENTATION: AgenticPlaybook(
        mode=AgenticMode.PRESENTATION,
        label="Presentacion",
        objective="Crear una presentacion clara para cliente, clase o despacho.",
        steps=(
            "definir audiencia",
            "guion narrativo",
            "diapositivas",
            "notas del presentador",
            "revision visual",
            "exportar PPTX",
        ),
        tools=("read_file", "web_fetch", "python-pptx"),
        verification=("mensaje por slide", "jerarquia visual", "duracion", "fuentes"),
    ),
    AgenticMode.SPREADSHEET: AgenticPlaybook(
        mode=AgenticMode.SPREADSHEET,
        label="Hoja de calculo",
        objective="Resolver calculos y construir tablas auditables.",
        steps=(
            "identificar variables",
            "definir formulas",
            "calcular con Python",
            "crear XLSX",
            "validar unidades",
            "exportar resumen",
        ),
        tools=("python_exec", "openpyxl", "calcular_pem", "edificabilidad"),
        verification=("formulas visibles", "unidades", "supuestos", "comprobacion numerica"),
    ),
    AgenticMode.BUDGET: AgenticPlaybook(
        mode=AgenticMode.BUDGET,
        label="Presupuesto o propuesta",
        objective="Preparar presupuesto, PEM o propuesta profesional para cliente.",
        steps=(
            "definir alcance",
            "calcular partidas",
            "separar supuestos",
            "redactar propuesta",
            "exportar PDF/XLSX",
        ),
        tools=("calcular_pem", "exportar_pem_pdf", "openpyxl", "PDF generator"),
        verification=("no confundir PEM con oferta contractual", "IVA y honorarios separados"),
    ),
    AgenticMode.OFFICE_OPS: AgenticPlaybook(
        mode=AgenticMode.OFFICE_OPS,
        label="Operacion diaria",
        objective="Ayudar con briefing, correo, agenda, tareas y gestion del estudio.",
        steps=("leer contexto", "priorizar", "proponer accion", "ejecutar con permisos"),
        tools=("calendar", "gmail", "task_list", "notes", "memory"),
        verification=("acciones supervisadas", "sin enviar ni borrar sin permiso"),
    ),
    AgenticMode.CHAT: AgenticPlaybook(
        mode=AgenticMode.CHAT,
        label="Chat contextual",
        objective="Responder de forma breve cuando no hace falta ejecutar un flujo completo.",
        steps=("entender", "responder", "proponer siguiente accion si aporta valor"),
        tools=("memory", "knowledge_search"),
        verification=("no sobreactuar", "no inventar herramientas usadas"),
    ),
}


def classify_agentic_request(text: str) -> AgenticPlaybook:
    normalized = _normalize(text)
    if _contains_any(
        normalized,
        ("expediente", "pgou", "catastro", "parcela", "licencia", "urbanistico"),
    ):
        return PLAYBOOKS[AgenticMode.EXPEDIENTE]
    if _contains_any(
        normalized,
        ("investiga", "investigacion", "busca en internet", "fuentes", "estado del arte"),
    ):
        return PLAYBOOKS[AgenticMode.DEEP_RESEARCH]
    if _contains_any(normalized, ("presentacion", "diapositiva", "ppt", "pptx")):
        return PLAYBOOKS[AgenticMode.PRESENTATION]
    if _contains_any(
        normalized,
        ("excel", "xlsx", "hoja de calculo", "tabla", "formula", "formulas"),
    ):
        return PLAYBOOKS[AgenticMode.SPREADSHEET]
    if _contains_any(normalized, ("presupuesto", "pem", "propuesta", "honorarios")):
        return PLAYBOOKS[AgenticMode.BUDGET]
    if _contains_any(normalized, ("documento", "docx", "trabajo", "maquetado", "entrega")):
        return PLAYBOOKS[AgenticMode.DOCUMENT]
    if _contains_any(normalized, ("agenda", "correo", "email", "reunion", "briefing")):
        return PLAYBOOKS[AgenticMode.OFFICE_OPS]
    return PLAYBOOKS[AgenticMode.CHAT]


def build_agentic_studio_section() -> str:
    blocks = [
        "## Agentic Studio",
        (
            "- Core rule: decide the work mode before answering. If the task is complex, "
            "use a playbook with tools, evidence, verification and an exportable result."
        ),
        (
            "- Do not rely on the language model for exact arithmetic, spreadsheet formulas, "
            "legal citations or source lookup when a tool can verify it."
        ),
        (
            "- For school/work deliverables: read attachments, research when needed, create "
            "a structured draft, verify, then generate the requested artifact."
        ),
    ]
    for mode in (
        AgenticMode.EXPEDIENTE,
        AgenticMode.DEEP_RESEARCH,
        AgenticMode.DOCUMENT,
        AgenticMode.PRESENTATION,
        AgenticMode.SPREADSHEET,
        AgenticMode.BUDGET,
    ):
        blocks.append(PLAYBOOKS[mode].as_prompt_block())
    return "\n".join(blocks)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _normalize(text: str) -> str:
    table = str.maketrans("áéíóúüñ", "aeiouun")
    return " ".join(text.casefold().translate(table).split())


__all__ = [
    "AgenticMode",
    "AgenticPlaybook",
    "PLAYBOOKS",
    "build_agentic_studio_section",
    "classify_agentic_request",
]
