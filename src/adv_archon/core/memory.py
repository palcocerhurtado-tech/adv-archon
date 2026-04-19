from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from adv_archon.core.logging import AppLogger


class EmbeddingEncoder(Protocol):
    def encode_texts(self, texts: Sequence[str]) -> np.ndarray: ...


@dataclass(slots=True)
class MemoryRecord:
    id: int
    content: str
    tags: list[str]
    source: str
    created_at: str
    updated_at: str
    score: float | None = None


class SentenceTransformerEncoder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: Any | None = None

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        model = self._load_model()
        embeddings = model.encode(
            list(texts),
            normalize_embeddings=True,
        )
        return np.asarray(embeddings, dtype=np.float32)

    def _load_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model


class MemoryStore:
    def __init__(
        self,
        db_path: Path,
        *,
        persist: bool = True,
        encoder: EmbeddingEncoder | None = None,
        logger: AppLogger | None = None,
    ) -> None:
        self._db_path = db_path
        self._persist = persist
        self._encoder = encoder or SentenceTransformerEncoder()
        self._logger = logger
        self._conn = self._connect()

    def remember(
        self,
        content: str,
        tags: Sequence[str] | None = None,
        *,
        source: str = "manual",
    ) -> MemoryRecord:
        if not self._persist:
            raise PermissionError("El modo incógnito no permite escribir memoria persistente.")

        clean_content = content.strip()
        if not clean_content:
            raise ValueError("No se puede recordar un texto vacío.")
        clean_tags = _normalize_tags(tags or [])
        vector = self._encode_text(clean_content, clean_tags)
        timestamp = datetime.now(UTC).isoformat()
        existing = self._conn.execute(
            """
            SELECT id, content, tags_json, source, created_at, updated_at, embedding_json
            FROM memories
            WHERE content = ?
            """,
            (clean_content,),
        ).fetchone()

        if existing is None:
            cursor = self._conn.execute(
                """
                INSERT INTO memories (
                    content,
                    tags_json,
                    source,
                    embedding_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_content,
                    json.dumps(clean_tags, ensure_ascii=False),
                    source,
                    json.dumps(vector.tolist()),
                    timestamp,
                    timestamp,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite no devolvió el id de la nueva memoria.")
            memory_id = int(cursor.lastrowid)
        else:
            merged_tags = _normalize_tags(
                [*json.loads(existing["tags_json"]), *clean_tags]
            )
            memory_id = int(existing["id"])
            self._conn.execute(
                """
                UPDATE memories
                SET tags_json = ?, source = ?, embedding_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(merged_tags, ensure_ascii=False),
                    source,
                    json.dumps(vector.tolist()),
                    timestamp,
                    memory_id,
                ),
            )

        self._conn.commit()
        record = self.get_by_id(memory_id)
        if record is None:
            raise RuntimeError("No se pudo recuperar la memoria recién guardada.")
        if self._logger is not None:
            self._logger.log("memory_remembered", memory_id=record.id, tags=record.tags)
        return record

    def recall(self, query: str, *, limit: int = 5) -> list[MemoryRecord]:
        rows = self._conn.execute(
            """
            SELECT id, content, tags_json, source, created_at, updated_at, embedding_json
            FROM memories
            ORDER BY updated_at DESC
            """
        ).fetchall()
        if not rows:
            return []

        query_vector = _normalize_vector(self._encoder.encode_texts([query])[0])
        matrix = np.vstack(
            [
                _normalize_vector(
                    np.asarray(json.loads(str(row["embedding_json"])), dtype=np.float32)
                )
                for row in rows
            ]
        )
        scores = matrix @ query_vector

        ranked: list[MemoryRecord] = []
        lowered_query = query.lower()
        for row, score in zip(rows, scores.tolist(), strict=True):
            lexical_bonus = 0.0
            content = str(row["content"])
            tags = json.loads(str(row["tags_json"]))
            if lowered_query and lowered_query in content.lower():
                lexical_bonus += 0.1
            if any(lowered_query in tag.lower() for tag in tags):
                lexical_bonus += 0.05
            ranked.append(
                MemoryRecord(
                    id=int(row["id"]),
                    content=content,
                    tags=tags,
                    source=str(row["source"]),
                    created_at=str(row["created_at"]),
                    updated_at=str(row["updated_at"]),
                    score=round(float(score + lexical_bonus), 4),
                )
            )

        ranked.sort(key=lambda record: record.score or 0.0, reverse=True)
        return ranked[:limit]

    def find_matches(self, query_or_id: str, *, limit: int = 5) -> list[MemoryRecord]:
        if query_or_id.isdigit():
            record = self.get_by_id(int(query_or_id))
            return [record] if record is not None else []

        pattern = f"%{query_or_id.lower()}%"
        rows = self._conn.execute(
            """
            SELECT id, content, tags_json, source, created_at, updated_at, embedding_json
            FROM memories
            WHERE lower(content) LIKE ? OR lower(tags_json) LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        ).fetchall()
        if rows:
            return [self._row_to_record(row) for row in rows]
        return self.recall(query_or_id, limit=limit)

    def forget_by_ids(self, ids: Sequence[int]) -> int:
        if not self._persist:
            raise PermissionError("El modo incógnito no permite borrar memoria persistente.")
        if not ids:
            return 0
        placeholders = ", ".join("?" for _ in ids)
        cursor = self._conn.execute(
            f"DELETE FROM memories WHERE id IN ({placeholders})",
            tuple(ids),
        )
        self._conn.commit()
        deleted = int(cursor.rowcount or 0)
        if self._logger is not None and deleted:
            self._logger.log("memory_forgotten", memory_ids=list(ids), deleted=deleted)
        return deleted

    def get_by_id(self, memory_id: int) -> MemoryRecord | None:
        row = self._conn.execute(
            """
            SELECT id, content, tags_json, source, created_at, updated_at, embedding_json
            FROM memories
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS count FROM memories").fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def pending_notes(self, *, limit: int = 5) -> list[MemoryRecord]:
        queries = (
            "%todo%",
            "%pending%",
            "%pendiente%",
            "%note%",
            "%nota%",
        )
        rows = self._conn.execute(
            """
            SELECT id, content, tags_json, source, created_at, updated_at, embedding_json
            FROM memories
            WHERE lower(content) LIKE ?
               OR lower(content) LIKE ?
               OR lower(content) LIKE ?
               OR lower(tags_json) LIKE ?
               OR lower(tags_json) LIKE ?
               OR lower(tags_json) LIKE ?
               OR lower(tags_json) LIKE ?
               OR lower(tags_json) LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (
                queries[0],
                queries[1],
                queries[2],
                queries[0],
                queries[1],
                queries[2],
                queries[3],
                queries[4],
                limit,
            ),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        readonly = not self._persist and self._db_path.exists()
        if self._persist:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path)
        elif readonly:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        else:
            conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        if not readonly:
            self._ensure_schema(conn)
        return conn

    @staticmethod
    def _ensure_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                source TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_updated_at
            ON memories (updated_at DESC)
            """
        )
        conn.commit()

    def _encode_text(self, content: str, tags: Sequence[str]) -> np.ndarray:
        joined_tags = ", ".join(tags)
        text = content if not joined_tags else f"{content}\nTags: {joined_tags}"
        vector = self._encoder.encode_texts([text])[0]
        return _normalize_vector(np.asarray(vector, dtype=np.float32))

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=int(row["id"]),
            content=str(row["content"]),
            tags=json.loads(str(row["tags_json"])),
            source=str(row["source"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )


def _normalize_tags(tags: Sequence[str]) -> list[str]:
    normalized = {tag.strip() for tag in tags if tag.strip()}
    return sorted(normalized)


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm
