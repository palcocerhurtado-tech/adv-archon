"""
Episodic memory for expediente analysis history.
Each episode captures a (municipality, case_type, params, verdict) tuple
with a text embedding for semantic similarity search.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS episodes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    municipality TEXT NOT NULL DEFAULT '',
    case_type    TEXT NOT NULL DEFAULT '',
    verdict      TEXT NOT NULL DEFAULT '',
    params_json  TEXT NOT NULL DEFAULT '{}',
    summary      TEXT NOT NULL DEFAULT '',
    embedding    BLOB,
    created_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodes_municipality ON episodes (municipality);
CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes (created_at);
"""


@dataclass(slots=True)
class Episode:
    id: int
    municipality: str
    case_type: str
    verdict: str
    params: dict[str, Any]
    summary: str
    created_at: float


class EpisodicMemory:
    """Persist analysis episodes; retrieve similar ones by embedding cosine similarity."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_DDL)
        self._conn.commit()

    def store(
        self,
        *,
        municipality: str,
        case_type: str,
        verdict: str,
        params: dict[str, Any],
        summary: str,
        embedding: list[float] | None = None,
    ) -> int:
        blob = _pack(embedding) if embedding else None
        cur = self._conn.execute(
            """INSERT INTO episodes
               (municipality, case_type, verdict, params_json, summary, embedding, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (municipality, case_type, verdict, json.dumps(params), summary, blob, time.time()),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def search_similar(
        self,
        query_embedding: list[float],
        *,
        municipality: str = "",
        limit: int = 5,
    ) -> list[Episode]:
        """Return top-k episodes ranked by cosine similarity."""
        sql = "SELECT * FROM episodes WHERE embedding IS NOT NULL"
        params: tuple[Any, ...] = ()
        if municipality:
            sql += " AND municipality = ?"
            params = (municipality,)
        sql += " ORDER BY created_at DESC LIMIT 200"
        rows = self._conn.execute(sql, params).fetchall()
        if not rows:
            return []
        q = np.array(query_embedding, dtype=np.float32)
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            vec = _unpack(row["embedding"])
            if vec is not None:
                norm = float(np.linalg.norm(q) * np.linalg.norm(vec))
                sim = float(np.dot(q, vec)) / (norm + 1e-9)
                scored.append((sim, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [_row_to_episode(r) for _, r in scored[:limit]]

    def list_recent(self, limit: int = 20) -> list[Episode]:
        rows = self._conn.execute(
            "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_episode(r) for r in rows]


def _pack(vec: list[float]) -> bytes:
    return np.array(vec, dtype=np.float32).tobytes()


def _unpack(blob: bytes) -> np.ndarray | None:
    try:
        return np.frombuffer(blob, dtype=np.float32)
    except Exception:
        return None


def _row_to_episode(row: sqlite3.Row) -> Episode:
    return Episode(
        id=row["id"],
        municipality=row["municipality"],
        case_type=row["case_type"],
        verdict=row["verdict"],
        params=json.loads(row["params_json"] or "{}"),
        summary=row["summary"],
        created_at=row["created_at"],
    )
