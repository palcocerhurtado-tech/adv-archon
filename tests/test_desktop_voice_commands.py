from __future__ import annotations

import pytest

from adv_archon.desktop.voice_commands import parse_live_turns


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
