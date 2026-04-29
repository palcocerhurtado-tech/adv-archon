from pathlib import Path

from adv_archon.desktop.presenters import (
    build_history_entry,
    format_sources_summary,
    merge_recent_items,
    onboarding_cards,
    recommended_window_size,
)


def test_format_sources_summary_groups_tools_memory_and_knowledge() -> None:
    summary = format_sources_summary(
        tool_names=("read_file", "web_search", "read_file"),
        memory_hits=("Investigas grimorios",),
        knowledge_hits=("clavicula-salomon.pdf",),
    )

    assert "herramientas: read_file, web_search" in summary
    assert "Memoria:" in summary
    assert "Conocimiento local:" in summary


def test_build_history_entry_compacts_prompt_response_and_attachments() -> None:
    entry = build_history_entry(
        "Hazme un resumen del grimorio con foco en simbolismo ritual",
        attachments=(Path("/tmp/clavicula.pdf"),),
        response_text="Resumen breve con puntos clave y matices interpretativos.",
    )

    assert "Hazme un resumen del grimorio" in entry
    assert "Adjuntos: clavicula.pdf" in entry
    assert "Respuesta: Resumen breve" in entry


def test_merge_recent_items_deduplicates_and_keeps_latest_first() -> None:
    merged = merge_recent_items(
        ["A", "B"],
        ["C", "A"],
        limit=3,
    )

    assert merged == ["C", "A", "B"]


def test_recommended_window_size_respects_screen_bounds() -> None:
    width, height = recommended_window_size(1512, 982)

    assert width <= 1512
    assert height <= 982
    assert width >= 980
    assert height >= 680


def test_onboarding_cards_expose_actionable_prompts() -> None:
    cards = onboarding_cards()

    assert len(cards) == 3
    assert any("briefing ejecutivo" in card.prompt for card in cards)
    assert any("study partner" in card.prompt for card in cards)
