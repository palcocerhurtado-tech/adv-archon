from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class DraftSection:
    id: str
    title: str
    content: str
    level: int = 1
    include_in_report: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "level": self.level,
            "include_in_report": self.include_in_report,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DraftSection:
        return cls(
            id=str(data.get("id") or ""),
            title=str(data.get("title") or ""),
            content=str(data.get("content") or ""),
            level=max(1, int(data.get("level") or 1)),
            include_in_report=bool(data.get("include_in_report", True)),
        )


@dataclass(frozen=True, slots=True)
class DraftTable:
    id: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    include_in_report: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows],
            "include_in_report": self.include_in_report,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DraftTable:
        columns = tuple(str(item) for item in _as_sequence(data.get("columns")))
        rows = tuple(
            tuple(str(cell) for cell in _as_sequence(row))
            for row in _as_sequence(data.get("rows"))
        )
        return cls(
            id=str(data.get("id") or ""),
            title=str(data.get("title") or ""),
            columns=columns,
            rows=rows,
            include_in_report=bool(data.get("include_in_report", True)),
        )


@dataclass(frozen=True, slots=True)
class DraftSource:
    id: str
    title: str
    source_type: str
    reference: str = ""
    url: str = ""
    consulted_at: str = ""
    result: str = ""
    confidence: str = ""
    official: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source_type": self.source_type,
            "reference": self.reference,
            "url": self.url,
            "consulted_at": self.consulted_at,
            "result": self.result,
            "confidence": self.confidence,
            "official": self.official,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DraftSource:
        return cls(
            id=str(data.get("id") or ""),
            title=str(data.get("title") or ""),
            source_type=str(data.get("source_type") or ""),
            reference=str(data.get("reference") or ""),
            url=str(data.get("url") or ""),
            consulted_at=str(data.get("consulted_at") or ""),
            result=str(data.get("result") or ""),
            confidence=str(data.get("confidence") or ""),
            official=bool(data.get("official", False)),
        )


@dataclass(frozen=True, slots=True)
class DocumentDraft:
    title: str
    client_name: str = ""
    project_name: str = ""
    municipality: str = ""
    cadastral_ref: str = ""
    verdict: str = "REVISAR"
    executive_summary: str = ""
    id: str = ""
    expediente_id: str = ""
    kind: str = "expediente"
    sections: tuple[DraftSection, ...] = ()
    tables: tuple[DraftTable, ...] = ()
    sources: tuple[DraftSource, ...] = ()
    warnings: tuple[str, ...] = ()
    next_steps: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "expediente_id": self.expediente_id,
            "kind": self.kind,
            "title": self.title,
            "client_name": self.client_name,
            "project_name": self.project_name,
            "municipality": self.municipality,
            "cadastral_ref": self.cadastral_ref,
            "verdict": self.verdict,
            "executive_summary": self.executive_summary,
            "sections": [section.to_dict() for section in self.sections],
            "tables": [table.to_dict() for table in self.tables],
            "sources": [source.to_dict() for source in self.sources],
            "warnings": list(self.warnings),
            "next_steps": list(self.next_steps),
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    def with_id(self, draft_id: str) -> DocumentDraft:
        return replace(self, id=draft_id)

    def with_section_update(self, section_id: str, content: str) -> DocumentDraft:
        sections = tuple(
            replace(section, content=content) if section.id == section_id else section
            for section in self.sections
        )
        return replace(self, sections=sections)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentDraft:
        return cls(
            id=str(data.get("id") or ""),
            expediente_id=str(data.get("expediente_id") or ""),
            kind=str(data.get("kind") or "expediente"),
            title=str(data.get("title") or "Documento ADV ARCHON"),
            client_name=str(data.get("client_name") or ""),
            project_name=str(data.get("project_name") or ""),
            municipality=str(data.get("municipality") or ""),
            cadastral_ref=str(data.get("cadastral_ref") or ""),
            verdict=str(data.get("verdict") or "REVISAR"),
            executive_summary=str(data.get("executive_summary") or ""),
            sections=tuple(
                DraftSection.from_dict(item)
                for item in _as_dict_sequence(data.get("sections"))
            ),
            tables=tuple(
                DraftTable.from_dict(item)
                for item in _as_dict_sequence(data.get("tables"))
            ),
            sources=tuple(
                DraftSource.from_dict(item)
                for item in _as_dict_sequence(data.get("sources"))
            ),
            warnings=tuple(str(item) for item in _as_sequence(data.get("warnings"))),
            next_steps=tuple(str(item) for item in _as_sequence(data.get("next_steps"))),
            metadata=_metadata(data.get("metadata")),
        )

    @classmethod
    def from_json(cls, raw: str) -> DocumentDraft:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("DocumentDraft JSON must contain an object")
        return cls.from_dict(data)


