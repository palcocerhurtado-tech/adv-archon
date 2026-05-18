from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from personality.context_builder import _ensure_schema


def evolve_personality(interaction_summary: str, *, db_path: Path) -> None:
    """Extension point for future adaptive personality evolution.

    FASE futura: extraer patrones, actualizar pesos, marcar eventos significativos
    y generar un resumen comprimido con un modelo local pequeño. En FASE 2 solo
    deja trazabilidad local y asegura el esquema SQLite.
    """
    _ensure_schema(db_path)
    log_path = db_path.parent / "evolution.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat()
    clean_summary = " ".join(interaction_summary.split()) or "session_closed"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{timestamp}\t{clean_summary}\n")
