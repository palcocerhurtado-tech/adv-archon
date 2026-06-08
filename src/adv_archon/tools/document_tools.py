from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from adv_archon.core.document_draft import DocumentDraft
from adv_archon.core.document_store import DocumentStore


class DocumentTools:
    """Agent tools for editable office drafts and professional exports."""

    def __init__(self, store: DocumentStore, *, output_dir: Path | None = None) -> None:
        self._store = store
        self._output_dir = output_dir or Path.home() / "Desktop"

    def update_pdf_draft(
        self,
        draft_id: str = "",
        draft: dict[str, Any] | None = None,
        title: str = "",
        kind: str = "general",
        executive_summary: str = "",
        sections: list[dict[str, Any]] | None = None,
        section_id: str = "",
        section_content: str = "",
    ) -> dict[str, Any]:
        """Create or update an editable draft before exporting to PDF/DOCX/XLSX."""

        current = self._resolve_draft(draft_id=draft_id, draft=draft)
        if current is None:
            current = DocumentDraft.from_dict(
                {
                    "id": draft_id,
                    "kind": kind,
                    "title": title or "Documento ADV ARCHON",
                    "executive_summary": executive_summary,
                    "sections": sections or [],
                }
            )
        else:
            payload = current.to_dict()
            if title:
                payload["title"] = title
            if kind:
                payload["kind"] = kind
            if executive_summary:
                payload["executive_summary"] = executive_summary
            if sections is not None:
                payload["sections"] = sections
            current = DocumentDraft.from_dict(payload)
        if section_id:
            current = current.with_section_update(section_id, section_content)
        saved = self._store.save_draft(current)
        return {
            "ok": True,
            "draft_id": saved.id,
            "draft": saved.to_dict(),
            "message": "Borrador actualizado. Revisa antes de exportar.",
        }

    def generate_docx(
        self,
        draft_id: str = "",
        draft: dict[str, Any] | None = None,
        output_path: str = "",
    ) -> dict[str, Any]:
        from adv_archon.core.docx_generator import generate_expediente_docx

        resolved = self._require_draft(draft_id=draft_id, draft=draft)
        output = self._resolve_output_path(output_path, resolved, ".docx")
        generate_expediente_docx(resolved, output)
        if resolved.id:
            self._store.mark_exported(resolved.id, "docx", output)
        return {"ok": True, "draft_id": resolved.id, "output_path": str(output)}

    def generate_xlsx(
        self,
        draft_id: str = "",
        draft: dict[str, Any] | None = None,
        output_path: str = "",
    ) -> dict[str, Any]:
        from adv_archon.core.xlsx_generator import generate_expediente_xlsx

        resolved = self._require_draft(draft_id=draft_id, draft=draft)
        output = self._resolve_output_path(output_path, resolved, ".xlsx")
        generate_expediente_xlsx(resolved, output)
        if resolved.id:
            self._store.mark_exported(resolved.id, "xlsx", output)
        return {"ok": True, "draft_id": resolved.id, "output_path": str(output)}

    def generate_pdf(
        self,
        draft_id: str = "",
        draft: dict[str, Any] | None = None,
        output_path: str = "",
    ) -> dict[str, Any]:
        from adv_archon.core.pdf_generator_v2 import generate_draft_pdf

        resolved = self._require_draft(draft_id=draft_id, draft=draft)
        output = self._resolve_output_path(output_path, resolved, ".pdf")
        generate_draft_pdf(resolved, output)
        if resolved.id:
            self._store.mark_exported(resolved.id, "pdf", output)
        return {"ok": True, "draft_id": resolved.id, "output_path": str(output)}

    def _resolve_draft(
        self,
        *,
        draft_id: str,
        draft: dict[str, Any] | None,
    ) -> DocumentDraft | None:
        if draft is not None:
            return self._store.save_draft(DocumentDraft.from_dict(draft))
        if draft_id:
            return self._store.get_draft(draft_id)
        return None

    def _require_draft(
        self,
        *,
        draft_id: str,
        draft: dict[str, Any] | None,
    ) -> DocumentDraft:
        resolved = self._resolve_draft(draft_id=draft_id, draft=draft)
        if resolved is None:
            raise ValueError("No se ha encontrado el borrador indicado.")
        return resolved

    def _resolve_output_path(
        self,
        output_path: str,
        draft: DocumentDraft,
        suffix: str,
    ) -> Path:
        if output_path.strip():
            return Path(output_path).expanduser()
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        safe = _slugify(draft.title)
        return self._output_dir / f"adv_archon_{safe}_{stamp}{suffix}"


def build_document_tool_specs(tools: DocumentTools) -> list[dict[str, Any]]:
    draft_schema = {
        "type": "object",
        "description": "Editable DocumentDraft payload.",
    }
    return [
        {
            "name": "update_pdf_draft",
            "description": (
                "Create or update an editable professional draft before exporting. "
                "Use this for reports, deliverables, research documents and PDF/DOCX drafts."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string"},
                    "draft": draft_schema,
                    "title": {"type": "string"},
                    "kind": {"type": "string"},
                    "executive_summary": {"type": "string"},
                    "sections": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "section_id": {"type": "string"},
                    "section_content": {"type": "string"},
                },
            },
            "fn": tools.update_pdf_draft,
        },
        {
            "name": "generate_docx",
            "description": (
                "Export an editable ADV ARCHON draft to a professional DOCX file. "
                "Use when the user asks for Word, DOCX or an editable written delivery."
            ),
            "schema": _export_schema(draft_schema),
            "fn": tools.generate_docx,
        },
        {
            "name": "generate_xlsx",
            "description": (
                "Export an ADV ARCHON draft to an auditable XLSX workbook with sources, "
                "risks, tables and traceability. Use for Excel deliverables."
            ),
            "schema": _export_schema(draft_schema),
            "fn": tools.generate_xlsx,
        },
        {
            "name": "generate_pdf",
            "description": (
                "Export an editable ADV ARCHON draft to a professional preliminary PDF."
            ),
            "schema": _export_schema(draft_schema),
            "fn": tools.generate_pdf,
        },
    ]


def _export_schema(draft_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "draft_id": {"type": "string"},
            "draft": draft_schema,
            "output_path": {"type": "string"},
        },
    }


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return slug[:80] or "documento"


__all__ = ["DocumentTools", "build_document_tool_specs"]
