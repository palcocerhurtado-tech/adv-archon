from __future__ import annotations

from types import SimpleNamespace

from adv_archon.core.document_draft import (
    DocumentDraft,
    DraftSection,
    build_expediente_draft,
    build_research_draft,
)


def test_document_draft_roundtrip_json() -> None:
    draft = DocumentDraft(
        id="draft-1",
        title="Informe preliminar",
        executive_summary="Viable condicionado.",
        sections=(DraftSection("summary", "Resumen", "Texto"),),
        warnings=("No vinculante.",),
        next_steps=("Revisar PGOU.",),
    )

    restored = DocumentDraft.from_json(draft.to_json())

    assert restored == draft
    assert restored.to_dict()["sections"][0]["title"] == "Resumen"


def test_document_draft_updates_single_section() -> None:
    draft = DocumentDraft(
        title="Borrador",
        sections=(
            DraftSection("a", "A", "Uno"),
            DraftSection("b", "B", "Dos"),
        ),
    )

    updated = draft.with_section_update("b", "Dos actualizado")

    assert updated.sections[0].content == "Uno"
    assert updated.sections[1].content == "Dos actualizado"


def test_build_expediente_draft_is_conservative() -> None:
    expediente = SimpleNamespace(
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

    draft = build_expediente_draft(expediente)

    assert draft.expediente_id == "exp-1"
    assert draft.municipality == "Madrid"
    assert draft.tables[0].rows[0] == ("Direccion", "Calle Mayor 24")
    assert "no vinculante" in draft.warnings[0]


def test_build_research_draft_preserves_sources_and_formulas() -> None:
    evidence = SimpleNamespace(
        id="E1",
        title="Fuente",
        url="https://example.com",
        excerpt="Dato relevante.",
    )
    result = SimpleNamespace(
        question="Resolver una formula de estructuras",
        synthesis="Sintesis final",
        subquestions=("Que formula aplica?",),
        formula_candidates=("M = qL^2/8",),
        gaps=("Validar unidades.",),
        next_steps=("Preparar entrega.",),
        evidences=(evidence,),
    )

    draft = build_research_draft(result)

    assert draft.kind == "research"
    assert draft.sources[0].url == "https://example.com"
    assert any(section.id == "formulas" for section in draft.sections)
    assert draft.metadata == {
        "question": "Resolver una formula de estructuras",
        "evidence_count": 1,
    }
