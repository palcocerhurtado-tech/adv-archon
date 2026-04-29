from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from adv_archon.core.context import RuntimeContext

PATH_HINT_RE = re.compile(r"(~/|/[\w\-. ]+|[\w\-. ]+\.(?:pdf|docx|xlsx|pptx|md|txt|py|ts|js))")

CODE_KEYWORDS = {
    "codigo",
    "code",
    "script",
    "bug",
    "refactor",
    "repo",
    "python",
    "javascript",
    "typescript",
    "test",
    "tests",
    "funcion",
    "function",
    "api",
}
DOCUMENT_KEYWORDS = {
    "apunte",
    "apuntes",
    "carpeta",
    "carpetas",
    "desktop",
    "pdf",
    "docx",
    "xlsx",
    "pptx",
    "documento",
    "document",
    "escritorio",
    "libro",
    "libros",
    "propuesta",
    "contrato",
    "nota",
    "notas",
    "resume",
    "resumen",
    "lee",
    "leer",
    "estudia",
    "estudiar",
    "repaso",
    "repasar",
    "study",
    "preguntas de repaso",
}
WEB_KEYWORDS = {
    "internet",
    "web",
    "google",
    "biblioteca web",
    "contexto externo",
    "busca",
    "buscar",
    "mercado",
    "tendencias",
    "noticias",
    "latest",
    "actualidad",
    "precio",
}
SHELL_KEYWORDS = {
    "terminal",
    "shell",
    "comando",
    "ejecuta",
    "run",
    "git",
    "ls",
    "pwd",
    "rg",
}
ASSISTANT_KEYWORDS = {
    "recuerdame",
    "recordatorio",
    "recordatorios",
    "agenda",
    "calendario",
    "email",
    "correo",
    "mail",
    "cliente",
    "proyecto",
    "tarea",
    "tareas",
    "reunion",
    "meeting",
    "contacto",
    "contactos",
    "reminders",
    "calendar",
    "notes",
    "notas",
    "notion",
    "obsidian",
    "vault",
    "markdown",
    "gmail",
    "drive",
    "google calendar",
    "google drive",
    "biblioteca web",
    "triage",
    "meeting prep",
    "reunión",
    "briefing ejecutivo",
    "executive brief",
    "prepárame el día",
    "preparame el dia",
    "qué debería hacer hoy",
    "que deberia hacer hoy",
}
KNOWLEDGE_ASSISTANT_KEYWORDS = {
    "nota",
    "notas",
    "notes",
    "notion",
    "obsidian",
    "apunte",
    "apuntes",
    "archivo",
    "archivos",
    "carpeta",
    "carpetas",
    "desktop",
    "escritorio",
    "fichero",
    "ficheros",
    "libro",
    "libros",
    "documento",
    "documentos",
}
BROWSER_KEYWORDS = {
    "navega",
    "navegador",
    "browser",
    "pagina",
    "página",
    "formulario",
    "rellena",
    "captura",
    "screenshot",
    "haz click",
}
CAPABILITY_QUERY_PHRASES = {
    "que puedes hacer",
    "qué puedes hacer",
    "que sabes hacer",
    "qué sabes hacer",
    "en que me puedes ayudar",
    "en qué me puedes ayudar",
    "en que puedes ayudarme",
    "en qué puedes ayudarme",
    "como me puedes ayudar",
    "cómo me puedes ayudar",
    "what can you do",
}
PLAN_KEYWORDS = {
    "plan",
    "organiza",
    "ejecuta",
    "haz",
    "prepara",
    "investiga",
    "analiza",
    "revisa",
    "monta",
    "construye",
}
REASONING_KEYWORDS = {
    "razona",
    "razonamiento",
    "razonar",
    "deduce",
    "deducir",
    "infiere",
    "inferir",
    "step by step",
    "paso a paso",
    "explica por qué",
    "explica porque",
    "por qué funciona",
    "por que funciona",
    "demuestra",
    "demostrar",
    "prueba que",
    "complejidad",
    "algoritmo",
    "optimiza",
    "optimizar",
    "arquitectura",
    "diseña",
    "disenar",
    "tradeoff",
    "trade-off",
    "ventajas y desventajas",
    "pros y contras",
    "deep",
    "think",
    "piensa",
    "reflexiona",
}


