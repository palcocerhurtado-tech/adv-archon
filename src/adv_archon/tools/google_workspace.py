from __future__ import annotations

import base64
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from adv_archon.core.logging import AppLogger
from adv_archon.core.tasks import parse_due_text

ConfirmCallback = Callable[[str], bool]

GOOGLE_WORKSPACE_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
)


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class GoogleWorkspaceTools:
    def __init__(
        self,
        *,
        client_secret_file: Path,
        token_file: Path,
        confirm: ConfirmCallback,
        enabled: bool = True,
        timezone_name: str = "Europe/Madrid",
        default_calendar_id: str = "primary",
        gmail_default_max_results: int = 10,
        drive_default_max_results: int = 10,
        logger: AppLogger | None = None,
    ) -> None:
        self._client_secret_file = client_secret_file
        self._token_file = token_file
        self._confirm = confirm
        self._enabled = enabled
        self._timezone_name = timezone_name
        self._default_calendar_id = default_calendar_id
        self._gmail_default_max_results = gmail_default_max_results
        self._drive_default_max_results = drive_default_max_results
        self._logger = logger
        self._service_cache: dict[tuple[str, str], Any] = {}

    def gmail_search(self, query: str = "", max_results: int | None = None) -> ToolResult:
        service = self._service("gmail", "v1")
        payload = service.users().messages().list(
            userId="me",
            q=query or None,
            maxResults=max_results or self._gmail_default_max_results,
        ).execute()
        items = payload.get("messages", [])
        messages: list[dict[str, Any]] = []
        for item in items:
            detail = service.users().messages().get(
                userId="me",
                id=item["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date", "To"],
            ).execute()
            headers = _header_map(detail.get("payload", {}).get("headers", []))
            messages.append(
                {
                    "id": detail.get("id"),
                    "thread_id": detail.get("threadId"),
                    "label_ids": detail.get("labelIds", []),
                    "subject": headers.get("Subject", ""),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "date": headers.get("Date", ""),
                    "snippet": detail.get("snippet", ""),
                }
            )
        self._log("gmail_search", query=query, results=len(messages))
        return ToolResult(
            name="gmail_search",
            payload={"query": query, "messages": messages},
        )

    def gmail_read_thread(self, thread_id: str) -> ToolResult:
        service = self._service("gmail", "v1")
        payload = service.users().threads().get(
            userId="me",
            id=thread_id,
            format="full",
        ).execute()
        messages: list[dict[str, Any]] = []
        for item in payload.get("messages", []):
            headers = _header_map(item.get("payload", {}).get("headers", []))
            messages.append(
                {
                    "id": item.get("id"),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "snippet": item.get("snippet", ""),
                    "body_excerpt": _extract_gmail_body(item.get("payload", {}))[:2500],
                }
            )
        self._log("gmail_read_thread", thread_id=thread_id, messages=len(messages))
        return ToolResult(
            name="gmail_read_thread",
            payload={"thread_id": thread_id, "messages": messages},
        )

    def gmail_draft(
        self,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> ToolResult:
        self._confirm_action(
            "Se va a crear un borrador en Gmail.\n"
            f"Para: {', '.join(to)}\n"
            f"Asunto: {subject}\n"
            "¿Confirmas?"
        )
        service = self._service("gmail", "v1")
        message = EmailMessage()
        message["To"] = ", ".join(to)
        if cc:
            message["Cc"] = ", ".join(cc)
        if bcc:
            message["Bcc"] = ", ".join(bcc)
        message["Subject"] = subject
        message.set_content(body)
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        payload = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": encoded}},
        ).execute()
        self._log("gmail_draft", to=to, subject=subject)
        return ToolResult(
            name="gmail_draft",
            payload={
                "id": payload.get("id"),
                "message_id": payload.get("message", {}).get("id"),
            },
        )

    def gcal_list_events(
        self,
        days: int = 7,
        max_results: int = 20,
        start_offset_days: int = 0,
        calendar_id: str | None = None,
    ) -> ToolResult:
        service = self._service("calendar", "v3")
        timezone = ZoneInfo(self._timezone_name)
        window_start = datetime.now(timezone).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ) + timedelta(days=max(0, start_offset_days))
        window_end = window_start + timedelta(days=days)
        payload = service.events().list(
            calendarId=calendar_id or self._default_calendar_id,
            timeMin=window_start.astimezone(UTC).isoformat(),
            timeMax=window_end.astimezone(UTC).isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        ).execute()
        events: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            start_value = item.get("start", {})
            end_value = item.get("end", {})
            start = start_value.get("dateTime") or start_value.get("date")
            end = end_value.get("dateTime") or end_value.get("date")
            events.append(
                {
                    "id": item.get("id"),
                    "summary": item.get("summary", ""),
                    "start": start,
                    "end": end,
                    "location": item.get("location"),
                    "description": item.get("description"),
                    "calendar_id": calendar_id or self._default_calendar_id,
                    "all_day": "date" in start_value,
                    "html_link": item.get("htmlLink"),
                }
            )
        self._log(
            "gcal_list_events",
            days=days,
            start_offset_days=start_offset_days,
            results=len(events),
        )
        return ToolResult(
            name="gcal_list_events",
            payload={
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "events": events,
            },
        )

    def gcal_create_event(
        self,
        summary: str,
        start_text: str,
        end_text: str | None = None,
        duration_minutes: int = 60,
        calendar_id: str | None = None,
        description: str | None = None,
        location: str | None = None,
    ) -> ToolResult:
        self._confirm_action(
            "Se va a crear un evento en Google Calendar.\n"
            f"Titulo: {summary}\n"
            f"Cuando: {start_text}\n"
            "¿Confirmas?"
        )
        timezone = ZoneInfo(self._timezone_name)
        start_at = parse_due_text(start_text, timezone_name=self._timezone_name).astimezone(
            timezone
        )
        if end_text:
            end_at = parse_due_text(end_text, timezone_name=self._timezone_name).astimezone(
                timezone
            )
        else:
            end_at = start_at + timedelta(minutes=max(1, duration_minutes))
        service = self._service("calendar", "v3")
        payload = service.events().insert(
            calendarId=calendar_id or self._default_calendar_id,
            body={
                "summary": summary,
                "description": description or "",
                "location": location or "",
                "start": {
                    "dateTime": start_at.isoformat(),
                    "timeZone": timezone.key,
                },
                "end": {
                    "dateTime": end_at.isoformat(),
                    "timeZone": timezone.key,
                },
            },
        ).execute()
        self._log("gcal_create_event", summary=summary, calendar_id=calendar_id or "primary")
        return ToolResult(
            name="gcal_create_event",
            payload={
                "id": payload.get("id"),
                "html_link": payload.get("htmlLink"),
                "summary": payload.get("summary"),
            },
        )

    def drive_search(self, query: str = "", max_results: int | None = None) -> ToolResult:
        service = self._service("drive", "v3")
        payload = service.files().list(
            q=_drive_query(query),
            pageSize=max_results or self._drive_default_max_results,
            fields=(
                "files(id,name,mimeType,modifiedTime,webViewLink,webContentLink,owners(displayName))"
            ),
            orderBy="modifiedTime desc",
        ).execute()
        files = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "mime_type": item.get("mimeType"),
                "modified_time": item.get("modifiedTime"),
                "web_view_link": item.get("webViewLink"),
                "web_content_link": item.get("webContentLink"),
                "owner": (item.get("owners") or [{}])[0].get("displayName", ""),
            }
            for item in payload.get("files", [])
        ]
        self._log("drive_search", query=query, results=len(files))
        return ToolResult(
            name="drive_search",
            payload={"query": query, "files": files},
        )

    def drive_read_file(self, file_id: str) -> ToolResult:
        service = self._service("drive", "v3")
        metadata = service.files().get(
            fileId=file_id,
            fields="id,name,mimeType,modifiedTime,webViewLink,webContentLink",
        ).execute()
        mime_type = str(metadata.get("mimeType", ""))
        content = ""
        supported = False
        if mime_type == "application/vnd.google-apps.document":
            content = self._download_drive_text(file_id, export_mime_type="text/plain")
            supported = True
        elif mime_type == "application/vnd.google-apps.spreadsheet":
            content = self._download_drive_text(file_id, export_mime_type="text/csv")
            supported = True
        elif mime_type in {
            "text/plain",
            "text/markdown",
            "text/csv",
            "application/json",
        } or mime_type.startswith("text/"):
            content = self._download_drive_text(file_id)
            supported = True
        self._log("drive_read_file", file_id=file_id, supported=supported)
        return ToolResult(
            name="drive_read_file",
            payload={
                "id": metadata.get("id"),
                "name": metadata.get("name"),
                "mime_type": mime_type,
                "modified_time": metadata.get("modifiedTime"),
                "web_view_link": metadata.get("webViewLink"),
                "supported_content": supported,
                "content": content[:12000],
            },
        )

    def _download_drive_text(
        self,
        file_id: str,
        *,
        export_mime_type: str | None = None,
    ) -> str:
        service = self._service("drive", "v3")
        request = (
            service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            if export_mime_type
            else service.files().get_media(fileId=file_id)
        )
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import-untyped]

        handle = io.BytesIO()
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
        return handle.getvalue().decode("utf-8", errors="replace")

    def _service(self, api_name: str, version: str) -> Any:
        if not self._enabled:
            raise RuntimeError("Los conectores Google están desactivados en config.")
        cache_key = (api_name, version)
        if cache_key in self._service_cache:
            return self._service_cache[cache_key]
        from googleapiclient.discovery import build  # type: ignore[import-untyped]

        service = build(
            api_name,
            version,
            credentials=self._credentials(),
            cache_discovery=False,
        )
        self._service_cache[cache_key] = service
        return service

    def _credentials(self) -> Any:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]

        credentials: Any | None = None
        if self._token_file.exists():
            credentials = Credentials.from_authorized_user_file(
                str(self._token_file),
                GOOGLE_WORKSPACE_SCOPES,
            )  # type: ignore[no-untyped-call]
        if credentials is not None and credentials.valid:
            return credentials
        if credentials is not None and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._write_token(credentials)
            return credentials
        if not self._client_secret_file.exists():
            raise RuntimeError(
                "Falta el archivo OAuth de Google. "
                f"Añádelo en {self._client_secret_file} o configura [google].client_secret_file."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self._client_secret_file),
            GOOGLE_WORKSPACE_SCOPES,
        )
        credentials = flow.run_local_server(port=0)
        self._write_token(credentials)
        return credentials

    def _write_token(self, credentials: Any) -> None:
        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        self._token_file.write_text(credentials.to_json(), encoding="utf-8")

    def _confirm_action(self, question: str) -> None:
        if not self._confirm(question):
            raise PermissionError("Acción de Google cancelada por el usuario.")

    def _log(self, event: str, **fields: object) -> None:
        if self._logger is not None:
            self._logger.log(event, **fields)


