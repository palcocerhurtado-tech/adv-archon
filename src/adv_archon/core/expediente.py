from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class Expediente:
    id: str
    title: str
    address: str
    municipality: str
    province: str
    latitude: float | None
    longitude: float | None
    cadastral_ref: str
    status: str
    plan_path: str
    site_context: str
    analysis_result: str
    report_path: str
    created_at: str
    updated_at: str
    notes: str
    case_type: str = "cambio_uso_vivienda"


class ExpedienteStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = self._connect()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        self._migrate(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS expedientes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                address TEXT NOT NULL DEFAULT '',
                municipality TEXT NOT NULL DEFAULT '',
                province TEXT NOT NULL DEFAULT '',
                latitude REAL,
                longitude REAL,
                cadastral_ref TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'borrador',
                plan_path TEXT NOT NULL DEFAULT '',
                site_context TEXT NOT NULL DEFAULT '',
                analysis_result TEXT NOT NULL DEFAULT '',
                report_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                case_type TEXT NOT NULL DEFAULT 'cambio_uso_vivienda'
            );
        """)
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(expedientes)").fetchall()
        }
        columns = {
            "address": "TEXT NOT NULL DEFAULT ''",
            "municipality": "TEXT NOT NULL DEFAULT ''",
            "province": "TEXT NOT NULL DEFAULT ''",
            "latitude": "REAL",
            "longitude": "REAL",
            "cadastral_ref": "TEXT NOT NULL DEFAULT ''",
            "status": "TEXT NOT NULL DEFAULT 'borrador'",
            "plan_path": "TEXT NOT NULL DEFAULT ''",
            "site_context": "TEXT NOT NULL DEFAULT ''",
            "analysis_result": "TEXT NOT NULL DEFAULT ''",
            "report_path": "TEXT NOT NULL DEFAULT ''",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
            "notes": "TEXT NOT NULL DEFAULT ''",
            "case_type": "TEXT NOT NULL DEFAULT 'cambio_uso_vivienda'",
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE expedientes ADD COLUMN {name} {definition}")

        now = datetime.now(UTC).isoformat()
        conn.execute("UPDATE expedientes SET created_at = ? WHERE created_at = ''", (now,))
        conn.execute("UPDATE expedientes SET updated_at = ? WHERE updated_at = ''", (now,))
        conn.commit()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def create(
        self,
        *,
        title: str,
        address: str,
        municipality: str = "",
        province: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
        cadastral_ref: str = "",
        notes: str = "",
        case_type: str = "cambio_uso_vivienda",
    ) -> Expediente:
        now = datetime.now(UTC).isoformat()
        expediente = Expediente(
            id=str(uuid.uuid4()),
            title=title,
            address=address,
            municipality=municipality,
            province=province,
            latitude=latitude,
            longitude=longitude,
            cadastral_ref=cadastral_ref,
            status="borrador",
            plan_path="",
            site_context="",
            analysis_result="",
            report_path="",
            created_at=now,
            updated_at=now,
            notes=notes,
            case_type=case_type,
        )
        self._conn.execute(
            """
            INSERT INTO expedientes (
                id, title, address, municipality, province,
                latitude, longitude, cadastral_ref, status,
                plan_path, site_context, analysis_result, report_path,
                created_at, updated_at, notes, case_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expediente.id,
                expediente.title,
                expediente.address,
                expediente.municipality,
                expediente.province,
                expediente.latitude,
                expediente.longitude,
                expediente.cadastral_ref,
                expediente.status,
                expediente.plan_path,
                expediente.site_context,
                expediente.analysis_result,
                expediente.report_path,
                expediente.created_at,
                expediente.updated_at,
                expediente.notes,
                expediente.case_type,
            ),
        )
        self._conn.commit()
        return expediente

    def get(self, expediente_id: str) -> Expediente | None:
        row = self._conn.execute(
            "SELECT * FROM expedientes WHERE id = ?", (expediente_id,)
        ).fetchone()
        return self._row_to_expediente(row) if row else None

    def list_all(self) -> list[Expediente]:
        rows = self._conn.execute(
            "SELECT * FROM expedientes ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_expediente(r) for r in rows]

    def update(self, expediente: Expediente) -> None:
        now = datetime.now(UTC).isoformat()
        expediente.updated_at = now
        self._conn.execute(
            """
            UPDATE expedientes SET
                title = ?,
                address = ?,
                municipality = ?,
                province = ?,
                latitude = ?,
                longitude = ?,
                cadastral_ref = ?,
                status = ?,
                plan_path = ?,
                site_context = ?,
                analysis_result = ?,
                report_path = ?,
                updated_at = ?,
                notes = ?,
                case_type = ?
            WHERE id = ?
            """,
            (
                expediente.title,
                expediente.address,
                expediente.municipality,
                expediente.province,
                expediente.latitude,
                expediente.longitude,
                expediente.cadastral_ref,
                expediente.status,
                expediente.plan_path,
                expediente.site_context,
                expediente.analysis_result,
                expediente.report_path,
                expediente.updated_at,
                expediente.notes,
                expediente.case_type,
                expediente.id,
            ),
        )
        self._conn.commit()

    def delete(self, expediente_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM expedientes WHERE id = ?", (expediente_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _row_to_expediente(row: sqlite3.Row) -> Expediente:
        return Expediente(
            id=row["id"],
            title=row["title"],
            address=row["address"],
            municipality=row["municipality"],
            province=row["province"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            cadastral_ref=row["cadastral_ref"],
            status=row["status"],
            plan_path=row["plan_path"],
            site_context=row["site_context"],
            analysis_result=row["analysis_result"],
            report_path=row["report_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            notes=row["notes"],
            case_type=row["case_type"],
        )


__all__ = ["Expediente", "ExpedienteStore"]