COMPLIANCE_KEYWORDS = {
    "plano",
    "planos",
    "normativa",
    "pgou",
    "urbanismo",
    "urbanística",
    "urbanistica",
    "edificio",
    "edificacion",
    "edificación",
    "vivienda",
    "viviendas",
    "proyecto arquitectónico",
    "proyecto arquitectonico",
    "licencia obras",
    "licencia de obras",
    "retranqueo",
    "retranqueos",
    "altura maxima",
    "altura máxima",
    "edificabilidad",
    "ocupacion",
    "ocupación",
    "parcela",
    "uso residencial",
    "calificacion",
    "calificación",
    "cumple normativa",
    "cumplimiento normativa",
    "informe urbanístico",
    "informe urbanistico",
    "arquitecto",
    "arquitectura",
}

_MUNICIPALITY_PATTERNS = [
    re.compile(
        r"(?:en|de|para|del municipio de?|municipio|ciudad de?|ayuntamiento de?)\s+"
        r"([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s\-]{2,40}?)(?:\s*[,\.\n]|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:plano|proyecto|edificio|vivienda|obra)\s+(?:en|de)\s+"
        r"([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s\-]{2,40}?)(?:\s*[,\.\n]|$)",
        re.IGNORECASE,
    ),
]

_KNOWN_MUNICIPALITIES = {
    "madrid", "barcelona", "valencia", "sevilla", "zaragoza", "málaga", "malaga",
    "murcia", "palma", "las palmas", "bilbao", "alicante", "córdoba", "cordoba",
    "valladolid", "vigo", "gijón", "gijon", "granada", "elche", "oviedo",
    "badalona", "terrassa", "jerez", "sabadell", "santa cruz de tenerife",
    "pamplona", "almería", "almeria", "fuenlabrada", "leganés", "leganes",
    "san sebastián", "san sebastian", "donostia", "santander", "burgos",
    "albacete", "alcalá de henares", "alcala de henares", "getafe", "hospitalet",
    "castellón", "castellon", "logroño", "logro", "badajoz", "huelva",
    "salamanca", "marbella", "lleida", "tarragona", "mataró", "mataro",
}


def extract_municipality(text: str) -> str | None:
    """Extract a Spanish municipality name from natural language text."""
    lowered = _normalize(text)
    for muni in _KNOWN_MUNICIPALITIES:
        if muni in lowered:
            return muni.title()
    for pattern in _MUNICIPALITY_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = m.group(1).strip()
            if 3 <= len(candidate) <= 50 and not candidate.lower().startswith(
                ("un ", "una ", "el ", "la ", "los ", "las ", "este ", "esta ")
            ):
                return candidate.strip().title()
    return None


