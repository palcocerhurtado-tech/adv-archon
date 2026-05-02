from adv_archon.core.study_partner import (
    FALLBACK_SUMMARY,
    build_review_questions,
    build_short_study_plan,
    build_study_note,
    build_study_partner_guide,
    build_study_summary,
    extract_key_ideas,
)


def test_build_study_partner_guide_returns_renderable_sections() -> None:
    text = """
    # Retrieval Augmented Generation

    Retrieval augmented generation combines retrieval with generation
    so answers can use local knowledge.
    The workflow has three stages: index the corpus,
    retrieve relevant chunks, and synthesize a grounded answer.
    Better chunking improves precision, while evaluation tracks grounding, latency, and usefulness.
    Teams should keep regression cases close to user questions so the system keeps improving.
    """

    guide = build_study_partner_guide(
        title="RAG overview",
        content=text,
        objective="Prepare a 20 minute refresher before a design review",
        total_minutes=20,
    )
    rendered = guide.render()

    assert guide.title == "RAG overview"
    assert guide.objective == "Prepare a 20 minute refresher before a design review"
    assert guide.word_count >= 25
    assert "retriev" in guide.summary.lower()
    assert "ground" in guide.summary.lower()
    assert len(guide.key_ideas) >= 3
    assert any("retrieve relevant chunks" in idea.lower() for idea in guide.key_ideas)
    assert len(guide.review_questions) >= 3
    assert all(question.prompt.endswith("?") for question in guide.review_questions)
    assert all(question.answer_hint for question in guide.review_questions)
    assert sum(step.minutes for step in guide.study_plan) == 20
    assert guide.note.format == "markdown"
    assert "## Resumen" in guide.note.body
    assert "## Preguntas de repaso" in guide.note.body
    assert guide.note.suggested_filename == "study-rag-overview.md"
    assert "Study partner guide | RAG overview" in rendered
    assert "Prepare a 20 minute refresher before a design review" in rendered
    assert "Nota lista para guardar" in rendered

    payload = guide.as_payload()

    assert payload["title"] == "RAG overview"
    assert payload["key_ideas"]
    assert payload["review_questions"]
    assert payload["study_plan"]
    assert payload["note"]["suggested_filename"] == "study-rag-overview.md"


def test_extract_key_ideas_prefers_existing_bullets() -> None:
    text = """
    Study checklist
    - Define the main problem clearly
    - Compare retrieval quality against grounded answers
    - Track grounding, latency, and usefulness
    Closing line that should not displace the bullets.
    """

    ideas = extract_key_ideas(text, limit=3)
    questions = build_review_questions(text, limit=3)

    assert ideas == (
        "Define the main problem clearly",
        "Compare retrieval quality against grounded answers",
        "Track grounding, latency, and usefulness",
    )
    assert len(questions) == 3
    assert questions[0].answer_hint == "Define the main problem clearly"


def test_study_helpers_handle_empty_text_with_safe_fallbacks() -> None:
    summary = build_study_summary("   ")
    note = build_study_note("   ", title="Empty source", objective="Recover the basics quickly")
    guide = build_study_partner_guide(
        title="Empty source",
        content="   ",
        objective="Recover the basics quickly",
        total_minutes=12,
    )
    plan = build_short_study_plan("   ", total_minutes=12)

    assert summary == FALLBACK_SUMMARY
    assert note.title == "Empty source"
    assert "## Ideas clave" in note.body
    assert "Objective: Recover the basics quickly" in note.body
    assert "Sin ideas clave detectadas." in note.body
    assert note.suggested_filename == "study-empty-source.md"
    assert guide.word_count == 0
    assert guide.key_ideas == ()
    assert guide.review_questions == ()
    assert guide.study_plan == ()
    assert guide.note.suggested_filename == "study-empty-source.md"
    assert "No hay contenido suficiente para generar un resumen." in guide.render()
    assert plan == ()
