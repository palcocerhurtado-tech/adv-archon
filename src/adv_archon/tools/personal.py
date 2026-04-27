from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr  # type: ignore[import-untyped]

from adv_archon.core.logging import AppLogger
from adv_archon.core.tasks import parse_due_text

ConfirmCallback = Callable[[str], bool]
RECURRING_LOOKBACK_DAYS = 3650
PERSONAL_CONNECTOR_TIMEOUT_SECONDS = 12


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class PersonalTools:
    def __init__(
        self,
        *,
        confirm: ConfirmCallback,
        timezone_name: str = "Europe/Madrid",
        logger: AppLogger | None = None,
    ) -> None:
        self._confirm = confirm
        self._timezone_name = timezone_name
        self._logger = logger

    def calendar_upcoming(
        self,
        days: int = 7,
        limit: int = 20,
        start_offset_days: int = 0,
    ) -> ToolResult:
        timezone = ZoneInfo(self._timezone_name)
        now = datetime.now(timezone)
        base_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        window_start = base_start + timedelta(days=max(0, start_offset_days))
        window_end = window_start + timedelta(days=days)
        raw_events = _parse_calendar_rows(
            self._run_applescript(
                _calendar_script(days=max(days + max(0, start_offset_days), days))
            )
        )
        events = _expand_calendar_events(
            raw_events,
            window_start=window_start,
            window_end=window_end,
            limit=limit,
            timezone=timezone,
        )
        return ToolResult(
            name="calendar_upcoming",
            payload={
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "events": events,
            },
        )

    def reminders_list(self, limit: int = 20) -> ToolResult:
        payload = self._run_jxa(_reminders_script(limit=limit))
        return ToolResult(name="reminders_list", payload=payload)

    def notes_search(self, query: str, limit: int = 10) -> ToolResult:
        payload = self._run_jxa(_notes_script(query=query, limit=limit))
        return ToolResult(name="notes_search", payload=payload)

    def notes_create(
        self,
        title: str,
        body: str,
        folder: str | None = None,
    ) -> ToolResult:
        question = (
            "Se va a crear una nota en macOS Notes.\n"
            f"Titulo: {title}\n"
            f"Carpeta: {folder or 'predeterminada'}\n"
            "¿Confirmas?"
        )
        if not self._confirm(question):
            raise PermissionError("Creacion de nota cancelada por el usuario.")
        payload = self._run_jxa(_notes_create_script(title=title, body=body, folder=folder))
        return ToolResult(name="notes_create", payload=payload)

    def contacts_search(self, query: str, limit: int = 10) -> ToolResult:
        payload = self._run_jxa(_contacts_script(query=query, limit=limit))
        return ToolResult(name="contacts_search", payload=payload)

    def reminder_create(
        self,
        title: str,
        due_text: str | None = None,
        notes: str | None = None,
    ) -> ToolResult:
        question = (
            "Se va a crear un recordatorio en macOS.\n"
            f"Titulo: {title}\n"
            f"Cuando: {due_text or 'sin fecha'}\n"
            "¿Confirmas?"
        )
        if not self._confirm(question):
            raise PermissionError("Creacion de recordatorio cancelada por el usuario.")
        due_at = (
            parse_due_text(due_text, timezone_name=self._timezone_name).isoformat()
            if due_text
            else None
        )
        payload = self._run_jxa(
            _reminder_create_script(title=title, notes=notes, due_at_iso=due_at)
        )
        return ToolResult(name="reminder_create", payload=payload)

    def mail_draft(self, to: list[str], subject: str, body: str) -> ToolResult:
        question = (
            "Se va a crear un borrador de email en Mail.\n"
            f"Para: {', '.join(to)}\n"
            f"Asunto: {subject}\n"
            "¿Confirmas?"
        )
        if not self._confirm(question):
            raise PermissionError("Creacion de borrador cancelada por el usuario.")
        payload = self._run_jxa(_mail_draft_script(to=to, subject=subject, body=body))
        return ToolResult(name="mail_draft", payload=payload)

    def _run_jxa(self, script: str) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", script],
                capture_output=True,
                text=True,
                check=False,
                timeout=PERSONAL_CONNECTOR_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "El conector personal ha tardado demasiado y se ha cancelado."
            ) from exc
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Fallo ejecutando conector personal.")
        output = completed.stdout.strip() or "{}"
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Respuesta invalida del conector personal: {output}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Respuesta invalida del conector personal: se esperaba un objeto.")
        if self._logger is not None:
            self._logger.log("personal_tool", payload_keys=sorted(payload.keys()))
        return payload

    def _run_applescript(self, lines: list[str]) -> str:
        command = ["osascript"]
        for line in lines:
            command.extend(["-e", line])
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=PERSONAL_CONNECTOR_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "El conector personal ha tardado demasiado y se ha cancelado."
            ) from exc
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Fallo ejecutando AppleScript.")
        return completed.stdout.strip()