def build_google_workspace_tool_specs(tool: GoogleWorkspaceTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "gmail_search",
            "description": "Search Gmail messages and return recent matching emails.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.gmail_search,
        },
        {
            "name": "gmail_read_thread",
            "description": "Read a Gmail thread by thread id with message excerpts.",
            "schema": {
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string"},
                },
                "required": ["thread_id"],
            },
            "fn": tool.gmail_read_thread,
        },
        {
            "name": "gmail_draft",
            "description": "Create a Gmail draft after confirmation.",
            "schema": {
                "type": "object",
                "properties": {
                    "to": {"type": "array", "items": {"type": "string"}},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "cc": {"type": "array", "items": {"type": "string"}},
                    "bcc": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["to", "subject", "body"],
            },
            "fn": tool.gmail_draft,
        },
        {
            "name": "gcal_list_events",
            "description": "List upcoming events from Google Calendar.",
            "schema": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer"},
                    "max_results": {"type": "integer"},
                    "start_offset_days": {"type": "integer"},
                    "calendar_id": {"type": "string"},
                },
                "required": [],
            },
            "fn": tool.gcal_list_events,
        },
        {
            "name": "gcal_create_event",
            "description": "Create a Google Calendar event after confirmation.",
            "schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "start_text": {"type": "string"},
                    "end_text": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                    "calendar_id": {"type": "string"},
                    "description": {"type": "string"},
                    "location": {"type": "string"},
                },
                "required": ["summary", "start_text"],
            },
            "fn": tool.gcal_create_event,
        },
        {
            "name": "drive_search",
            "description": "Search Google Drive files by name or content.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tool.drive_search,
        },
        {
            "name": "drive_read_file",
            "description": "Read supported text content from a Google Drive file by file id.",
            "schema": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string"},
                },
                "required": ["file_id"],
            },
            "fn": tool.drive_read_file,
        },
    ]


def _header_map(headers: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in headers:
        key = str(item.get("name", "")).strip()
        if key:
            mapping[key] = str(item.get("value", ""))
    return mapping


def _extract_gmail_body(payload: dict[str, Any]) -> str:
    body_data = payload.get("body", {}).get("data")
    if isinstance(body_data, str) and body_data:
        try:
            return base64.urlsafe_b64decode(body_data.encode("utf-8")).decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            return ""
    for part in payload.get("parts", []) or []:
        if not isinstance(part, dict):
            continue
        mime_type = str(part.get("mimeType", ""))
        if mime_type in {"text/plain", "text/html"}:
            extracted = _extract_gmail_body(part)
            if extracted:
                return extracted
    return ""


def _drive_query(query: str) -> str:
    base = ["trashed = false"]
    terms = [token.strip() for token in query.split() if token.strip()]
    if not terms:
        return " and ".join(base)
    clauses: list[str] = []
    for term in terms[:4]:
        safe = term.replace("'", "\\'")
        clauses.append(f"name contains '{safe}'")
        clauses.append(f"fullText contains '{safe}'")
    base.append("(" + " or ".join(clauses) + ")")
    return " and ".join(base)
