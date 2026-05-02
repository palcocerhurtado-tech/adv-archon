from __future__ import annotations

from datetime import datetime
from subprocess import TimeoutExpired
from zoneinfo import ZoneInfo

import pytest

from adv_archon.tools.personal import (
    RECURRING_LOOKBACK_DAYS,
    PersonalTools,
    _calendar_script,
    _expand_calendar_events,
)


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


def test_notes_create_requires_confirmation() -> None:
    tool = PersonalTools(confirm=lambda _question: False)

    with pytest.raises(PermissionError):
        tool.notes_create("Ideas", "Revisar conectores")


def test_notes_create_calls_jxa_when_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    tool = PersonalTools(confirm=lambda _question: True)

    def fake_run(script: str) -> dict[str, object]:
        captured["script"] = script
        return {"created": True, "title": "Ideas", "folder": "Notas"}

    monkeypatch.setattr(tool, "_run_jxa", fake_run)

    result = tool.notes_create("Ideas", "Revisar conectores", folder="Notas")

    assert result.payload["created"] is True
    assert "Ideas" in captured["script"]
    assert "Revisar conectores" in captured["script"]
    assert "Notas" in captured["script"]


def test_calendar_upcoming_expands_weekly_recurrence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = PersonalTools(confirm=lambda _question: True, timezone_name="Europe/Madrid")

    monkeypatch.setattr(
        tool,
        "_run_applescript",
        lambda _script: "\n".join(
            [
                (
                    "CLASE\tCLASECILLAS\t2026-04-06T08:30:00\t2026-04-06T14:00:00\t"
                    "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR\t"
                ),
                (
                    "Festivos en España\tDía de San Jorge\t2026-04-23T00:00:00\t"
                    "2026-04-23T23:59:59\t\t"
                ),
            ]
        ),
    )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: ZoneInfo | None = None) -> datetime:
            base = cls(2026, 4, 21, 9, 10, tzinfo=ZoneInfo("Europe/Madrid"))
            return base if tz is None else base.astimezone(tz)

    monkeypatch.setattr("adv_archon.tools.personal.datetime", FrozenDateTime)

    result = tool.calendar_upcoming(days=6, limit=20)
    titles = [event["title"] for event in result.payload["events"]]

    assert titles == [
        "CLASECILLAS",
        "CLASECILLAS",
        "Día de San Jorge",
        "CLASECILLAS",
        "CLASECILLAS",
    ]


def test_calendar_upcoming_supports_offset_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = PersonalTools(confirm=lambda _question: True, timezone_name="Europe/Madrid")

    monkeypatch.setattr(
        tool,
        "_run_applescript",
        lambda _script: "\n".join(
            [
                "CLASE\tHOY\t2026-04-21T08:30:00\t2026-04-21T09:30:00\t\t",
                "CLASE\tMANANA\t2026-04-22T08:30:00\t2026-04-22T09:30:00\t\t",
            ]
        ),
    )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: ZoneInfo | None = None) -> datetime:
            base = cls(2026, 4, 21, 9, 10, tzinfo=ZoneInfo("Europe/Madrid"))
            return base if tz is None else base.astimezone(tz)

    monkeypatch.setattr("adv_archon.tools.personal.datetime", FrozenDateTime)

    result = tool.calendar_upcoming(days=1, limit=20, start_offset_days=1)
    titles = [event["title"] for event in result.payload["events"]]

    assert titles == ["MANANA"]


def test_calendar_script_uses_long_recurrence_lookback() -> None:
    script_lines = _calendar_script(days=7)

    assert any(
        f"({RECURRING_LOOKBACK_DAYS} * days)" in line for line in script_lines
    )
    assert "if not running then launch" in script_lines


def test_expand_calendar_events_handles_recurring_and_one_off() -> None:
    timezone = ZoneInfo("Europe/Madrid")
    events = _expand_calendar_events(
        [
            {
                "calendar": "CLASE",
                "title": "CLASECILLAS",
                "start": "2026-04-06T06:30:00.000Z",
                "end": "2026-04-06T12:00:00.000Z",
                "location": None,
                "recurrence": "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR",
            },
            {
                "calendar": "Festivos en España",
                "title": "Día de San Jorge",
                "start": "2026-04-22T22:00:00.000Z",
                "end": "2026-04-23T21:59:59.000Z",
                "location": None,
                "recurrence": None,
            },
        ],
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone),
        window_end=datetime(2026, 4, 27, 0, 0, tzinfo=timezone),
        limit=20,
        timezone=timezone,
    )

    assert len(events) == 5
    assert events[0]["start"].startswith("2026-04-21T08:30:00")
    assert events[1]["start"].startswith("2026-04-22T08:30:00")
    assert events[2]["title"] == "Día de San Jorge"


def test_notes_search_times_out_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = PersonalTools(confirm=lambda _question: True)

    def fake_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise TimeoutExpired(cmd=["osascript"], timeout=12)

    monkeypatch.setattr("adv_archon.tools.personal.subprocess.run", fake_run)

    with pytest.raises(RuntimeError):
        tool.notes_search("acme", limit=3)
