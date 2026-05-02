from __future__ import annotations

from pathlib import Path

from adv_archon.desktop.models import DesktopChatRequest, collect_attachments
from adv_archon.desktop.runtime import EchoDesktopBackend, build_default_runtime_assumptions


def test_echo_backend_mentions_attachments(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("# Notes\n", encoding="utf-8")
    backend = EchoDesktopBackend()

    response = backend.complete(
        DesktopChatRequest(
            prompt="resume esto",
            attachments=tuple(collect_attachments([notes])),
        )
    )

    assert "notes.md" in response.text
    assert response.metadata["backend"] == "echo-desktop"
    assert response.used_attachments[0].display_name == "notes.md"


def test_default_runtime_assumptions_cover_desktop_scope() -> None:
    assumptions = build_default_runtime_assumptions()

    assert len(assumptions) == 3
    assert assumptions[0].title == "Chat sync placeholder"
    assert "Adjuntos" in assumptions[1].description or "adjuntos" in assumptions[1].description
