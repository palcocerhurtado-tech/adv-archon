from __future__ import annotations

import pytest

from adv_archon.tools.personal import PersonalTools


def test_reminder_create_includes_due_date_when_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    tool = PersonalTools(confirm=lambda _question: True, timezone_name="Europe/Madrid")

    def fake_run(script: str) -> dict[str, object]:
        captured["script"] = script
        return {"created": True}

    monkeypatch.setattr(tool, "_run_jxa", fake_run)

    result = tool.reminder_create(
        "Llamar a ACME",
        due_text="2026-04-24 09:00",
        notes="Preparar cierre",
    )

    assert result.payload["created"] is True
    assert "dueDate" in captured["script"]
    assert "Llamar a ACME" in captured["script"]


def test_mail_draft_requires_confirmation() -> None:
    tool = PersonalTools(confirm=lambda _question: False)

    with pytest.raises(PermissionError):
        tool.mail_draft(
            ["cliente@example.com"],
            "Propuesta",
            "Te adjunto la propuesta.",
        )
