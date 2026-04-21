from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import EmbeddingEncoder
from adv_archon.tools.files import IGNORED_DIRS, IMAGE_EXTENSIONS, TEXT_EXTENSIONS, read_file

INDEXABLE_EXTENSIONS = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".html",
    ".htm",
}
IGNORED_PATH_FRAGMENTS = {
    "/.git/",
    "/node_modules/",
    "/.venv/",
    "/__pycache__/",
    "/Library/Caches/",
    "/Library/Logs/",
    "/.Trash/",
    "/.cache/",
    "/.local/share/uv/",
}


@dataclass(slots=True)
class KnowledgeRecord:
    path: str
    title: str
    excerpt: str
    root: str
    content_type: str
    updated_at: str
    score: float | None = None


@dataclass(slots=True)
class KnowledgeIndexResult:
    scanned_files: int
    indexed_files: int
    skipped_files: int
    roots: list[str]


class KnowledgeStore:
    def __init__(
        self,
        db_path: Path,
        *,
        encoder: EmbeddingEncoder,
        default_roots: Sequence[str] = (),
        vault_roots: Sequence[str] = (),
        auto_index_on_search: bool = True,
        max_files_per_root: int = 200,
        max_file_bytes: int = 2_000_000,
        logger: AppLogger | None = None,
    ) -> None:
        self._db_path = db_path
        self._encoder = encoder
        self._default_roots = tuple(default_roots)
        self._vault_roots = tuple(vault_roots)
        self._auto_index_on_search = auto_index_on_search
        self._max_files_per_root = max_files_per_root
        self._max_file_bytes = max_file_bytes
        self._logger = logger
        self._conn = self._connect()

    def set_default_roots(self, roots: Sequence[str]) -> None:
        self._default_roots = tuple(roots)

    def set_vault_roots(self, roots: Sequence[str]) -> None:
        self._vault_roots = tuple(roots)

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS count FROM knowledge_entries").fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def index_default_roots(self) -> KnowledgeIndexResult:
        resolved = [Path(root).expanduser() for root in self._default_roots]
        return self.index_paths(resolved)

    def index_vault_roots(self) -> KnowledgeIndexResult:
        resolved = [Path(root).expanduser() for root in self._vault_roots]
        return self.index_paths(resolved)

    def index_paths(self, paths: Sequence[Path | str]) -> KnowledgeIndexResult:
        scanned_files = 0
        indexed_files = 0
        skipped_files = 0
        roots: list[str] = []
        pending: list[tuple[Path, str, str, str, float, int]] = []

        for raw_path in paths:
            root = Path(raw_path).expanduser().resolve()
            roots.append(str(root))
            if not root.exists():
                continue
            candidates = self._collect_candidates(root)
            for path in candidates:
                scanned_files += 1
                try:
                    stat_result = path.stat()
                except OSError:
                    skipped_files += 1
                    continue
                if stat_result.st_size > self._max_file_bytes:
                    skipped_files += 1
                    continue
                if self._is_fresh(path, stat_result.st_mtime):
                    continue
                excerpt = self._extract_excerpt(path)
                if not excerpt:
                    skipped_files += 1
                    continue
                pending.append(
                    (
                        path,
                        path.name,
                        excerpt,
                        str(root),
                        stat_result.st_mtime,
                        stat_result.st_size,
                    )
                )

        if pending:
            embeddings = self._encoder.encode_texts(
                [f"{title}\n\n{excerpt}" for _path, title, excerpt, _root, _mtime, _size in pending]
            )
            for (path, title, excerpt, indexed_root, mtime, size), embedding in zip(
                pending, embeddings, strict=True
            ):
                self._upsert(
                    path=path,
                    title=title,
                    excerpt=excerpt,
                    root=indexed_root,
                    mtime=mtime,
                    size=size,
                    embedding=embedding,
                )
                indexed_files += 1
            self._conn.commit()

        result = KnowledgeIndexResult(
            scanned_files=scanned_files,
            indexed_files=indexed_files,
            skipped_files=skipped_files,
            roots=roots,
        )
        if self._logger is not None:
            self._logger.log(
                "knowledge_indexed",
                scanned_files=result.scanned_files,
                indexed_files=result.indexed_files,
                skipped_files=result.skipped_files,
                roots=result.roots,
            )
        return result

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        roots: Sequence[str] | None = None,
        suffixes: Sequence[str] | None = None,
    ) -> list[KnowledgeRecord]:
        if roots and self._auto_index_on_search:
            self.index_paths(roots)
        if self.count() == 0 and self._auto_index_on_search and self._default_roots:
            self.index_default_roots()

        rows = self._conn.execute(
            """
            SELECT path, title, excerpt, root, content_type, updated_at, embedding_json
            FROM knowledge_entries
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
        lowered_query = query.lower()
        records: list[KnowledgeRecord] = []
        resolved_roots = {str(Path(root).expanduser().resolve()) for root in (roots or ())}
        suffix_filter = {suffix.lower() for suffix in suffixes or ()}
        for row, score in zip(rows, scores.tolist(), strict=True):
            title = str(row["title"])
            excerpt = str(row["excerpt"])
            path = str(row["path"])
            root = str(row["root"])
            if resolved_roots and root not in resolved_roots:
                continue
            if suffix_filter and Path(path).suffix.lower() not in suffix_filter:
                continue
            lexical_bonus = 0.0
            if lowered_query and lowered_query in title.lower():
                lexical_bonus += 0.12
            if lowered_query and lowered_query in excerpt.lower():
                lexical_bonus += 0.08
            if lowered_query and lowered_query in path.lower():
                lexical_bonus += 0.05
            records.append(
                KnowledgeRecord(
                    path=path,
                    title=title,
                    excerpt=excerpt,
                    root=root,
                    content_type=str(row["content_type"]),
                    updated_at=str(row["updated_at"]),
                    score=round(float(score + lexical_bonus), 4),
                )
            )
        records.sort(key=lambda record: record.score or 0.0, reverse=True)
        if self._logger is not None:
            self._logger.log("knowledge_searched", query=query, results=min(limit, len(records)))
        return records[:limit]

    def search_vault(
        self,
        query: str,
        *,
        limit: int = 5,
        roots: Sequence[str] | None = None,
    ) -> list[KnowledgeRecord]:
        selected_roots = tuple(roots or self._vault_roots)
        return self.search(
            query,
            limit=limit,
            roots=selected_roots,
            suffixes=(".md", ".markdown"),
        )

    def _collect_candidates(self, root: Path) -> list[Path]:
        if root.is_file():
            return [root] if root.suffix.lower() in INDEXABLE_EXTENSIONS else []

        collected: list[Path] = []
        for path in root.rglob("*"):
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            path_text = f"/{path.as_posix().lstrip('/')}/"
            if any(fragment in path_text for fragment in IGNORED_PATH_FRAGMENTS):
                continue
            if not path.is_file():
                continue
            if path.suffix.lower() not in INDEXABLE_EXTENSIONS:
                continue
            collected.append(path)
            if len(collected) >= self._max_files_per_root:
                break
        return collected

    def _extract_excerpt(self, path: Path) -> str:
        try:
            result = read_file(str(path))
        except Exception:
            return ""
        content = str(result.payload.get("content", "")).strip()
        if not content:
            return ""
        compact = " ".join(content.split())
        return compact[:1800]

    def _is_fresh(self, path: Path, mtime: float) -> bool:
        row = self._conn.execute(
            "SELECT mtime FROM knowledge_entries WHERE path = ?",
            (str(path),),
        ).fetchone()
        if row is None:
            return False
        stored = float(row["mtime"])
        return abs(stored - mtime) < 0.0001

    def _upsert(
        self,
        *,
        path: Path,
        title: str,
        excerpt: str,
        root: str,
        mtime: float,
        size: int,
        embedding: np.ndarray,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO knowledge_entries (
                path,
                title,
                excerpt,
                root,
                content_type,
                mtime,
                file_size,
                embedding_json,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(path) DO UPDATE SET
                title = excluded.title,
                excerpt = excluded.excerpt,
                root = excluded.root,
                content_type = excluded.content_type,
                mtime = excluded.mtime,
                file_size = excluded.file_size,
                embedding_json = excluded.embedding_json,
                updated_at = datetime('now')
            """,
            (
                str(path),
                title,
                excerpt,
                root,
                path.suffix.lower().lstrip(".") or "text",
                mtime,
                size,
                json.dumps(embedding.tolist()),
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                path TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                root TEXT NOT NULL,
                content_type TEXT NOT NULL,
                mtime REAL NOT NULL,
                file_size INTEGER NOT NULL,
                embedding_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_updated_at
            ON knowledge_entries (updated_at DESC)
            """
        )
        return conn


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return np.asarray(vector / norm, dtype=np.float32)
