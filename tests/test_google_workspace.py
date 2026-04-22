from __future__ import annotations

from pathlib import Path

import pytest

from adv_archon.tools.google_workspace import GoogleWorkspaceTools


class _FakeCall:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def execute(self) -> object:
        return self._payload


class _FakeGmailMessages:
    def list(self, *, userId: str, q: str | None, maxResults: int) -> _FakeCall:  # noqa: N803
        assert userId == "me"
        assert q == "acme"
        assert maxResults == 5
        return _FakeCall({"messages": [{"id": "m1"}]})

    def get(
        self,
        *,
        userId: str,  # noqa: N803
        id: str,
        format: str,
        metadataHeaders: list[str],  # noqa: N803
    ) -> _FakeCall:
        assert userId == "me"
        assert id == "m1"
        assert format == "metadata"
        assert metadataHeaders
        return _FakeCall(
            {
                "id": "m1",
                "threadId": "t1",
                "labelIds": ["INBOX"],
                "snippet": "Hola Acme",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Acme follow-up"},
                        {"name": "From", "value": "cliente@acme.com"},
                        {"name": "To", "value": "pablo@example.com"},
                    ]
                },
            }
        )


class _FakeGmailUsers:
    def messages(self) -> _FakeGmailMessages:
        return _FakeGmailMessages()


class _FakeGmailService:
    def users(self) -> _FakeGmailUsers:
        return _FakeGmailUsers()


class _FakeCalendarEvents:
    def list(self, **kwargs: object) -> _FakeCall:
        assert kwargs["calendarId"] == "primary"
        return _FakeCall(
            {
                "items": [
                    {
                        "id": "e1",
                        "summary": "Review",
                        "start": {"dateTime": "2026-04-22T09:00:00+02:00"},
                        "end": {"dateTime": "2026-04-22T10:00:00+02:00"},
                    }
                ]
            }
        )


class _FakeCalendarService:
    def events(self) -> _FakeCalendarEvents:
        return _FakeCalendarEvents()


class _FakeDriveFiles:
    def list(self, **kwargs: object) -> _FakeCall:
        assert "trashed = false" in str(kwargs["q"])
        return _FakeCall(
            {
                "files": [
                    {
                        "id": "f1",
                        "name": "propuesta-acme.md",
                        "mimeType": "text/markdown",
                        "modifiedTime": "2026-04-21T10:00:00Z",
                        "webViewLink": "https://drive.google.com/file/d/f1/view",
                        "owners": [{"displayName": "Pablo"}],
                    }
                ]
            }
        )


class _FakeDriveService:
    def files(self) -> _FakeDriveFiles:
        return _FakeDriveFiles()


def _build_tool(tmp_path: Path) -> GoogleWorkspaceTools:
    return GoogleWorkspaceTools(
        client_secret_file=tmp_path / "client.json",
        token_file=tmp_path / "token.json",
        confirm=lambda _question: True,
    )


def test_gmail_search_normalizes_messages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _build_tool(tmp_path)
    monkeypatch.setattr(tool, "_service", lambda api, version: _FakeGmailService())

    result = tool.gmail_search("acme", max_results=5)

    assert result.payload["messages"] == [
        {
            "id": "m1",
            "thread_id": "t1",
            "label_ids": ["INBOX"],
            "subject": "Acme follow-up",
            "from": "cliente@acme.com",
            "to": "pablo@example.com",
            "date": "",
            "snippet": "Hola Acme",
        }
    ]


def test_gcal_list_events_returns_normalized_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = _build_tool(tmp_path)
    monkeypatch.setattr(tool, "_service", lambda api, version: _FakeCalendarService())

    result = tool.gcal_list_events(days=1, start_offset_days=1, max_results=10)

    assert result.payload["events"][0]["summary"] == "Review"
    assert result.payload["events"][0]["all_day"] is False


def test_drive_search_returns_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _build_tool(tmp_path)
    monkeypatch.setattr(tool, "_service", lambda api, version: _FakeDriveService())

    result = tool.drive_search("propuesta acme", max_results=5)

    assert result.payload["files"][0]["name"] == "propuesta-acme.md"


def test_gmail_draft_requires_confirmation(tmp_path: Path) -> None:
    tool = GoogleWorkspaceTools(
        client_secret_file=tmp_path / "client.json",
        token_file=tmp_path / "token.json",
        confirm=lambda _question: False,
    )

    with pytest.raises(PermissionError):
        tool.gmail_draft(["cliente@acme.com"], "Seguimiento", "Hola")
