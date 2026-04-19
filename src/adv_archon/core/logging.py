from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import structlog


@dataclass(slots=True)
class LogEntry:
    timestamp: str
    session_id: str
    event: str
    fields: dict[str, Any]


class AppLogger:
    def __init__(self, logs_dir: Path, *, session_id: str, persist: bool = True) -> None:
        self._logs_dir = logs_dir
        self._session_id = session_id
        self._persist = persist
        self._renderer = structlog.processors.JSONRenderer(sort_keys=True)
        self._buffer: list[LogEntry] = []

    def log(self, event: str, **fields: Any) -> LogEntry:
        entry = LogEntry(
            timestamp=datetime.now().astimezone().isoformat(),
            session_id=self._session_id,
            event=event,
            fields={key: _sanitize_value(value) for key, value in fields.items()},
        )
        self._buffer.append(entry)
        if self._persist:
            self._logs_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "timestamp": entry.timestamp,
                "session_id": entry.session_id,
                "event": entry.event,
                **entry.fields,
            }
            rendered = cast(str, self._renderer(None, "log", payload))
            with self._log_path().open("a", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.write("\n")
        return entry

    def recent(self, limit: int = 10) -> list[LogEntry]:
        return self._buffer[-limit:]

    def _log_path(self) -> Path:
        return self._logs_dir / f"archon-{date.today().isoformat()}.jsonl"

    @property
    def session_id(self) -> str:
        return self._session_id


def read_log_entries(
    logs_dir: Path,
    *,
    day: date | None = None,
    limit: int | None = None,
) -> list[LogEntry]:
    target_day = day or date.today()
    log_path = logs_dir / f"archon-{target_day.isoformat()}.jsonl"
    if not log_path.exists():
        return []
    entries: list[LogEntry] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            timestamp = payload.pop("timestamp", "")
            session_id = payload.pop("session_id", "")
            event = payload.pop("event", "")
            if not (
                isinstance(timestamp, str)
                and isinstance(session_id, str)
                and isinstance(event, str)
            ):
                continue
            entries.append(
                LogEntry(
                    timestamp=timestamp,
                    session_id=session_id,
                    event=event,
                    fields=payload,
                )
            )
    if limit is not None:
        return entries[-limit:]
    return entries


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value