def build_personal_tool_specs(tool: PersonalTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "calendar_upcoming",
            "description": "List upcoming events from the user's macOS Calendar.",
            "schema": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer"},
                    "limit": {"type": "integer"},
                    "start_offset_days": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.calendar_upcoming,
        },
        {
            "name": "reminders_list",
            "description": "List open reminders from the user's macOS Reminders app.",
            "schema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.reminders_list,
        },
        {
            "name": "notes_search",
            "description": "Search macOS Notes by text content.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            "fn": tool.notes_search,
        },
        {
            "name": "notes_create",
            "description": "Create a new note in macOS Notes after confirmation.",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "folder": {"type": "string"},
                },
                "required": ["title", "body"],
            },
            "fn": tool.notes_create,
        },
        {
            "name": "contacts_search",
            "description": "Search macOS Contacts by name, email, or phone.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            "fn": tool.contacts_search,
        },
        {
            "name": "reminder_create",
            "description": "Create a reminder in macOS Reminders after confirmation.",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "due_text": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["title"],
            },
            "fn": tool.reminder_create,
        },
        {
            "name": "mail_draft",
            "description": "Create a draft email in macOS Mail after confirmation.",
            "schema": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
            "fn": tool.mail_draft,
        },
    ]


def _calendar_script(*, days: int) -> list[str]:
    return [
        "set startDate to (current date)",
        "set startDate to startDate - (time of startDate)",
        f"set recurringLookbackDate to startDate - ({RECURRING_LOOKBACK_DAYS} * days)",
        f"set endDate to startDate + ({days} * days)",
        "on safeText(value)",
        "if value is missing value then return \"\"",
        "try",
        "return value as text",
        "on error",
        "return \"\"",
        "end try",
        "end safeText",
        "on pad2(n)",
        "if n < 10 then return \"0\" & (n as text)",
        "return n as text",
        "end pad2",
        "on localIso(d)",
        "set y to year of d as integer",
        "set m to my pad2(month of d as integer)",
        "set dayNumber to my pad2(day of d as integer)",
        "set hh to my pad2(hours of d)",
        "set mm to my pad2(minutes of d)",
        "set ss to my pad2(seconds of d)",
        "return (y as text) & \"-\" & m & \"-\" & dayNumber & \"T\" & hh & \":\" & mm & \":\" & ss",
        "end localIso",
        "tell application \"Calendar\"",
        "if not running then launch",
        "set outputLines to {}",
        "repeat with cal in calendars",
        "set calName to my safeText(name of cal)",
        (
            "set recurringCandidates to "
            "(every event of cal whose start date >= recurringLookbackDate "
            "and start date < endDate)"
        ),
        "repeat with ev in recurringCandidates",
        "try",
        "set evRecurrence to recurrence of ev",
        "if evRecurrence is missing value then error number -128",
        (
            "set outputLines to outputLines & "
            "((calName & tab & my safeText(summary of ev) & tab & "
            "my localIso(start date of ev) & tab & my localIso(end date of ev) & tab & "
            "my safeText(evRecurrence) & tab & my safeText(location of ev)) as text)"
        ),
        "end try",
        "end repeat",
        (
            "set directCandidates to "
            "(every event of cal whose start date < endDate and end date >= startDate)"
        ),
        "repeat with ev in directCandidates",
        "try",
        "set evRecurrence to recurrence of ev",
        "if evRecurrence is not missing value then error number -128",
        (
            "set outputLines to outputLines & "
            "((calName & tab & my safeText(summary of ev) & tab & "
            "my localIso(start date of ev) & tab & my localIso(end date of ev) & tab & "
            "\"\" & tab & my safeText(location of ev)) as text)"
        ),
        "end try",
        "end repeat",
        "end repeat",
        "set AppleScript's text item delimiters to linefeed",
        "return outputLines as text",
        "end tell",
    ]


