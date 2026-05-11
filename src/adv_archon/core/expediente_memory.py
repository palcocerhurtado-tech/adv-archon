from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adv_archon.core.expediente import Expediente
    from adv_archon.core.memory import MemoryRecord, MemoryStore


def snapshot_expediente(
    expediente: Expediente,
    memory_store: MemoryStore,
) -> MemoryRecord:
    """Save a context snapshot of the expediente under its own namespace.

    Idempotent — if a snapshot already exists, the MemoryStore upserts it.
    Returns the saved MemoryRecord.
    """
    notes = expediente.notes or ""
    content = (
        f"Expediente: {expediente.title}. "
        f"Dirección: {expediente.address}, {expediente.municipality} ({expediente.province}). "
        f"Ref. catastral: {expediente.cadastral_ref}. "
        f"Estado: {expediente.status}."
        + (f" Notas: {notes}" if notes else "")
    ).strip()
    tags: list[str] = ["expediente"]
    if expediente.municipality:
        tags.append(expediente.municipality)
    return memory_store.remember(
        content,
        tags=tags,
        source="expediente",
        memory_type="context",
        namespace=expediente.id,
        importance=8,
    )


def recall_expediente_context(
    expediente_id: str,
    memory_store: MemoryStore,
    *,
    limit: int = 20,
) -> list[MemoryRecord]:
    """Return all memories for this expediente, ordered by importance desc."""
    records = memory_store.recall(
        "",
        limit=limit,
        namespace=expediente_id,
    )
    return sorted(records, key=lambda r: r.importance, reverse=True)