def build_expediente_draft(expediente: Any) -> DocumentDraft:
    """Build a conservative editable draft from an expediente-like object."""

    title = str(getattr(expediente, "title", "") or "Informe urbanistico")
    municipality = str(getattr(expediente, "municipality", "") or "")
    cadastral_ref = str(getattr(expediente, "cadastral_ref", "") or "")
    analysis = str(getattr(expediente, "analysis_result", "") or "")
    notes = str(getattr(expediente, "notes", "") or "")
    summary = analysis[:900] if analysis else "Borrador pendiente de analisis tecnico."
    sections = [
        DraftSection(
            id="executive-summary",
            title="Resumen ejecutivo",
            content=summary,
        ),
        DraftSection(
            id="technical-analysis",
            title="Analisis tecnico preliminar",
            content=analysis or notes or "Pendiente de completar por ARCHON.",
        ),
    ]
    if notes:
        sections.append(DraftSection(id="notes", title="Notas del expediente", content=notes))
    return DocumentDraft(
        id=str(getattr(expediente, "document_draft_id", "") or ""),
        expediente_id=str(getattr(expediente, "id", "") or ""),
        title=title,
        project_name=title,
        municipality=municipality,
        cadastral_ref=cadastral_ref,
        verdict=str(getattr(expediente, "status", "") or "REVISAR").upper(),
        executive_summary=summary,
        sections=tuple(sections),
        tables=(
            DraftTable(
                id="expediente-data",
                title="Datos del expediente",
                columns=("Campo", "Valor"),
                rows=(
                    ("Direccion", str(getattr(expediente, "address", "") or "")),
                    ("Municipio", municipality),
                    ("Referencia catastral", cadastral_ref),
                    ("Tipo de actuacion", str(getattr(expediente, "case_type", "") or "")),
                ),
            ),
        ),
        warnings=("Informe preliminar no vinculante juridicamente.",),
        next_steps=("Revision tecnica por arquitecto antes de presentar.",),
    )


def build_research_draft(result: Any) -> DocumentDraft:
    """Build an editable delivery draft from a ResearchWorkbenchResult-like object."""

    question = str(getattr(result, "question", "") or "Investigacion ADV ARCHON")
    synthesis = str(getattr(result, "synthesis", "") or "Pendiente de sintetizar.")
    subquestions = tuple(str(item) for item in getattr(result, "subquestions", ()) or ())
    formulas = tuple(str(item) for item in getattr(result, "formula_candidates", ()) or ())
    gaps = tuple(str(item) for item in getattr(result, "gaps", ()) or ())
    next_steps = tuple(str(item) for item in getattr(result, "next_steps", ()) or ())
    evidences = tuple(getattr(result, "evidences", ()) or ())
    sections = [
        DraftSection(
            id="synthesis",
            title="Sintesis de investigacion",
            content=synthesis,
        ),
        DraftSection(
            id="method",
            title="Metodo y subpreguntas",
            content="\n".join(f"- {item}" for item in subquestions)
            or "Sin subpreguntas registradas.",
        ),
    ]
    if formulas:
        sections.append(
            DraftSection(
                id="formulas",
                title="Formulas y metodos detectados",
                content="\n".join(f"- {item}" for item in formulas),
            )
        )
    if gaps:
        sections.append(
            DraftSection(
                id="validation",
                title="Validaciones pendientes",
                content="\n".join(f"- {item}" for item in gaps),
            )
        )
    sources = tuple(
        DraftSource(
            id=str(getattr(evidence, "id", "") or f"src-{index}"),
            title=str(getattr(evidence, "title", "") or "Fuente web"),
            source_type="web",
            url=str(getattr(evidence, "url", "") or ""),
            result=str(getattr(evidence, "excerpt", "") or "")[:500],
            confidence="media",
            official=False,
        )
        for index, evidence in enumerate(evidences, start=1)
    )
    return DocumentDraft(
        kind="research",
        title=f"Entrega investigada - {question[:70]}",
        project_name=question,
        verdict="BORRADOR",
        executive_summary=synthesis,
        sections=tuple(sections),
        sources=sources,
        warnings=(
            "Las fuentes web deben revisarse antes de entregar el documento final.",
        ),
        next_steps=next_steps or ("Revisar citas, formulas y supuestos antes de entregar.",),
        metadata={"question": question, "evidence_count": len(sources)},
    )


def _as_sequence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def _as_dict_sequence(value: Any) -> tuple[dict[str, Any], ...]:
    return tuple(item for item in _as_sequence(value) if isinstance(item, dict))


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}
