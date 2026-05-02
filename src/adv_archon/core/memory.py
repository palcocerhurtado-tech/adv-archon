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


MEMORY_CATEGORIES = {
    "general",
    "interests",
    "projects",
    "people",
    "preferences",
}
DEFAULT_MEMORY_CATEGORY = "general"
DEFAULT_MEMORY_IMPORTANCE = 3


@dataclass(slots=True)
class MemoryRecord:
    id: int
    content: str
    tags: list[str]
    source: str
    memory_type: str
    namespace: str
    category: str
    importance: int
    metadata: dict[str, Any]
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
        memory_type: str = "fact",
        namespace: str = "general",
        category: str | None = None,
        importance: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        if not self._persist:
            raise PermissionError("El modo incógnito no permite escribir memoria persistente.")

        clean_content = content.strip()
        if not clean_content:
            raise ValueError("No se puede recordar un texto vacío.")
        clean_tags = _normalize_tags(tags or [])
        clean_memory_type = memory_type.strip() or "fact"
        clean_namespace = namespace.strip() or "general"
        clean_metadata = metadata or {}
        clean_category = _normalize_category(
            category
            or clean_metadata.get("category")
            or _infer_category(
                memory_type=clean_memory_type,
                namespace=clean_namespace,
            )
        )
        clean_importance = _normalize_importance(
            importance if importance is not None else clean_metadata.get("importance")
        )
        vector = self._encode_text(
            clean_content,
            clean_tags,
            memory_type=clean_memory_type,
            namespace=clean_namespace,
            category=clean_category,
        )
        timestamp = datetime.now(UTC).isoformat()
        existing = self._conn.execute(
            """
            SELECT id, content, tags_json, source, memory_type, namespace, category,
                   importance, metadata_json, created_at, updated_at, embedding_json
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
                    memory_type,
                    namespace,
                    category,
                    importance,
                    metadata_json,
                    embedding_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_content,
                    json.dumps(clean_tags, ensure_ascii=False),
                    source,
                    clean_memory_type,
                    clean_namespace,
                    clean_category,
                    clean_importance,
                    json.dumps(clean_metadata, ensure_ascii=False),
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
            merged_metadata = {
                **json.loads(str(existing["metadata_json"])),
                **clean_metadata,
            }
            memory_id = int(existing["id"])
            self._conn.execute(
                """
                UPDATE memories
                SET tags_json = ?, source = ?, memory_type = ?, namespace = ?,
                    category = ?, importance = ?, metadata_json = ?,
                    embedding_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(merged_tags, ensure_ascii=False),
                    source,
                    clean_memory_type,
                    clean_namespace,
                    clean_category,
                    clean_importance,
                    json.dumps(merged_metadata, ensure_ascii=False),
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

    def recall(
        self,
        query: str,
        *,
        limit: int = 5,
        memory_type: str | None = None,
        namespace: str | None = None,
        category: str | None = None,
        min_importance: int | None = None,
    ) -> list[MemoryRecord]:
        rows = self._conn.execute(
            """
            SELECT id, content, tags_json, source, memory_type, namespace, category,
                   importance, metadata_json, created_at, updated_at, embedding_json
            FROM memories
            WHERE (? IS NULL OR memory_type = ?)
              AND (? IS NULL OR namespace = ?)
              AND (? IS NULL OR category = ?)
              AND (? IS NULL OR importance >= ?)
            ORDER BY updated_at DESC
            """
            ,
            (
                memory_type,
                memory_type,
                namespace,
                namespace,
                _normalize_category(category) if category is not None else None,
                _normalize_category(category) if category is not None else None,
                min_importance,
                min_importance,
            ),
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
            importance_bonus = _importance_bonus(int(row["importance"]))
            ranked.append(
                MemoryRecord(
                    id=int(row["id"]),
                    content=content,
                    tags=tags,
                    source=str(row["source"]),
                    memory_type=str(row["memory_type"]),
                    namespace=str(row["namespace"]),
                    category=str(row["category"]),
                    importance=int(row["importance"]),
                    metadata=json.loads(str(row["metadata_json"])),
                    created_at=str(row["created_at"]),
                    updated_at=str(row["updated_at"]),
                    score=round(float(score + lexical_bonus + importance_bonus), 4),
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
            SELECT id, content, tags_json, source, memory_type, namespace, category,
                   importance, metadata_json, created_at, updated_at, embedding_json
            FROM memories
            WHERE lower(content) LIKE ? OR lower(tags_json) LIKE ? OR lower(category) LIKE ?
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        ).fetchall()
        if rows:
            return [self._row_to_record(row) for row in rows]
        return self.recall(query_or_id, limit=limit)

    def list_memories(
        self,
        *,
        limit: int = 20,
        query: str | None = None,
        memory_type: str | None = None,
        namespace: str | None = None,
        category: str | None = None,
        min_importance: int | None = None,
    ) -> list[MemoryRecord]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if memory_type is not None:
            clauses.append("memory_type = ?")
            params.append(memory_type)
        if namespace is not None:
            clauses.append("namespace = ?")
            params.append(namespace)
        if category is not None:
            clauses.append("category = ?")
            params.append(_normalize_category(category))
        if min_importance is not None:
            clauses.append("importance >= ?")
            params.append(_normalize_importance(min_importance))
        if query:
            pattern = f"%{query.lower()}%"
            clauses.append(
                "(lower(content) LIKE ? OR lower(tags_json) LIKE ? OR lower(category) LIKE ?)"
            )
            params.extend([pattern, pattern, pattern])
        params.append(limit)
        rows = self._conn.execute(
            f"""
            SELECT id, content, tags_json, source, memory_type, namespace, category,
                   importance, metadata_json, created_at, updated_at, embedding_json
            FROM memories
            WHERE {" AND ".join(clauses)}
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def update_memory(
        self,
        memory_id: int,
        *,
        content: str | None = None,
        tags: Sequence[str] | None = None,
        source: str | None = None,
        memory_type: str | None = None,
        namespace: str | None = None,
        category: str | None = None,
        importance: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        if not self._persist:
            raise PermissionError("El modo incógnito no permite editar memoria persistente.")
        existing = self.get_by_id(memory_id)
        if existing is None:
            raise LookupError(f"No existe ninguna memoria con id {memory_id}.")

        next_content = content.strip() if content is not None else existing.content
        if not next_content:
            raise ValueError("No se puede guardar una memoria vacía.")
        next_tags = _normalize_tags(tags) if tags is not None else existing.tags
        next_memory_type = (memory_type or existing.memory_type).strip() or "fact"
        next_namespace = (namespace or existing.namespace).strip() or "general"
        next_category = _normalize_category(category or existing.category)
        next_importance = _normalize_importance(
            importance if importance is not None else existing.importance
        )
        next_metadata = dict(existing.metadata)
        if metadata is not None:
            next_metadata.update(metadata)

        vector = self._encode_text(
            next_content,
            next_tags,
            memory_type=next_memory_type,
            namespace=next_namespace,
            category=next_category,
        )
        updated_at = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            UPDATE memories
            SET content = ?, tags_json = ?, source = ?, memory_type = ?, namespace = ?,
                category = ?, importance = ?, metadata_json = ?, embedding_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_content,
                json.dumps(next_tags, ensure_ascii=False),
                source or existing.source,
                next_memory_type,
                next_namespace,
                next_category,
                next_importance,
                json.dumps(next_metadata, ensure_ascii=False),
                json.dumps(vector.tolist()),
                updated_at,
                memory_id,
            ),
        )
        self._conn.commit()
        record = self.get_by_id(memory_id)
        if record is None:
            raise RuntimeError("No se pudo recuperar la memoria actualizada.")
        if self._logger is not None:
            self._logger.log(
                "memory_updated",
                memory_id=record.id,
                category=record.category,
                importance=record.importance,
            )
        return record

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
            SELECT id, content, tags_json, source, memory_type, namespace, category,
                   importance, metadata_json, created_at, updated_at, embedding_json
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
            SELECT id, content, tags_json, source, memory_type, namespace, category,
                   importance, metadata_json, created_at, updated_at, embedding_json
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

    def context_matches(self, query: str, *, limit: int = 8) -> list[MemoryRecord]:
        return self.recall(query, limit=limit)

    def _connect(self) -> sqlite3.Connection:
        readonly = not self._persist and self._db_path.exists()
        if self._persist:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
        elif readonly:
            conn = sqlite3.connect(
                f"file:{self._db_path}?mode=ro",
                uri=True,
                check_same_thread=False,
            )
        else:
            conn = sqlite3.connect(":memory:", check_same_thread=False)
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
                memory_type TEXT NOT NULL DEFAULT 'fact',
                namespace TEXT NOT NULL DEFAULT 'general',
                category TEXT NOT NULL DEFAULT 'general',
                importance INTEGER NOT NULL DEFAULT 3,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(conn, "memories", "memory_type", "TEXT NOT NULL DEFAULT 'fact'")
        _ensure_column(conn, "memories", "namespace", "TEXT NOT NULL DEFAULT 'general'")
        _ensure_column(conn, "memories", "category", "TEXT NOT NULL DEFAULT 'general'")
        _ensure_column(conn, "memories", "importance", "INTEGER NOT NULL DEFAULT 3")
        _ensure_column(conn, "memories", "metadata_json", "TEXT NOT NULL DEFAULT '{}'")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_updated_at
            ON memories (updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_category_importance
            ON memories (category, importance DESC, updated_at DESC)
            """
        )
        conn.commit()

    def _encode_text(
        self,
        content: str,
        tags: Sequence[str],
        *,
        memory_type: str = "fact",
        namespace: str = "general",
        category: str = DEFAULT_MEMORY_CATEGORY,
    ) -> np.ndarray:
        joined_tags = ", ".join(tags)
        fragments = [
            content,
            f"Type: {memory_type}",
            f"Namespace: {namespace}",
            f"Category: {category}",
        ]
        if joined_tags:
            fragments.append(f"Tags: {joined_tags}")
        text = "\n".join(fragments)
        vector = self._encoder.encode_texts([text])[0]
        return _normalize_vector(np.asarray(vector, dtype=np.float32))

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=int(row["id"]),
            content=str(row["content"]),
            tags=json.loads(str(row["tags_json"])),
            source=str(row["source"]),
            memory_type=str(row["memory_type"]),
            namespace=str(row["namespace"]),
            category=str(row["category"]),
            importance=int(row["importance"]),
            metadata=json.loads(str(row["metadata_json"])),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )


def _normalize_tags(tags: Sequence[str]) -> list[str]:
    normalized = {tag.strip() for tag in tags if tag.strip()}
    return sorted(normalized)


def _normalize_category(category: str) -> str:
    normalized = category.strip().lower()
    if not normalized:
        return DEFAULT_MEMORY_CATEGORY
    if normalized not in MEMORY_CATEGORIES:
        return DEFAULT_MEMORY_CATEGORY
    return normalized


def _normalize_importance(importance: Any) -> int:
    if importance is None:
        return DEFAULT_MEMORY_IMPORTANCE
    try:
        numeric = int(importance)
    except (TypeError, ValueError):
        return DEFAULT_MEMORY_IMPORTANCE
    return max(1, min(5, numeric))


def _infer_category(*, memory_type: str, namespace: str) -> str:
    normalized_namespace = namespace.strip().lower()
    if normalized_namespace in MEMORY_CATEGORIES:
        return normalized_namespace
    if memory_type.strip().lower() == "preference":
        return "preferences"
    return DEFAULT_MEMORY_CATEGORY


def _importance_bonus(importance: int) -> float:
    return (importance - DEFAULT_MEMORY_IMPORTANCE) * 0.04


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {str(row[1]) for row in rows}
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
