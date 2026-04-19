from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(slots=True)
class SessionMessage:
    role: str
    content: str
    name: str | None = None
    timestamp: str | None = None


class SessionStore:
    def __init__(self, sessions_dir: Path, *, persist: bool = True) -> None:
        self.persist = persist
        self.session_id = uuid4().hex
        self._messages: list[SessionMessage] = []
        self._path = sessions_dir / f"{self.session_id}.jsonl"

    @property
    def messages(self) -> list[SessionMessage]:
        return list(self._messages)

    def recent(self, limit: int = 8) -> list[SessionMessage]:
        return self._messages[-limit:]

    def append(self, message: SessionMessage) -> None:
        stamped = SessionMessage(
            role=message.role,
            content=message.content,
            name=message.name,
            timestamp=datetime.now(UTC).isoformat(),
        )
        self._messages.append(stamped)
        if not self.persist:
            return
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(stamped), ensure_ascii=False) + "\n")
