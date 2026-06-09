from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkspaceAction:
    id: str
    title: str
    subtitle: str
    target: str
    priority: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "target": self.target,
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceStatus:
    label: str
    value: str
    status: str

    def to_dict(self) -> dict[str, str]:
        return {
            "label": self.label,
            "value": self.value,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceDocument:
    path: str
    title: str
    kind: str
    updated_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "title": self.title,
            "kind": self.kind,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    actions: tuple[WorkspaceAction, ...]
    statuses: tuple[WorkspaceStatus, ...]
    documents: tuple[WorkspaceDocument, ...]
    recent_activity: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions": [action.to_dict() for action in self.actions],
            "statuses": [status.to_dict() for status in self.statuses],
            "documents": [document.to_dict() for document in self.documents],
            "recent_activity": list(self.recent_activity),
        }


def build_default_workspace_actions() -> tuple[WorkspaceAction, ...]:
    """Return the canonical actions for Home Workspace V2."""

    return (
        WorkspaceAction(
            id="new-expediente",
            title="Nuevo expediente",
            subtitle="Crear o importar un caso urbanistico",
            target="expediente:new",
            priority=10,
        ),
        WorkspaceAction(
            id="research-workbench",
            title="Research Workbench",
            subtitle="Investigar normativa, formulas y fuentes",
            target="research:open",
            priority=20,
        ),
        WorkspaceAction(
            id="generated-documents",
            title="Documentos generados",
            subtitle="Revisar informes, memorias y hojas de calculo",
            target="documents:generated",
            priority=30,
        ),
        WorkspaceAction(
            id="system-status",
            title="Estado del sistema",
            subtitle="Comprobar motor local, modelo y diagnostico",
            target="system:status",
            priority=40,
        ),
        WorkspaceAction(
            id="recent-activity",
            title="Ultima actividad",
            subtitle="Continuar desde el trabajo mas reciente",
            target="activity:recent",
            priority=50,
        ),
        WorkspaceAction(
            id="quick-actions",
            title="Acciones rapidas",
            subtitle="Abrir atajos frecuentes del estudio",
            target="actions:quick",
            priority=60,
        ),
    )


def discover_generated_documents(
    root_dirs: Iterable[str | Path],
    limit: int = 8,
    max_depth: int = 2,
    max_entries: int = 1_500,
) -> tuple[WorkspaceDocument, ...]:
    """Discover generated ADV ARCHON documents without importing UI modules."""

    if limit <= 0:
        return ()

    documents: list[WorkspaceDocument] = []
    seen: set[Path] = set()
    for root in root_dirs:
        root_path = Path(root).expanduser()
        if not root_path.exists() or not root_path.is_dir():
            continue
        for path in _iter_candidate_files(
            root_path,
            max_depth=max_depth,
            max_entries=max_entries,
        ):
            if not path.is_file() or path.suffix.casefold() not in _DOCUMENT_SUFFIXES:
                continue
            if not _looks_generated(path):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                stat = path.stat()
            except OSError:
                continue
            documents.append(
                WorkspaceDocument(
                    path=str(resolved),
                    title=_document_title(path),
                    kind=path.suffix.lower().lstrip("."),
                    updated_at=_iso_from_timestamp(stat.st_mtime),
                )
            )

    documents.sort(key=lambda item: (item.updated_at, item.title.casefold()), reverse=True)
    return tuple(documents[:limit])


def build_workspace_snapshot(
    root_dirs: Iterable[str | Path],
    engine_status: str,
    ollama_model: str,
    last_expediente: str = "",
) -> WorkspaceSnapshot:
    documents = discover_generated_documents(root_dirs)
    statuses: tuple[WorkspaceStatus, ...] = (
        WorkspaceStatus(
            label="Motor",
            value=_clean_label(engine_status, default="Pendiente"),
            status=_status_level(engine_status),
        ),
        WorkspaceStatus(
            label="Modelo",
            value=_clean_label(ollama_model, default="Sin modelo"),
            status="ok" if str(ollama_model or "").strip() else "warning",
        ),
        WorkspaceStatus(
            label="Documentos",
            value=str(len(documents)),
            status="ok" if documents else "idle",
        ),
    )
    if last_expediente.strip():
        statuses += (
            WorkspaceStatus(
                label="Expediente",
                value=last_expediente.strip(),
                status="active",
            ),
        )

    return WorkspaceSnapshot(
        actions=build_default_workspace_actions(),
        statuses=statuses,
        documents=documents,
        recent_activity=_build_recent_activity(documents, last_expediente),
    )


_DOCUMENT_SUFFIXES = {".pdf", ".docx", ".xlsx"}
_GENERATED_NAME_TERMS = (
    "adv_archon",
    "archon",
    "informe",
    "memoria",
    "expediente",
    "research",
    "workbench",
    "proyecto",
)


def _iter_candidate_files(
    root_path: Path,
    *,
    max_depth: int,
    max_entries: int,
) -> Iterable[Path]:
    """Yield files from a shallow bounded scan so Home stays responsive."""

    visited = 0
    stack: list[tuple[Path, int]] = [(root_path, 0)]
    while stack and visited < max_entries:
        current, depth = stack.pop()
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for child in children:
            visited += 1
            if visited > max_entries:
                break
            if child.is_file():
                yield child
            elif child.is_dir() and depth < max_depth and not child.name.startswith("."):
                stack.append((child, depth + 1))


def _looks_generated(path: Path) -> bool:
    name = path.stem.casefold()
    return any(term in name for term in _GENERATED_NAME_TERMS)


def _document_title(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.name


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _clean_label(value: str, *, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def _status_level(engine_status: str) -> str:
    normalized = str(engine_status or "").strip().casefold()
    if normalized in {"ok", "listo", "ready", "online", "cloud"}:
        return "ok"
    if normalized in {"sin conexion", "sin conexión", "offline", "error", "fallo"}:
        return "error"
    if normalized in {"cargando", "cargando...", "cargando…", "pendiente", "loading"}:
        return "warning"
    return "idle" if not normalized else "warning"


def _build_recent_activity(
    documents: Sequence[WorkspaceDocument],
    last_expediente: str,
) -> tuple[str, ...]:
    activity: list[str] = []
    if last_expediente.strip():
        activity.append(f"Expediente activo: {last_expediente.strip()}")
    for document in documents[:3]:
        activity.append(f"Documento actualizado: {document.title}")
    if not activity:
        activity.append("Sin actividad reciente")
    return tuple(activity)


__all__ = [
    "WorkspaceAction",
    "WorkspaceDocument",
    "WorkspaceSnapshot",
    "WorkspaceStatus",
    "build_default_workspace_actions",
    "build_workspace_snapshot",
    "discover_generated_documents",
]
