from __future__ import annotations

from adv_archon.core.document_store import DocumentStore
from adv_archon.tools.document_tools import DocumentTools, build_document_tool_specs


def test_document_tools_update_and_export(tmp_path) -> None:
    store = DocumentStore(tmp_path / "documents.db")
    tools = DocumentTools(store, output_dir=tmp_path)

    created = tools.update_pdf_draft(
        title="Informe editable",
        executive_summary="Resumen",
        sections=[{"id": "summary", "title": "Resumen", "content": "Texto"}],
    )
    draft_id = str(created["draft_id"])
    updated = tools.update_pdf_draft(
        draft_id=draft_id,
        section_id="summary",
        section_content="Texto revisado",
    )
    docx = tools.generate_docx(draft_id=draft_id)
    xlsx = tools.generate_xlsx(draft_id=draft_id)
    pdf = tools.generate_pdf(draft_id=draft_id)

    assert updated["draft"]["sections"][0]["content"] == "Texto revisado"
    assert str(docx["output_path"]).endswith(".docx")
    assert str(xlsx["output_path"]).endswith(".xlsx")
    assert str(pdf["output_path"]).endswith(".pdf")
    assert store.get_record(draft_id) is not None
    store.close()


def test_build_document_tool_specs_exposes_expected_tools(tmp_path) -> None:
    specs = build_document_tool_specs(DocumentTools(DocumentStore(tmp_path / "db.sqlite")))

    assert {spec["name"] for spec in specs} == {
        "update_pdf_draft",
        "generate_docx",
        "generate_xlsx",
        "generate_pdf",
    }
