from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adv_archon.core.gmail_triage import GmailMailboxTriage, triage_mailbox
from adv_archon.core.meeting_prep import MeetingPrepBrief, build_meeting_prep_brief


@dataclass(frozen=True, slots=True)
class ExecutiveBrief:
    profile: str | None
    project_name: str | None
    priorities: tuple[str, ...]
    email_counts: dict[str, int]
    email_actions: tuple[str, ...]
    top_emails: tuple[str, ...]
    next_meeting_summary: str | None
    meeting_prep: MeetingPrepBrief | None

    def render(self) -> str:
        lines = [
            "ADV ARCHON executive brief",
            f"- Perfil: {self.profile or 'general'}",
            f"- Proyecto: {self.project_name or 'sin proyecto'}",
            "",
            "Prioridades de hoy:",
        ]
        if self.priorities:
            lines.extend(f"- {item}" for item in self.priorities)
        else:
            lines.append("- No veo una urgencia dominante con el contexto actual.")

        lines.extend(
            [
                "",
                "Inbox:",
                f"- Urgentes: {self.email_counts.get('urgent', 0)}",
                f"- Hoy: {self.email_counts.get('today', 0)}",
                f"- En espera: {self.email_counts.get('waiting', 0)}",
                f"- Baja prioridad: {self.email_counts.get('low', 0)}",
            ]
        )
        if self.email_actions:
            lines.append("- Correos a mover primero:")
            lines.extend(f"  {item}" for item in self.email_actions)
        if self.top_emails:
            lines.append("- Hilos relevantes:")
            lines.extend(f"  {item}" for item in self.top_emails)

        lines.extend(["", "Próxima reunión:"])
        if self.next_meeting_summary:
            lines.append(f"- {self.next_meeting_summary}")
        else:
            lines.append("- No detecto una reunión clara para preparar ahora mismo.")

        if self.meeting_prep is not None:
            lines.extend(
                [
                    "",
                    "Meeting prep:",
                ]
            )
            lines.extend(
                f"- {item}" for item in self.meeting_prep.priorities[:3]
            )
            if self.meeting_prep.risks:
                lines.append("- Riesgos:")
                lines.extend(f"  {item}" for item in self.meeting_prep.risks[:3])
            if self.meeting_prep.questions:
                lines.append("- Preguntas sugeridas:")
                lines.extend(f"  {item}" for item in self.meeting_prep.questions[:3])

        return "\n".join(lines)


def build_executive_brief(
    *,
    profile: str | None,
    project_name: str | None,
    local_calendar_events: list[dict[str, Any]] | None = None,
    google_calendar_events: list[dict[str, Any]] | None = None,
    reminders: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    gmail_messages: list[dict[str, Any]] | None = None,
    drive_files: list[dict[str, Any]] | None = None,
    notes: list[dict[str, Any]] | None = None,
    knowledge_hits: list[dict[str, Any]] | None = None,
) -> ExecutiveBrief:
    local_events = list(local_calendar_events or [])
    google_events = list(google_calendar_events or [])
    all_events = _sorted_events([*google_events, *local_events])
    mailbox = triage_mailbox(list(gmail_messages or []))
    meeting_title = ""
    meeting_window = ""
    if all_events:
        meeting = all_events[0]
        meeting_title = str(meeting.get("summary") or meeting.get("title") or "").strip()
        meeting_window = _format_event_window(meeting)

    priorities = _build_priorities(
        events=all_events,
        reminders=list(reminders or []),
        tasks=list(tasks or []),
        mailbox=mailbox,
    )
    top_emails = tuple(
        f"[{item.priority}] {item.subject or '(sin asunto)'} — {item.sender}"
        for item in mailbox.messages[:3]
    )
    email_actions = tuple(
        item.next_steps[0]
        for item in mailbox.messages[:3]
        if item.next_steps
    )

    meeting_prep = None
    next_meeting_summary = None
    if meeting_title:
        next_meeting_summary = f"{meeting_title} | {meeting_window}"
        meeting_prep = build_meeting_prep_brief(
            meeting_title=meeting_title,
            meeting_when=meeting_window,
            calendar_events=all_events,
            gmail_messages=list(gmail_messages or []),
            drive_files=list(drive_files or []),
            notes=list(notes or []),
            knowledge_hits=list(knowledge_hits or []),
            project_name=project_name,
        )

    return ExecutiveBrief(
        profile=profile,
        project_name=project_name,
        priorities=tuple(priorities),
        email_counts={str(key): value for key, value in mailbox.counts.items()},
        email_actions=email_actions[:3],
        top_emails=top_emails,
        next_meeting_summary=next_meeting_summary,
        meeting_prep=meeting_prep,
    )


def _build_priorities(
    *,
    events: list[dict[str, Any]],
    reminders: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    mailbox: GmailMailboxTriage,
) -> list[str]:
    priorities: list[str] = []
    for event in events[:2]:
        title = str(event.get("summary") or event.get("title") or "").strip()
        if title:
            priorities.append(f"Agenda: {title} ({_format_event_window(event)})")
    for task in tasks[:2]:
        title = str(task.get("title") or "").strip()
        if title:
            priorities.append(f"Tarea: {title}")
    for reminder in reminders[:2]:
        title = str(reminder.get("title") or "").strip()
        if title:
            priorities.append(f"Recordatorio: {title}")
    for item in mailbox.messages[:2]:
        priorities.append(f"Correo [{item.priority}]: {item.subject or '(sin asunto)'}")
    return priorities[:6]


def _sorted_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=_event_sort_key)


def _event_sort_key(event: dict[str, Any]) -> str:
    return str(event.get("start") or event.get("date") or "")


def _format_event_window(event: dict[str, Any]) -> str:
    start = str(event.get("start") or "").strip()
    end = str(event.get("end") or "").strip()
    if start and end:
        return f"{start} -> {end}"
    if start:
        return start
    return "sin hora"
