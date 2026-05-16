from __future__ import annotations

import pytest

from adv_archon.desktop.voice_commands import (
    build_voice_system_prompt,
    classify_voice_intent,
    parse_live_turns,
    split_voice_response,
)


def test_parse_live_turns_defaults_for_desktop() -> None:
    assert parse_live_turns("/live") == 3


def test_parse_live_turns_accepts_bounded_count() -> None:
    assert parse_live_turns("/live 1") == 1
    assert parse_live_turns("/live 999") == 20


def test_parse_live_turns_ignores_regular_chat() -> None:
    assert parse_live_turns("hola archon") is None


def test_parse_live_turns_rejects_invalid_argument() -> None:
    with pytest.raises(ValueError, match="Uso: /live"):
        parse_live_turns("/live ahora")


def test_classify_voice_intent_detects_expediente_actions() -> None:
    assert classify_voice_intent("crea un expediente nuevo") is not None
    assert classify_voice_intent("analiza este plano").action == "analyze_plan"
    assert classify_voice_intent("explícame los riesgos").action == "explain_risks"
    assert classify_voice_intent("qué falta para que sea viable").action == "missing_viability"


def test_voice_system_prompt_includes_expediente_context() -> None:
    prompt = build_voice_system_prompt("Dirección: Calle Mayor 24")

    assert "VOZ:" in prompt
    assert "DETALLE:" in prompt
    assert "Calle Mayor 24" in prompt


def test_split_voice_response_prefers_spoken_block() -> None:
    voice, screen = split_voice_response("VOZ: Es condicionado.\nDETALLE: Falta PGOU.")

    assert voice == "Es condicionado."
    assert "Falta PGOU" in screen
