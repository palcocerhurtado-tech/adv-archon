"""Personal Knowledge Base — local vector store for self-RAG.

Stores arbitrary documents (notes, files, web pages) as sentence-transformer
embeddings in SQLite. Used by send_prompt() to inject relevant context before
the LLM sees the user's query.

CLI surface (via ui/commands.py):
    /kb index <path|url|text>
    /kb ask <query>
    /kb list [n]
    /kb clear
"""

from __future__ import annotations

import json
import sqlite3
import textwrap
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from adv_archon.core.memory import SentenceTransformerEncoder

_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_SIMILARITY_THRESHOLD = 0.35   # minimum cosine similarity to include in context
_MAX_CONTEXT_CHUNKS = 4        # max KB hits injected into each prompt


@dataclass(slots=True)
class KBRecord:
    id: str
    source: str
    text: str
    tags: list[str]
    created_at: str
    score: float = 0.0

    def preview(self, max_chars: int = 120) -> str:
        return textwrap.shorten(self.text, width=max_chars, placeholder="…")


class PersonalKB:
    def __init__(
        self,
        db_path: Path,
        *,
        model_name: str = _DEFAULT_MODEL,
    ) -> None:
        self._db_path = db_path
        self._encoder = SentenceTransformerEncoder(model_name)
        self._conn = self._connect()

    # ── Setup ────────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kb_docs (
                id          TEXT PRIMARY KEY,
                source      TEXT NOT NULL,
                text        TEXT NOT NULL,
                tags_json   TEXT NOT NULL DEFAULT '[]',
                embedding   TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
            """
        )
        conn.commit()
        return conn

    # ── Write ─────────────────────────────────────────────────────────────────

    def add(
        self,
        text: str,
        *,
        source: str = "manual",
        tags: Sequence[str] | None = None,
    ) -> KBRecord:
        """Embed and store a text chunk. Returns the stored record."""
        text = text.strip()
        if not text:
            raise ValueError("No se puede indexar texto vacío.")

        embedding = self._encoder.encode_texts([text])[0]
        doc_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        tag_list = list(tags or [])

        self._conn.execute(
            """
            INSERT INTO kb_docs (id, source, text, tags_json, embedding, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                source,
                text,
                json.dumps(tag_list, ensure_ascii=False),
                json.dumps(embedding.tolist()),
                now,
            ),
        )
        self._conn.commit()
        return KBRecord(id=doc_id, source=source, text=text, tags=tag_list, created_at=now)

    def add_file(self, path: Path, *, chunk_size: int = 500, overlap: int = 50) -> int:
        """Index a text file in sliding-window chunks. Returns number of chunks added."""
        if not path.is_file():
            raise FileNotFoundError(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        return self._add_text_chunks(text, source=str(path), chunk_size=chunk_size, overlap=overlap)

    def add_url(self, url: str, *, chunk_size: int = 500, overlap: int = 50) -> int:
        """Download a URL, extract text, and index in chunks. Returns number of chunks."""
        from adv_archon.core._kb_fetch import fetch_url_text
        text = fetch_url_text(url)
        if not text:
            return 0
        return self._add_text_chunks(text, source=url, chunk_size=chunk_size, overlap=overlap)

    def _add_text_chunks(
        self,
        text: str,
        *,
        source: str,
        chunk_size: int,
        overlap: int,
    ) -> int:
        words = text.split()
        if not words:
            return 0
        count = 0
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + chunk_size])
            self.add(chunk, source=source)
            count += 1
            i += chunk_size - overlap
        return count

    def delete(self, doc_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM kb_docs WHERE id = ?", (doc_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def clear(self) -> int:
        cursor = self._conn.execute("DELETE FROM kb_docs")
        self._conn.commit()
        return cursor.rowcount

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(self, query: str, *, limit: int = 8) -> list[KBRecord]:
        """Return top-k records by cosine similarity."""
        rows = self._conn.execute(
            "SELECT id, source, text, tags_json, embedding, created_at FROM kb_docs"
        ).fetchall()
        if not rows:
            return []

        q_vec = self._encoder.encode_texts([query])[0]
        scored: list[tuple[float, sqlite3.Row]] = []

        for row in rows:
            try:
                emb = np.array(json.loads(row["embedding"]), dtype=np.float32)
                score = float(np.dot(q_vec, emb))
            except Exception:
                score = 0.0
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, row in scored[:limit]:
            results.append(
                KBRecord(
                    id=row["id"],
                    source=row["source"],
                    text=row["text"],
                    tags=json.loads(row["tags_json"]),
                    created_at=row["created_at"],
                    score=score,
                )
            )
        return results

    def list_all(self, *, limit: int = 20) -> list[KBRecord]:
        rows = self._conn.execute(
            "SELECT id, source, text, tags_json, created_at FROM kb_docs "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            KBRecord(
                id=r["id"],
                source=r["source"],
                text=r["text"],
                tags=json.loads(r["tags_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM kb_docs").fetchone()[0])

    # ── Self-RAG ──────────────────────────────────────────────────────────────

    def build_context_injection(
        self,
        query: str,
        *,
        threshold: float = _SIMILARITY_THRESHOLD,
        max_chunks: int = _MAX_CONTEXT_CHUNKS,
    ) -> str | None:
        """Return a context string to prepend to the prompt, or None if nothing relevant."""
        hits = self.search(query, limit=max_chunks * 2)
        relevant = [h for h in hits if h.score >= threshold][:max_chunks]
        if not relevant:
            return None
        parts = ["[Conocimiento personal relevante encontrado en tu KB:]"]
        for i, rec in enumerate(relevant, 1):
            parts.append(
                f"\n[{i}] (fuente: {rec.source} | similitud: {rec.score:.2f})\n{rec.text[:600]}"
            )
        parts.append("\n[Fin de contexto KB — usa esta información si es útil para responder.]")
        return "\n".join(parts)

    def close(self) -> None:
        self._conn.close()
