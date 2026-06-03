"""Modo equipo: export/import de expedientes como .archon y sincronización
de stores hacia una carpeta compartida (NAS, iCloud, Dropbox…).

Configuración en ~/.adv-archon/config.toml:
    [team]
    enabled = true
    shared_data_path = "/Volumes/NAS-Despacho/adv-archon-compartido"
    user_name = "Pablo"
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adv_archon.core.config import AppConfig
    from adv_archon.core.expediente import Expediente, ExpedienteStore

_FORMAT_VERSION = "1"


# ── Export ─────────────────────────────────────────────────────────────────────

def export_expediente(
    expediente: Expediente,
    output_path: Path | None = None,
    *,
    author: str = "",
) -> Path:
    """Export an expediente as a .archon JSON file for sharing with teammates."""
    payload: dict[str, Any] = {
        "format": "adv-archon-expediente",
        "version": _FORMAT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "author": author,
        "expediente": asdict(expediente),
    }
    name = f"{expediente.id[:8]}_{expediente.title[:30].replace(' ', '_')}.archon"
    out = output_path or Path.home() / "Desktop" / name
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def import_expediente(
    archon_path: Path,
    store: ExpedienteStore,
    *,
    overwrite: bool = False,
) -> Expediente:
    """Import a .archon file into the local ExpedienteStore.

    If overwrite=False and the expediente id already exists, raises ValueError.
    """
    from adv_archon.core.expediente import Expediente

    raw = json.loads(archon_path.read_text(encoding="utf-8"))
    if raw.get("format") != "adv-archon-expediente":
        raise ValueError(f"{archon_path.name} no es un archivo .archon válido.")

    data = raw["expediente"]
    exp = Expediente(**data)

    existing = store.get(exp.id)
    if existing is not None and not overwrite:
        raise ValueError(
            f"El expediente «{exp.title}» (id={exp.id}) ya existe. "
            "Usa overwrite=True para sobreescribirlo."
        )

    if existing is None:
        store._conn.execute(  # noqa: SLF001
            """
            INSERT INTO expedientes
              (id, title, address, municipality, province,
               latitude, longitude, cadastral_ref, status,
               plan_path, site_context, analysis_result, report_path,
               created_at, updated_at, notes, case_type, review_state,
               quality_score, quality_result, agent_history, agent_step_reviews)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                exp.id, exp.title, exp.address, exp.municipality, exp.province,
                exp.latitude, exp.longitude, exp.cadastral_ref, exp.status,
                exp.plan_path, exp.site_context, exp.analysis_result, exp.report_path,
                exp.created_at, exp.updated_at, exp.notes, exp.case_type,
                exp.review_state, exp.quality_score, exp.quality_result,
                exp.agent_history, exp.agent_step_reviews,
            ),
        )
        store._conn.commit()  # noqa: SLF001
    else:
        store.update(exp)

    return exp


# ── Sync to shared folder ──────────────────────────────────────────────────────

def sync_shared_knowledge(config: AppConfig) -> dict[str, Any]:
    """Copy the local knowledge.db to the shared folder (and pull others' files).

    The shared folder structure:
        <shared_data_path>/
          knowledge/
            <user_name>.db      ← this user's knowledge index
            other_user.db       ← other team members' indices (read-only merge)
          expedientes/
            <id>.archon         ← exported expedientes

    Returns a summary dict with files pushed and pulled.
    """
    if not config.team.enabled or not config.team.shared_data_path:
        return {"ok": False, "error": "Modo equipo no habilitado o sin ruta compartida."}

    shared = Path(config.team.shared_data_path).expanduser()
    if not shared.exists():
        return {"ok": False, "error": f"La carpeta compartida no existe: {shared}"}

    user = config.team.user_name or "usuario"
    shared_knowledge = shared / "knowledge"
    shared_knowledge.mkdir(parents=True, exist_ok=True)

    # Push local knowledge.db
    local_kb = config.paths.knowledge_db
    dest = shared_knowledge / f"{user}.db"
    pushed = False
    if local_kb.exists():
        shutil.copy2(local_kb, dest)
        pushed = True

    # Pull other members' knowledge chunks into local db
    pulled_from: list[str] = []
    for remote_db in shared_knowledge.glob("*.db"):
        if remote_db.stem == user:
            continue
        try:
            _merge_knowledge_db(local_kb, remote_db)
            pulled_from.append(remote_db.stem)
        except Exception:
            pass

    return {
        "ok": True,
        "pushed": str(dest) if pushed else "",
        "pulled_from": pulled_from,
        "shared_path": str(shared),
    }


def _merge_knowledge_db(local: Path, remote: Path) -> None:
    """Merge knowledge_entries from remote SQLite into local — no duplicates."""
    if not local.exists():
        shutil.copy2(remote, local)
        return
    with sqlite3.connect(local) as loc_conn:
        loc_conn.execute(f"ATTACH DATABASE '{remote}' AS remote")
        loc_conn.execute(
            """
            INSERT OR IGNORE INTO knowledge_entries
            SELECT * FROM remote.knowledge_entries
            """
        )
        loc_conn.commit()
        loc_conn.execute("DETACH DATABASE remote")


# ── Tool wrapper ───────────────────────────────────────────────────────────────

class TeamTools:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._exp_store: Any = None

    def set_expediente_store(self, store: Any) -> None:
        self._exp_store = store

    def exportar_expediente(
        self,
        expediente_id: str,
        ruta_salida: str = "",
    ) -> dict[str, Any]:
        if self._exp_store is None:
            return {"ok": False, "error": "Sin ExpedienteStore configurado."}
        exp = self._exp_store.get(expediente_id)
        if exp is None:
            return {"ok": False, "error": f"Expediente {expediente_id!r} no encontrado."}
        out = export_expediente(
            exp,
            Path(ruta_salida).expanduser() if ruta_salida else None,
            author=self._config.team.user_name,
        )
        return {"ok": True, "archivo": str(out)}

    def importar_expediente(
        self,
        ruta_archivo: str,
        sobreescribir: bool = False,
    ) -> dict[str, Any]:
        if self._exp_store is None:
            return {"ok": False, "error": "Sin ExpedienteStore configurado."}
        path = Path(ruta_archivo).expanduser()
        if not path.exists():
            return {"ok": False, "error": f"Archivo no encontrado: {path}"}
        try:
            exp = import_expediente(path, self._exp_store, overwrite=sobreescribir)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "expediente": exp.title, "id": exp.id}

    def sincronizar_conocimiento(self) -> dict[str, Any]:
        return sync_shared_knowledge(self._config)
