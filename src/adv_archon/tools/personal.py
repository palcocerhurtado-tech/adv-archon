from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from adv_archon.core.logging import AppLogger
from adv_archon.core.tasks import parse_due_text

ConfirmCallback = Callable[[str], bool]


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

    def calendar_upcoming(self, days: int = 7, limit: int = 20) -> ToolResult:
        payload = self._run_jxa(_calendar_script(days=days, limit=limit))
        return ToolResult(name="calendar_upcoming", payload=payload)

    def reminders_list(self, limit: int = 20) -> ToolResult:
        payload = self._run_jxa(_reminders_script(limit=limit))
        return ToolResult(name="reminders_list", payload=payload)

    def notes_search(self, query: str, limit: int = 10) -> ToolResult:
        payload = self._run_jxa(_notes_script(query=query, limit=limit))
        return ToolResult(name="notes_search", payload=payload)

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
        completed = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
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


def _calendar_script(*, days: int, limit: int) -> str:
    return f"""
const Calendar = Application('Calendar');
Calendar.includeStandardAdditions = true;
const now = new Date();
const end = new Date(now.getTime() + ({days} * 24 * 60 * 60 * 1000));
const calendars = Calendar.calendars();
let events = [];
for (const cal of calendars) {{
  const matches = cal.events.whose({{
    startDate: {{_greaterThan: now}},
    endDate: {{_lessThan: end}}
  }})();
  for (const event of matches) {{
    events.push({{
      calendar: cal.name(),
      title: event.summary(),
      start: event.startDate().toISOString(),
      end: event.endDate().toISOString(),
      location: event.location()
    }});
  }}
}}
events = events.sort((a, b) => a.start.localeCompare(b.start)).slice(0, {limit});
JSON.stringify({{events}});
"""


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
