from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from adv_archon.core.document_draft import DocumentDraft, build_expediente_draft
from adv_archon.core.document_store import DocumentStore
from adv_archon.core.docx_generator import generate_expediente_docx
from adv_archon.core.pdf_generator_v2 import generate_draft_pdf
from adv_archon.core.xlsx_generator import generate_expediente_xlsx


def ensure_expediente_draft(
    store: DocumentStore,
    expediente: Any,
) -> DocumentDraft:
    """Return the existing expediente draft or create a conservative one."""

    expediente_id = str(getattr(expediente, "id", "") or "")
    if not expediente_id:
        raise ValueError("expediente must expose a non-empty id")

    existing = store.list_drafts(expediente_id=expediente_id, kind="expediente")
    if existing:
        return existing[0]

    draft = build_expediente_draft(expediente)
    if not draft.expediente_id:
        draft = DocumentDraft.from_dict({**draft.to_dict(), "expediente_id": expediente_id})
    return store.save_draft(draft)


def save_edited_expediente_draft(
    store: DocumentStore,
    draft_payload: dict[str, Any] | DocumentDraft,
) -> DocumentDraft:
    """Persist an edited expediente draft payload."""

    draft = (
        draft_payload
        if isinstance(draft_payload, DocumentDraft)
        else DocumentDraft.from_dict(draft_payload)
    )
    return store.save_draft(draft)


def export_expediente_draft(
    draft: DocumentDraft,
    kind: str,
    output_dir: Path,
    archon_logo_path: Path | None = None,
) -> Path:
    """Export a draft to PDF, DOCX or XLSX in output_dir."""

    normalized = kind.lower().lstrip(".")
    if normalized not in {"pdf", "docx", "xlsx"}:
        raise ValueError("kind must be one of: pdf, docx, xlsx")

    output_path = _draft_output_path(draft, output_dir, normalized)
    if normalized == "pdf":
        return generate_draft_pdf(
            draft,
            output_path,
            archon_logo_path=archon_logo_path,
        )
    if normalized == "docx":
        return generate_expediente_docx(
            draft,
            output_path,
            archon_logo_path=archon_logo_path,
        )
    return generate_expediente_xlsx(draft, output_path)


def build_document_history(
    store: DocumentStore,
    expediente_id: str,
) -> list[dict[str, str]]:
    """Build a compact draft history for an expediente."""

    history: list[dict[str, str]] = []
    for draft in store.list_drafts(expediente_id=expediente_id):
        item = {
            "id": draft.id,
            "title": draft.title,
            "kind": draft.kind,
        }
        if draft.id:
            record = store.get_record(draft.id)
            if record is not None and record.updated_at:
                item["updated_at"] = record.updated_at
        history.append(item)
    return history


def _draft_output_path(draft: DocumentDraft, output_dir: Path, suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_dir.expanduser() / f"adv_archon_{_slugify(draft.title)}_{stamp}.{suffix}"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return slug[:80] or "expediente"


__all__ = [
    "build_document_history",
    "ensure_expediente_draft",
    "export_expediente_draft",
    "save_edited_expediente_draft",
]
