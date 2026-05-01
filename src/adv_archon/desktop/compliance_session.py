"""
ComplianceSession — tracks the lifecycle of an architectural plan compliance check.

States:
  idle         → no active compliance task
  pdf_attached → PDF attached, waiting for municipality confirmation
  running      → compliance analysis underway
  done         → result available, export possible
  error        → analysis failed
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ComplianceState = Literal["idle", "pdf_attached", "running", "done", "error"]

# Spanish municipality name pattern: 2+ word title-case tokens, or known
# keywords like "municipio de X".
_MUNI_PATTERN = re.compile(
    r"""(?:
        municipio\s+de\s+(?P<muni1>[A-ZÁÉÍÓÚÜÑ][a-záéíóúüña-z]+(?:\s+de\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)*)
        |
        [Aa]yuntamiento\s+de\s+(?P<muni2>[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)*)
        |
        [Tt]\.\s*[Mm]\.\s+(?P<muni3>[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)*)
    )""",
    re.VERBOSE,
)


@dataclass
class ComplianceSession:
    state: ComplianceState = "idle"
    pdf_path: Path | None = None
    municipality: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    export_path: str = ""
    error: str = ""

    # ── Transitions ───────────────────────────────────────────────────────────

    def attach_pdf(self, path: Path) -> None:
        self.pdf_path  = path
        self.state     = "pdf_attached"
        self.result    = {}
        self.export_path = ""
        self.error     = ""

    def set_municipality(self, name: str) -> None:
        self.municipality = name.strip()

    def mark_running(self) -> None:
        self.state = "running"

    def mark_done(self, result: dict[str, Any], export_path: str = "") -> None:
        self.result      = result
        self.export_path = export_path
        self.state       = "done"

    def mark_error(self, message: str) -> None:
        self.error = message
        self.state = "error"

    def reset(self) -> None:
        self.state       = "idle"
        self.pdf_path    = None
        self.municipality = ""
        self.result      = {}
        self.export_path  = ""
        self.error       = ""

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def can_run(self) -> bool:
        return (
            self.state == "pdf_attached"
            and self.pdf_path is not None
            and bool(self.municipality)
        )

    @property
    def has_result(self) -> bool:
        return self.state == "done" and bool(self.result)

    @property
    def summary(self) -> str:
        return self.result.get("summary", "")

    @property
    def annotations(self) -> list[dict[str, Any]]:
        return self.result.get("annotations", [])

    @property
    def ok_count(self) -> int:
        return sum(1 for a in self.annotations if a.get("status") == "ok")

    @property
    def warning_count(self) -> int:
        return sum(1 for a in self.annotations if a.get("status") == "warning")

    @property
    def violation_count(self) -> int:
        return sum(1 for a in self.annotations if a.get("status") == "violation")


# ── PDF municipality extractor ────────────────────────────────────────────────

def extract_municipality_hint(pdf_path: Path, *, max_chars: int = 4000) -> str:
    """
    Try to extract a municipality name from the first pages of a PDF.
    Returns the best candidate or "" if nothing found.
    Uses only the stdlib + optional pdfminer; gracefully degrades.
    """
    text = _read_pdf_text(pdf_path, max_chars=max_chars)
    if not text:
        return ""
    match = _MUNI_PATTERN.search(text)
    if match:
        for group in ("muni1", "muni2", "muni3"):
            value = match.group(group)
            if value:
                return value.strip()
    return ""


def _read_pdf_text(pdf_path: Path, *, max_chars: int) -> str:
    # Try pdfminer.six (optional heavy dep)
    try:
        from pdfminer.high_level import extract_text  # type: ignore[import-untyped]
        text = extract_text(str(pdf_path), page_numbers=[0, 1, 2], maxpages=3)
        return (text or "")[:max_chars]
    except ImportError:
        pass
    # Try PyMuPDF (fitz)
    try:
        import fitz  # type: ignore[import-untyped]
        doc = fitz.open(str(pdf_path))
        chunks: list[str] = []
        for page in doc[:3]:
            chunks.append(page.get_text())
            if sum(len(c) for c in chunks) >= max_chars:
                break
        doc.close()
        return "".join(chunks)[:max_chars]
    except ImportError:
        pass
    return ""


# ── Prompt builders ───────────────────────────────────────────────────────────

def build_compliance_prompt(pdf_path: Path, municipality: str) -> str:
    return (
        f"Analiza el cumplimiento normativo del plano arquitectónico '{pdf_path.name}' "
        f"contra el PGOU del municipio de {municipality}. "
        "Usa las herramientas plan_compliance_check y, si el análisis es favorable, "
        "genera el informe exportable con plan_compliance_export."
    )


def build_municipality_ask_prompt(pdf_path: Path, hint: str = "") -> str:
    base = (
        f"He adjuntado el plano arquitectónico '{pdf_path.name}'. "
    )
    if hint:
        base += (
            f"Parece que el proyecto puede estar en el municipio de {hint}. "
            "¿Es correcto? Si no, indícame el municipio real "
            "y analizaré el cumplimiento normativo completo."
        )
    else:
        base += (
            "¿En qué municipio se ubica el proyecto? "
            "Una vez que me lo confirmes, analizaré el cumplimiento normativo "
            "completo contra el PGOU de ese municipio."
        )
    return base
