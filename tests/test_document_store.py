from __future__ import annotations

from adv_archon.core.document_draft import DocumentDraft, DraftSection
from adv_archon.core.document_store import DocumentStore


def test_document_store_saves_lists_and_marks_exports(tmp_path) -> None:
    store = DocumentStore(tmp_path / "documents.db")
    draft = store.save_draft(
        DocumentDraft(
            title="Informe",
            expediente_id="exp-1",
            sections=(DraftSection("summary", "Resumen", "Texto"),),
        )
    )

    loaded = store.get_draft(draft.id)
    listed = store.list_drafts(expediente_id="exp-1")
    marked = store.mark_exported(draft.id, "docx", tmp_path / "informe.docx")
    record = store.get_record(draft.id)

    assert loaded is not None
    assert loaded.title == "Informe"
    assert listed == [draft]
    assert marked is True
    assert record is not None
    assert record.exported_docx_path.endswith("informe.docx")
    assert store.delete_draft(draft.id) is True
    assert store.get_draft(draft.id) is None
    store.close()
