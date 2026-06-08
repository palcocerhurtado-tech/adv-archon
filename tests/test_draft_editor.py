from __future__ import annotations

from pathlib import Path

from adv_archon.desktop.draft_editor import (
    build_attachment_previews,
    extract_draft_sections,
)


def test_extract_draft_sections_accepts_loose_json() -> None:
    draft = {
        "title": "Informe preliminar",
        "sections": [
            {"id": "summary", "title": "Resumen", "content": "Viable condicionado."},
            {"section_id": "sources", "heading": "Fuentes", "body": "Catastro y PGOU."},
        ],
    }

    sections = extract_draft_sections(draft)

    assert [section.section_id for section in sections] == ["summary", "sources"]
    assert sections[1].title == "Fuentes"
    assert sections[1].content == "Catastro y PGOU."


def test_extract_draft_sections_falls_back_to_executive_summary() -> None:
    sections = extract_draft_sections({"executive_summary": "Resumen ejecutivo disponible."})

    assert len(sections) == 1
    assert sections[0].section_id == "executive_summary"
    assert sections[0].content == "Resumen ejecutivo disponible."


def test_build_attachment_previews_classifies_files(tmp_path: Path) -> None:
    pdf = tmp_path / "plano.pdf"
    pdf.write_bytes(b"%PDF")

    previews = build_attachment_previews([pdf])

    assert len(previews) == 1
    assert previews[0].display_name == "plano.pdf"
    assert previews[0].kind == "document"
    assert "plano.pdf" in previews[0].summary
