from __future__ import annotations

from adv_archon.desktop.workers import DesktopBusyState


def test_busy_state_blocks_actions_until_backend_is_ready() -> None:
    state = DesktopBusyState(backend_ready=False, busy=False)

    assert state.accepts_user_actions is True
    assert state.can_dispatch_requests is False
    assert state.allows_configuration is True
    assert state.status_text(mode="local", profile="general") == "Esperando backend…"


def test_busy_state_reports_prompt_processing() -> None:
    state = DesktopBusyState(backend_ready=True, busy=True, task="prompt")

    assert state.accepts_user_actions is False
    assert state.can_dispatch_requests is False
    assert state.allows_configuration is False
    assert state.status_text(mode="local", profile="general") == "Procesando petición…"


def test_busy_state_reports_clean_shutdown() -> None:
    state = DesktopBusyState(backend_ready=True, closing=True)

    assert state.accepts_user_actions is False
    assert state.can_dispatch_requests is False
    assert state.allows_configuration is False
    assert state.status_text(mode="cloud", profile="coding") == "Cerrando…"


def test_busy_state_renders_idle_mode_and_profile() -> None:
    state = DesktopBusyState(backend_ready=True, busy=False)

    assert state.accepts_user_actions is True
    assert state.can_dispatch_requests is True
    assert state.allows_configuration is True
    assert state.status_text(mode="cloud", profile="research") == "Modo: cloud | Perfil: research"