def _normalize(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


IntentCategory = (
    "chat",
    "coding",
    "compliance",
    "documents",
    "web",
    "shell",
    "assistant",
    "research",
)
IntentProfile = ("general", "coding", "work", "personal", "research")


@dataclass(slots=True)
class IntentAnalysis:
    category: str
    profile: str
    needs_plan: bool
    needs_knowledge: bool
    needs_web: bool
    needs_shell: bool
    reasons: list[str]

    def summary(self) -> str:
        flags: list[str] = []
        if self.needs_plan:
            flags.append("operator")
        if self.needs_knowledge:
            flags.append("knowledge")
        if self.needs_web:
            flags.append("web")
        if self.needs_shell:
            flags.append("shell")
        joined_flags = ", ".join(flags) if flags else "direct"
        return f"{self.category} | perfil={self.profile} | modo={joined_flags}"


class IntentRouter:
    def analyze(self, user_input: str, context: RuntimeContext | None = None) -> IntentAnalysis:
        text = user_input.lower().strip()
        reasons: list[str] = []

        if looks_like_capability_query(text):
            return IntentAnalysis(
                category="chat",
                profile="general",
                needs_plan=False,
                needs_knowledge=False,
                needs_web=False,
                needs_shell=False,
                reasons=["consulta sobre capacidades del agente"],
            )

        category_scores = {
            "chat": 0,
            "coding": 0,
            "compliance": 0,
            "documents": 0,
            "web": 0,
            "shell": 0,
            "assistant": 0,
            "research": 0,
        }

        if _contains_any(text, CODE_KEYWORDS):
            category_scores["coding"] += 3
            reasons.append("keywords de codigo")
        if _contains_any(text, COMPLIANCE_KEYWORDS):
            category_scores["compliance"] += 4
            reasons.append("keywords de normativa/plano arquitectónico")
        if _contains_any(text, REASONING_KEYWORDS):
            category_scores["coding"] += 2
            category_scores["research"] += 2
            reasons.append("keywords de razonamiento profundo")
        if _contains_any(text, DOCUMENT_KEYWORDS):
            category_scores["documents"] += 3
            reasons.append("keywords de documentos")
        if _contains_any(text, WEB_KEYWORDS):
            category_scores["web"] += 3
            category_scores["research"] += 2
            reasons.append("keywords de web/actualidad")
        if _contains_any(text, SHELL_KEYWORDS):
            category_scores["shell"] += 3
            reasons.append("keywords de shell")
        if _contains_any(text, ASSISTANT_KEYWORDS):
            category_scores["assistant"] += 3
            reasons.append("keywords de asistente personal")
        if _contains_any(text, BROWSER_KEYWORDS):
            category_scores["assistant"] += 2
            category_scores["web"] += 2
            reasons.append("keywords de navegador/automatizacion")
        if PATH_HINT_RE.search(user_input):
            category_scores["documents"] += 2
            category_scores["coding"] += 1
            reasons.append("hay paths o ficheros en el prompt")
            if category_scores["compliance"] > 0:
                category_scores["compliance"] += 2

        if context is not None and context.git.repo_root is not None:
            category_scores["coding"] += 1
            reasons.append("estas dentro de un repo git")

        if any(token in text for token in {"mercado", "tendencia", "comparativa", "analiza"}):
            category_scores["research"] += 2
        if text.startswith("/") or text.startswith("git "):
            category_scores["shell"] += 3

        category = max(category_scores, key=lambda name: category_scores[name])
        if category_scores[category] == 0:
            category = "chat"
        if (
            category == "chat"
            and context is not None
            and context.active_profile != "general"
            and _contains_any(text, PLAN_KEYWORDS)
        ):
            category = "assistant"
            reasons.append("perfil activo aplicado")

        profile = self._choose_profile(category, text, context)
        needs_plan = category in {"coding", "assistant", "compliance", "research"} or _contains_any(
            text, PLAN_KEYWORDS
        ) or _contains_any(
            text, BROWSER_KEYWORDS
        )
        needs_web = category in {"web", "research"}
        needs_shell = category in {"shell", "coding"}
        needs_knowledge = (
            category in {"documents", "research"}
            or bool(PATH_HINT_RE.search(user_input))
            or _contains_any(text, DOCUMENT_KEYWORDS)
            or _contains_any(text, KNOWLEDGE_ASSISTANT_KEYWORDS)
        )

        return IntentAnalysis(
            category=category,
            profile=profile,
            needs_plan=needs_plan,
            needs_knowledge=needs_knowledge,
            needs_web=needs_web,
            needs_shell=needs_shell,
            reasons=reasons or ["sin señales especiales"],
        )

    @staticmethod
    def _choose_profile(
        category: str,
        text: str,
        context: RuntimeContext | None = None,
    ) -> str:
        if category == "coding":
            return "coding"
        if category == "compliance":
            return "work"
        if category in {"web", "research"}:
            return "research"
        if category == "assistant":
            if any(token in text for token in {"cliente", "trabajo", "propuesta", "proyecto"}):
                return "work"
            if any(token in text for token in {"familia", "casa", "personal"}):
                return "personal"
        if context is not None and context.active_profile != "general":
            return context.active_profile
        return "general"


def _contains_any(text: str, words: set[str]) -> bool:
    for word in words:
        if " " in word:
            if word in text:
                return True
            continue
        if len(word) <= 3:
            if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text):
                return True
            continue
        if word in text:
            return True
    return False


def looks_like_capability_query(text: str) -> bool:
    lowered = text.lower().strip()
    return any(phrase in lowered for phrase in CAPABILITY_QUERY_PHRASES)
