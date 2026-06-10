from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from adv_archon.core.document_draft import DocumentDraft

# SQL identifiers (column names) may only ever come from internal allowlists.
# This guard makes that invariant explicit and defends against accidental
# interpolation of untrusted input into DDL/DML statements.
_SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(name: str) -> str:
    if not _SQL_IDENTIFIER.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


@dataclass(frozen=True, slots=True)
class DocumentDraftRecord:
    draft: DocumentDraft
    created_at: str
    updated_at: str
    exported_pdf_path: str = ""
    exported_docx_path: str = ""
    exported_xlsx_path: str = ""


class DocumentStore:
    """SQLite store for editable office document drafts."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path.expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS document_drafts (
                id TEXT PRIMARY KEY,
                expediente_id TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT 'expediente',
                title TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                exported_pdf_path TEXT NOT NULL DEFAULT '',
                exported_docx_path TEXT NOT NULL DEFAULT '',
                exported_xlsx_path TEXT NOT NULL DEFAULT ''
            );
            """
        )
        existing = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(document_drafts)")
        }
        columns = {
            "expediente_id": "TEXT NOT NULL DEFAULT ''",
            "kind": "TEXT NOT NULL DEFAULT 'expediente'",
            "title": "TEXT NOT NULL DEFAULT ''",
            "draft_json": "TEXT NOT NULL DEFAULT '{}'",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
            "exported_pdf_path": "TEXT NOT NULL DEFAULT ''",
            "exported_docx_path": "TEXT NOT NULL DEFAULT ''",
            "exported_xlsx_path": "TEXT NOT NULL DEFAULT ''",
        }
        for name, definition in columns.items():
            if name not in existing:
                self._conn.execute(
                    f"ALTER TABLE document_drafts "
                    f"ADD COLUMN {_safe_identifier(name)} {definition}"
                )
        self._conn.commit()

    def save_draft(self, draft: DocumentDraft) -> DocumentDraft:
        draft_id = draft.id or str(uuid.uuid4())
        saved = draft.with_id(draft_id)
        now = datetime.now(UTC).isoformat()
        row = self._conn.execute(
            "SELECT created_at FROM document_drafts WHERE id = ?",
            (draft_id,),
        ).fetchone()
        created_at = str(row["created_at"]) if row else now
        self._conn.execute(
            """
            INSERT INTO document_drafts (
                id, expediente_id, kind, title, draft_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                expediente_id = excluded.expediente_id,
                kind = excluded.kind,
                title = excluded.title,
                draft_json = excluded.draft_json,
                updated_at = excluded.updated_at
            """,
            (
                saved.id,
                saved.expediente_id,
                saved.kind,
                saved.title,
                saved.to_json(),
                created_at,
                now,
            ),
        )
        self._conn.commit()
        return saved

    def get_draft(self, draft_id: str) -> DocumentDraft | None:
        record = self.get_record(draft_id)
        return record.draft if record else None

    def get_record(self, draft_id: str) -> DocumentDraftRecord | None:
        row = self._conn.execute(
            "SELECT * FROM document_drafts WHERE id = ?",
            (draft_id,),
        ).fetchone()
        return _row_to_record(row) if row else None

    def list_drafts(
        self,
        *,
        expediente_id: str | None = None,
        kind: str | None = None,
    ) -> list[DocumentDraft]:
        query = "SELECT * FROM document_drafts"
        clauses: list[str] = []
        params: list[str] = []
        if expediente_id is not None:
            clauses.append("expediente_id = ?")
            params.append(expediente_id)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC, created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [_row_to_record(row).draft for row in rows]

    def mark_exported(self, draft_id: str, file_type: str, output_path: Path) -> bool:
        column = {
            "pdf": "exported_pdf_path",
            "docx": "exported_docx_path",
            "xlsx": "exported_xlsx_path",
        }.get(file_type.lower().lstrip("."))
        if column is None:
            raise ValueError("file_type must be one of: pdf, docx, xlsx")
        cursor = self._conn.execute(
            f"UPDATE document_drafts SET {_safe_identifier(column)} = ?, "
            f"updated_at = ? WHERE id = ?",
            (str(output_path.expanduser()), datetime.now(UTC).isoformat(), draft_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete_draft(self, draft_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM document_drafts WHERE id = ?", (draft_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        self._conn.close()


def _row_to_record(row: sqlite3.Row) -> DocumentDraftRecord:
    return DocumentDraftRecord(
        draft=DocumentDraft.from_json(str(row["draft_json"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        exported_pdf_path=str(row["exported_pdf_path"] or ""),
        exported_docx_path=str(row["exported_docx_path"] or ""),
        exported_xlsx_path=str(row["exported_xlsx_path"] or ""),
    )