def _parse_calendar_rows(output: str) -> list[dict[str, Any]]:
    if not output:
        return []
    events: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        calendar, title, start, end, recurrence, location = parts[:6]
        events.append(
            {
                "calendar": calendar.strip(),
                "title": title.strip(),
                "start": start.strip(),
                "end": end.strip(),
                "recurrence": recurrence.strip() or None,
                "location": location.strip() or None,
            }
        )
    return events


def _expand_calendar_events(
    raw_events: Sequence[object],
    *,
    window_start: datetime,
    window_end: datetime,
    limit: int,
    timezone: ZoneInfo,
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for item in raw_events:
        if not isinstance(item, dict):
            continue
        calendar = str(item.get("calendar") or "").strip()
        title = str(item.get("title") or "").strip()
        start_raw = item.get("start")
        end_raw = item.get("end")
        recurrence_raw = item.get("recurrence")
        if not isinstance(start_raw, str) or not isinstance(end_raw, str):
            continue
        try:
            start_dt = datetime.fromisoformat(start_raw)
            end_dt = datetime.fromisoformat(end_raw)
        except ValueError:
            continue
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone)
        else:
            start_dt = start_dt.astimezone(timezone)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone)
        else:
            end_dt = end_dt.astimezone(timezone)
        duration = end_dt - start_dt
        location_value = item.get("location")
        location = str(location_value).strip() if isinstance(location_value, str) else None

        if isinstance(recurrence_raw, str) and recurrence_raw.strip():
            try:
                rule = rrulestr(recurrence_raw.strip(), dtstart=start_dt)
                occurrences = rule.between(window_start, window_end, inc=True)
            except Exception:
                occurrences = [start_dt] if window_start <= start_dt < window_end else []
            for occurrence in occurrences:
                occurrence_end = occurrence + duration
                _append_calendar_event(
                    expanded,
                    seen,
                    calendar=calendar,
                    title=title,
                    start_dt=occurrence.astimezone(timezone),
                    end_dt=occurrence_end.astimezone(timezone),
                    location=location,
                )
            continue

        if start_dt < window_end and end_dt >= window_start:
            _append_calendar_event(
                expanded,
                seen,
                calendar=calendar,
                title=title,
                start_dt=start_dt,
                end_dt=end_dt,
                location=location,
            )

    expanded.sort(key=lambda record: str(record["start"]))
    return expanded[:limit]


def _append_calendar_event(
    events: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    *,
    calendar: str,
    title: str,
    start_dt: datetime,
    end_dt: datetime,
    location: str | None,
) -> None:
    key = (
        calendar,
        title,
        start_dt.isoformat(),
        end_dt.isoformat(),
    )
    if key in seen:
        return
    seen.add(key)
    events.append(
        {
            "calendar": calendar,
            "title": title,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "location": location,
            "all_day": _is_all_day_event(start_dt, end_dt),
        }
    )


def _is_all_day_event(start_dt: datetime, end_dt: datetime) -> bool:
    return (
        start_dt.hour == 0
        and start_dt.minute == 0
        and start_dt.second == 0
        and end_dt.hour == 23
        and end_dt.minute == 59
    )


def _reminders_script(*, limit: int) -> str:
    return f"""
const Reminders = Application('Reminders');
let reminders = [];
for (const list of Reminders.lists()) {{
  for (const reminder of list.reminders()) {{
    if (reminder.completed()) continue;
    reminders.push({{
      list: list.name(),
      title: reminder.name(),
      body: reminder.body(),
      dueDate: reminder.dueDate() ? reminder.dueDate().toISOString() : null
    }});
  }}
}}
reminders = reminders.slice(0, {limit});
JSON.stringify({{reminders}});
"""


