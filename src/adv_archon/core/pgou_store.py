from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from adv_archon.core.memory import EmbeddingEncoder

_CHUNK_SIZE = 1200
_CHUNK_OVERLAP = 200


@dataclass(slots=True)
class PGOUChunk:
    id: int
    municipality: str
    article_ref: str
    title: str
    text: str
    chunk_index: int
    source: str
    score: float | None = None


@dataclass(slots=True)
class PGOUMunicipality:
    id: int
    name: str
    canonical: str
    source: str
    chunk_count: int
    indexed_at: str


@dataclass(slots=True)
class PGOUSearchResult:
    municipality: str
    chunks: list[PGOUChunk]
    total_chunks_searched: int


class PGOUStore:
    def __init__(
        self,
        db_path: Path,
        *,
        encoder: EmbeddingEncoder | None = None,
    ) -> None:
        self._db_path = db_path
        self._encoder = encoder
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
            CREATE TABLE IF NOT EXISTS pgou_municipalities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                canonical   TEXT NOT NULL UNIQUE,
                source      TEXT NOT NULL DEFAULT '',
                chunk_count INTEGER NOT NULL DEFAULT 0,
                indexed_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pgou_chunks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                municipality_id INTEGER NOT NULL
                    REFERENCES pgou_municipalities(id) ON DELETE CASCADE,
                municipality    TEXT NOT NULL,
                article_ref     TEXT NOT NULL DEFAULT '',
                title           TEXT NOT NULL DEFAULT '',
                text            TEXT NOT NULL,
                chunk_index     INTEGER NOT NULL DEFAULT 0,
                source          TEXT NOT NULL DEFAULT '',
                embedding_json  TEXT NOT NULL DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_pgou_chunks_municipality
                ON pgou_chunks(municipality);
        """)
        conn.commit()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def list_municipalities(self) -> list[PGOUMunicipality]:
        rows = self._conn.execute(
            "SELECT * FROM pgou_municipalities ORDER BY name"
        ).fetchall()
        return [self._row_to_municipality(r) for r in rows]

    def get_municipality(self, name: str) -> PGOUMunicipality | None:
        canonical = _canonicalize(name)
        row = self._conn.execute(
            "SELECT * FROM pgou_municipalities WHERE canonical = ?", (canonical,)
        ).fetchone()
        return self._row_to_municipality(row) if row else None

    def index_text(
        self,
        text: str,
        *,
        municipality: str,
        source: str = "",
    ) -> int:
        canonical = _canonicalize(municipality)
        now = datetime.now(UTC).isoformat()

        existing = self._conn.execute(
            "SELECT id FROM pgou_municipalities WHERE canonical = ?", (canonical,)
        ).fetchone()

        if existing:
            muni_id = existing["id"]
            self._conn.execute(
                "DELETE FROM pgou_chunks WHERE municipality_id = ?", (muni_id,)
            )
        else:
            cur = self._conn.execute(
                "INSERT INTO pgou_municipalities "
                "(name, canonical, source, chunk_count, indexed_at) "
                "VALUES (?, ?, ?, 0, ?)",
                (municipality.strip().title(), canonical, source, now),
            )
            muni_id = cur.lastrowid

        chunks = _split_chunks(text)
        for idx, (article_ref, title, chunk_text) in enumerate(chunks):
            embedding: list[float] = []
            if self._encoder is not None:
                payload = f"{municipality} {title} {article_ref}\n{chunk_text[:800]}"
                encoded = self._encoder.encode_texts([payload])
                if encoded.size > 0:
                    vec = encoded[0]
                    norm = float(np.linalg.norm(vec))
                    if norm > 0:
                        vec = vec / norm
                    embedding = vec.tolist()

            self._conn.execute(
                "INSERT INTO pgou_chunks "
                "(municipality_id, municipality, article_ref, title, text, "
                "chunk_index, source, embedding_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    muni_id,
                    canonical,
                    article_ref,
                    title,
                    chunk_text,
                    idx,
                    source,
                    json.dumps(embedding),
                ),
            )

        self._conn.execute(
            "UPDATE pgou_municipalities "
            "SET chunk_count = ?, source = ?, indexed_at = ? WHERE id = ?",
            (len(chunks), source, now, muni_id),
        )
        self._conn.commit()
        return len(chunks)

    def search(
        self,
        query: str,
        *,
        municipality: str,
        limit: int = 8,
    ) -> PGOUSearchResult:
        canonical = _canonicalize(municipality)
        total = self._conn.execute(
            "SELECT COUNT(*) FROM pgou_chunks WHERE municipality = ?", (canonical,)
        ).fetchone()[0]

        rows = self._conn.execute(
            "SELECT * FROM pgou_chunks WHERE municipality = ?", (canonical,)
        ).fetchall()

        query_vec: np.ndarray | None = None
        if self._encoder is not None and query.strip():
            encoded = self._encoder.encode_texts([query])
            if encoded.size > 0:
                v = encoded[0]
                norm = float(np.linalg.norm(v))
                if norm > 0:
                    query_vec = v / norm

        scored: list[tuple[float, PGOUChunk]] = []
        query_terms = set(query.lower().split())

        for row in rows:
            chunk = self._row_to_chunk(row)
            score = _lexical_score(chunk, query_terms)
            if query_vec is not None:
                emb_data = json.loads(row["embedding_json"])
                if emb_data:
                    emb = np.array(emb_data, dtype=np.float32)
                    cosine = float(np.dot(query_vec, emb))
                    score = 0.4 * score + 0.6 * cosine
            chunk.score = score
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [c for _, c in scored[:limit]]

        return PGOUSearchResult(
            municipality=municipality,
            chunks=top,
            total_chunks_searched=total,
        )

    def delete_municipality(self, name: str) -> bool:
        canonical = _canonicalize(name)
        cur = self._conn.execute(
            "DELETE FROM pgou_municipalities WHERE canonical = ?", (canonical,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _row_to_municipality(row: sqlite3.Row) -> PGOUMunicipality:
        return PGOUMunicipality(
            id=row["id"],
            name=row["name"],
            canonical=row["canonical"],
            source=row["source"],
            chunk_count=row["chunk_count"],
            indexed_at=row["indexed_at"],
        )

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> PGOUChunk:
        return PGOUChunk(
            id=row["id"],
            municipality=row["municipality"],
            article_ref=row["article_ref"],
            title=row["title"],
            text=row["text"],
            chunk_index=row["chunk_index"],
            source=row["source"],
        )


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

_ARTICLE_RE = re.compile(
    r"(?i)(art[íi]culo|art\.|cap[íi]tulo|secci[oó]n|norma|disposici[oó]n|anexo)"
    r"\s*[\d\.]+[^\n]{0,80}",
    re.IGNORECASE,
)


def _canonicalize(name: str) -> str:
    import unicodedata
    nfd = unicodedata.normalize("NFD", name.lower().strip())
    ascii_name = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")


def _split_chunks(text: str) -> list[tuple[str, str, str]]:
    """Split text into (article_ref, title, chunk_text) tuples."""
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[tuple[str, str, str]] = []
    current: list[str] = []
    current_len = 0
    current_ref = ""
    current_title = ""

    def flush() -> None:
        if current:
            chunks.append((current_ref, current_title, "\n\n".join(current)))
            current.clear()

    for para in paragraphs:
        m = _ARTICLE_RE.match(para)
        if m:
            flush()
            current_ref = m.group(0)[:60].strip()
            current_title = para[:120].strip()
            current_len = 0

        if current_len + len(para) > _CHUNK_SIZE and current:
            flush()
            current_len = 0

        current.append(para)
        current_len += len(para)

    flush()

    if not chunks:
        words = text.split()
        step = _CHUNK_SIZE
        for i in range(0, len(words), step - _CHUNK_OVERLAP):
            snippet = " ".join(words[i : i + step])
            chunks.append(("", "", snippet))

    return chunks


def _lexical_score(chunk: PGOUChunk, terms: set[str]) -> float:
    haystack = f"{chunk.article_ref} {chunk.title} {chunk.text}".lower()
    hits = sum(1 for t in terms if t in haystack)
    return hits / max(len(terms), 1)
