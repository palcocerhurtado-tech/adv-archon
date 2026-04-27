from __future__ import annotations

import mimetypes
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Role = Literal["user", "assistant", "system"]

_DOCUMENT_SUFFIXES = {
    ".doc",
    ".docx",
    ".md",
    ".odt",
    ".pages",
    ".pdf",
    ".rtf",
    ".txt",
}
_SPREADSHEET_SUFFIXES = {".csv", ".numbers", ".ods", ".tsv", ".xls", ".xlsx"}
_PRESENTATION_SUFFIXES = {".odp", ".key", ".ppt", ".pptx"}
_IMAGE_SUFFIXES = {".avif", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".tiff", ".webp"}
_AUDIO_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}
_VIDEO_SUFFIXES = {".m4v", ".mov", ".mp4", ".mkv", ".webm"}
_CODE_SUFFIXES = {
    ".c",
    ".cpp",
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".json",
    ".kt",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".xml",
    ".yaml",
    ".yml",
}
_ARCHIVE_SUFFIXES = {".7z", ".dmg", ".gz", ".rar", ".tar", ".zip"}


def format_bytes(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "size unknown"
    value = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


def _classify_kind(path: Path, mime_type: str | None) -> str:
    suffix = path.suffix.lower()
    if path.exists() and path.is_dir():
        return "folder"
    if suffix in _DOCUMENT_SUFFIXES:
        return "document"
    if suffix in _SPREADSHEET_SUFFIXES:
        return "spreadsheet"
    if suffix in _PRESENTATION_SUFFIXES:
        return "presentation"
    if suffix in _IMAGE_SUFFIXES:
        return "image"
    if suffix in _AUDIO_SUFFIXES:
        return "audio"
    if suffix in _VIDEO_SUFFIXES:
        return "video"
    if suffix in _CODE_SUFFIXES:
        return "code"
    if suffix in _ARCHIVE_SUFFIXES:
        return "archive"
    if mime_type is None:
        return "file"
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("text/"):
        return "document"
    return "file"


@dataclass(frozen=True, slots=True)
class DesktopAttachment:
    path: Path
    display_name: str
    kind: str
    size_bytes: int | None
    mime_type: str | None

    @classmethod
    def from_path(cls, raw_path: str | Path) -> DesktopAttachment:
        raw = Path(raw_path).expanduser()
        resolved = raw.resolve(strict=False)
        mime_type, _encoding = mimetypes.guess_type(str(resolved))
        size_bytes: int | None = None
        if resolved.exists() and resolved.is_file():
            size_bytes = resolved.stat().st_size
        return cls(
            path=resolved,
            display_name=resolved.name or str(resolved),
            kind=_classify_kind(resolved, mime_type),
            size_bytes=size_bytes,
            mime_type=mime_type,
        )

    @property
    def is_directory(self) -> bool:
        return self.kind == "folder"

    def summary(self) -> str:
        details = [self.kind]
        if self.size_bytes is not None and not self.is_directory:
            details.append(format_bytes(self.size_bytes))
        return f"{self.display_name} ({' · '.join(details)})"


def collect_attachments(paths: Iterable[str | Path]) -> list[DesktopAttachment]:
    seen: set[Path] = set()
    attachments: list[DesktopAttachment] = []
    for raw_path in paths:
        attachment = DesktopAttachment.from_path(raw_path)
        if attachment.path in seen:
            continue
        seen.add(attachment.path)
        attachments.append(attachment)
    return attachments


@dataclass(frozen=True, slots=True)
class DesktopChatMessage:
    role: Role
    text: str
    attachments: tuple[DesktopAttachment, ...] = ()


@dataclass(frozen=True, slots=True)
class DesktopChatRequest:
    prompt: str
    attachments: tuple[DesktopAttachment, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.prompt.strip() and not self.attachments


@dataclass(frozen=True, slots=True)
class DesktopChatResponse:
    text: str
    used_attachments: tuple[DesktopAttachment, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)