def _notes_script(*, query: str, limit: int) -> str:
    query_json = json.dumps(query.lower())
    return f"""
const Notes = Application('Notes');
const query = {query_json};
let results = [];
for (const folder of Notes.folders()) {{
  for (const note of folder.notes()) {{
    const title = String(note.name() || '');
    const body = String(note.body() || '');
    const haystack = (title + ' ' + body).toLowerCase();
    if (!haystack.includes(query)) continue;
    results.push({{
      folder: folder.name(),
      title,
      body: body.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim().slice(0, 600)
    }});
  }}
}}
results = results.slice(0, {limit});
JSON.stringify({{notes: results}});
"""


def _notes_create_script(*, title: str, body: str, folder: str | None) -> str:
    title_json = json.dumps(title)
    folder_json = json.dumps(folder)
    body_json = json.dumps(body)
    return f"""
const Notes = Application('Notes');
const title = {title_json};
const bodyText = {body_json};
const requestedFolder = {folder_json};

function escapeHtml(value) {{
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}}

function chooseFolder() {{
  if (requestedFolder) {{
    for (const folder of Notes.folders()) {{
      if (String(folder.name()) === requestedFolder) {{
        return folder;
      }}
    }}
  }}
  const folders = Notes.folders();
  if (folders.length > 0) {{
    return folders[0];
  }}
  throw new Error('No he encontrado una carpeta disponible en Notes.');
}}

const noteBody = '<div>' + escapeHtml(bodyText).replace(/\\n/g, '<br>') + '</div>';
const folder = chooseFolder();
const note = Notes.Note({{name: title, body: noteBody}});
folder.notes.push(note);
JSON.stringify({{
  created: true,
  title: note.name(),
  folder: folder.name()
}});
"""


def _contacts_script(*, query: str, limit: int) -> str:
    query_json = json.dumps(query.lower())
    return f"""
const Contacts = Application('Contacts');
const query = {query_json};
let results = [];
for (const person of Contacts.people()) {{
  const first = String(person.firstName() || '');
  const last = String(person.lastName() || '');
  const org = String(person.organization() || '');
  const emails = person.emails().map(e => String(e.value()));
  const phones = person.phones().map(p => String(p.value()));
  const haystack = [first, last, org].concat(emails).concat(phones).join(' ').toLowerCase();
  if (!haystack.includes(query)) continue;
  results.push({{
    name: [first, last].join(' ').trim(),
    organization: org,
    emails,
    phones
  }});
}}
results = results.slice(0, {limit});
JSON.stringify({{contacts: results}});
"""


def _reminder_create_script(
    *,
    title: str,
    notes: str | None,
    due_at_iso: str | None,
) -> str:
    title_json = json.dumps(title)
    notes_json = json.dumps(notes or "")
    due_json = json.dumps(due_at_iso)
    return f"""
const Reminders = Application('Reminders');
const list = Reminders.defaultList();
const reminderArgs = {{name: {title_json}, body: {notes_json}}};
if ({due_json} !== null) {{
  reminderArgs.dueDate = new Date({due_json});
}}
const reminder = Reminders.Reminder(reminderArgs);
list.reminders.push(reminder);
JSON.stringify({{
  created: true,
  title: reminder.name(),
  list: list.name(),
  dueDate: reminder.dueDate() ? reminder.dueDate().toISOString() : null
}});
"""


def _mail_draft_script(*, to: list[str], subject: str, body: str) -> str:
    to_json = json.dumps(to)
    subject_json = json.dumps(subject)
    body_json = json.dumps(body)
    return f"""
const Mail = Application('Mail');
const recipients = {to_json}.map(address => Mail.Recipient({{address}}));
const draft = Mail.OutgoingMessage({{
  subject: {subject_json},
  content: {body_json},
  visible: false
}});
draft.toRecipients = recipients;
Mail.outgoingMessages.push(draft);
JSON.stringify({{created: true, subject: draft.subject(), to: {to_json}}});
"""
