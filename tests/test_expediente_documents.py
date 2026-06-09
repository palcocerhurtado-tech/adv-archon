from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from adv_archon.core.document_draft import DocumentDraft, DraftSection
from adv_archon.core.document_store import DocumentStore
from adv_archon.core.expediente_documents import (
    build_document_history,
    ensure_expediente_draft,
    export_expediente_draft,
    save_edited_expediente_draft,
)


def _store(tmp_path: Path) -> DocumentStore:
    return DocumentStore(tmp_path / "documents.db")


def _expediente() -> SimpleNamespace:
    return SimpleNamespace(
        id="exp-1",
        title="Cambio de uso",
        address="Calle Mayor 24",
        municipality="Madrid",
        cadastral_ref="28079...",
        case_type="cambio_uso",
        status="condicionado",
        analysis_result="Analisis preliminar.",
        notes="Nota interna",
    )


def test_ensure_expediente_draft_creates_and_reuses_existing(tmp_path: Path) -> None:
    store = _store(tmp_path)

    created = ensure_expediente_draft(store, _expediente())
    reused = ensure_expediente_draft(store, _expediente())

    assert created.id
    assert reused == created
    assert reused.expediente_id == "exp-1"
    assert reused.title == "Cambio de uso"
    assert len(store.list_drafts(expediente_id="exp-1")) == 1
    store.close()


def test_save_edited_expediente_draft_persists_payload(tmp_path: Path) -> None:
    store = _store(tmp_path)
    draft = ensure_expediente_draft(store, _expediente())
    payload = draft.to_dict()
    payload["title"] = "Cambio de uso actualizado"
    payload["sections"] = [
        {
            "id": "executive-summary",
            "title": "Resumen ejecutivo",
            "content": "Texto editado.",
        }
    ]

    saved = save_edited_expediente_draft(store, payload)
    loaded = store.get_draft(saved.id)

    assert loaded is not None
    assert loaded.title == "Cambio de uso actualizado"
    assert loaded.sections == (
        DraftSection("executive-summary", "Resumen ejecutivo", "Texto editado."),
    )
    store.close()


def test_export_expediente_draft_supports_pdf_docx_and_xlsx(tmp_path: Path) -> None:
    draft = DocumentDraft(
        title="Informe puente",
        expediente_id="exp-1",
        executive_summary="Resumen.",
        sections=(DraftSection("summary", "Resumen", "Texto"),),
    )

    pdf = export_expediente_draft(draft, "pdf", tmp_path)
    docx = export_expediente_draft(draft, ".docx", tmp_path)
    xlsx = export_expediente_draft(draft, "xlsx", tmp_path)

    assert pdf.suffix == ".pdf"
    assert docx.suffix == ".docx"
    assert xlsx.suffix == ".xlsx"
    assert pdf.exists()
    assert docx.exists()
    assert xlsx.exists()


def test_export_expediente_draft_rejects_unknown_kind(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="pdf, docx, xlsx"):
        export_expediente_draft(DocumentDraft(title="Informe"), "txt", tmp_path)


def test_build_document_history_includes_updated_at_when_available(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    first = store.save_draft(
        DocumentDraft(title="Primero", expediente_id="exp-1", kind="expediente")
    )
    second = store.save_draft(
        DocumentDraft(title="Segundo", expediente_id="exp-1", kind="expediente")
    )
    store.save_draft(
        DocumentDraft(title="Otro expediente", expediente_id="exp-2", kind="expediente")
    )

    history = build_document_history(store, "exp-1")

    assert [item["id"] for item in history] == [second.id, first.id]
    assert history[0]["title"] == "Segundo"
    assert history[0]["kind"] == "expediente"
    assert history[0]["updated_at"]
    assert all(item["id"] != "exp-2" for item in history)
    store.close()
