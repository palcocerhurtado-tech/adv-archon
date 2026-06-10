"""Legal & regulatory compliance text for ADV ARCHON (Spain, 2026).

Single source of truth for the disclaimers, privacy notice and AI-transparency
statements that must accompany the product and every document it generates.

Scope covered (the application is **local-first**, so most processing never
leaves the user's device):

* **RGPD** — Reglamento (UE) 2016/679 — y **LOPDGDD** (Ley Orgánica 3/2018):
  protección de datos. El despacho usuario es el *responsable del tratamiento*.
* **Reglamento (UE) 2024/1689** (Reglamento Europeo de Inteligencia Artificial):
  obligaciones de transparencia (art. 50) y supervisión humana.
* **Responsabilidad profesional**: LOE (Ley 38/1999) y normativa urbanística.
  Las salidas son un cribado preliminar, no vinculante, que debe validar un
  técnico competente.
* **Reutilización de información del sector público** (Ley 37/2007 / Directiva
  (UE) 2019/1024): atribución de Catastro, PGOU, BOE y demás fuentes oficiales.

NOTE: This module provides legally-informed templates. A final review by a
licensed lawyer is recommended before commercial distribution.
"""
from __future__ import annotations

# Bump when the legal texts change; surfaced in the UI and document footers.
LEGAL_VERSION = "2026.1"
LEGAL_LAST_UPDATED = "2026-06-10"

# ── AI transparency (Reglamento UE 2024/1689, art. 50) ──────────────────────
AI_TRANSPARENCY_NOTICE = (
    "Este producto incorpora un sistema de inteligencia artificial. Los "
    "contenidos generados (análisis, resúmenes, borradores e informes) son "
    "producidos total o parcialmente por IA y pueden contener errores o "
    "imprecisiones. Conforme al Reglamento (UE) 2024/1689, se informa de que "
    "está interactuando con un sistema de IA y se garantiza la supervisión "
    "humana: ninguna salida debe adoptarse sin revisión de un profesional."
)

# ── Professional / technical disclaimer (no vinculante) ─────────────────────
PROFESSIONAL_DISCLAIMER = (
    "AVISO IMPORTANTE — DOCUMENTO PRELIMINAR NO VINCULANTE. Este documento ha "
    "sido generado como herramienta de apoyo mediante un cribado automatizado y "
    "no constituye un informe técnico ni un dictamen jurídico vinculante, ni "
    "sustituye la consulta urbanística oficial ante la administración "
    "competente (p. ej., cédula o consulta urbanística del Ayuntamiento). Su "
    "contenido debe ser verificado y validado por un técnico competente "
    "(arquitecto/a o aparejador/a colegiado/a) antes de cualquier uso, "
    "presentación o toma de decisiones. ADV ARCHON y sus autores no asumen "
    "responsabilidad por decisiones adoptadas a partir de este documento sin "
    "dicha validación profesional."
)

# ── Privacy notice (RGPD / LOPDGDD) ─────────────────────────────────────────
PRIVACY_NOTICE = (
    "PROTECCIÓN DE DATOS (RGPD / LOPDGDD). ADV ARCHON funciona en modo local: "
    "los expedientes, planos, datos catastrales y demás información se procesan "
    "y almacenan en el dispositivo del usuario y no se transmiten a servidores "
    "de los autores ni a terceros. El despacho o profesional usuario actúa como "
    "responsable del tratamiento de los datos personales que introduzca y debe "
    "garantizar una base de licitud, informar a los interesados y atender sus "
    "derechos de acceso, rectificación, supresión, oposición, limitación y "
    "portabilidad. Se recomienda cifrar el disco del equipo y mantener copias "
    "de seguridad bajo control del responsable."
)

# ── Public-sector data attribution (Ley 37/2007) ────────────────────────────
DATA_SOURCES_ATTRIBUTION = (
    "Fuentes oficiales: la información urbanística y cartográfica puede proceder "
    "de la Dirección General del Catastro, planeamiento municipal (PGOU/PGM), "
    "Boletín Oficial del Estado y otros organismos públicos, reutilizada al "
    "amparo de la Ley 37/2007. La vigencia y exactitud deben confirmarse en la "
    "fuente oficial correspondiente en el momento de uso."
)

# ── AI-generated content seal for documents ─────────────────────────────────
AI_GENERATED_SEAL = (
    "Contenido asistido por IA · Revisión profesional obligatoria"
)


def document_legal_footer() -> str:
    """Compact multi-line legal footer to embed in generated documents."""
    return "\n".join(
        [
            PROFESSIONAL_DISCLAIMER,
            "",
            AI_TRANSPARENCY_NOTICE,
            "",
            PRIVACY_NOTICE,
            "",
            DATA_SOURCES_ATTRIBUTION,
            "",
            f"ADV ARCHON · Aviso legal v{LEGAL_VERSION} ({LEGAL_LAST_UPDATED}).",
        ]
    )


def document_short_disclaimer() -> str:
    """One-line disclaimer for page footers / cover stamps."""
    return (
        "Documento preliminar no vinculante asistido por IA — requiere "
        "validación de técnico competente. ADV ARCHON."
    )


def full_legal_text() -> str:
    """Full legal text for an in-app 'Aviso legal' / onboarding screen."""
    sections = [
        ("Descargo de responsabilidad profesional", PROFESSIONAL_DISCLAIMER),
        ("Transparencia de inteligencia artificial", AI_TRANSPARENCY_NOTICE),
        ("Protección de datos", PRIVACY_NOTICE),
        ("Fuentes de información pública", DATA_SOURCES_ATTRIBUTION),
    ]
    parts = [
        f"ADV ARCHON — Aviso legal y de uso (v{LEGAL_VERSION}, "
        f"{LEGAL_LAST_UPDATED})",
        "",
    ]
    for title, body in sections:
        parts.append(title.upper())
        parts.append(body)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def acceptance_summary() -> str:
    """Short text shown next to a first-run acceptance checkbox."""
    return (
        "He leído y acepto que ADV ARCHON es una herramienta de apoyo que "
        "genera contenido preliminar no vinculante asistido por IA, que debo "
        "validar como técnico competente, y que soy responsable del tratamiento "
        "de los datos que introduzca (RGPD/LOPDGDD)."
    )
