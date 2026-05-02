from __future__ import annotations

import json
import os
import plistlib
import re
import sqlite3
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

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
INDEXED_STATUS = "indexed"
PENDING_STATUS = "pending"
SKIPPED_STATUS = "skipped"
ERROR_STATUS = "error"
DELETED_STATUS = "deleted"
DEFAULT_EMBEDDING_BATCH_SIZE = 64
DEFAULT_CANDIDATE_WINDOW = 250


@dataclass(slots=True)
class KnowledgeRecord:
    path: str
    title: str
    excerpt: str
    root: str
    content_type: str
    updated_at: str
    score: float | None = None
    relative_path: str = ""
    suffix: str = ""
    file_size: int = 0
    modified_at: str = ""
    indexed_at: str = ""
    status: str = INDEXED_STATUS
    matched_terms: tuple[str, ...] = ()
    term_coverage: float = 0.0


@dataclass(slots=True)
class KnowledgeDiscoveryResult:
    scanned_files: int
    unchanged_files: int
    pending_files: int
    skipped_files: int
    failed_files: int
    deleted_files: int
    roots: list[str]
    run_id: str | None = None
    status: str = "completed"

    @property
    def discovered_files(self) -> int:
        return self.scanned_files


@dataclass(slots=True)
class KnowledgeIndexResult:
    scanned_files: int
    indexed_files: int
    skipped_files: int
    roots: list[str]
    processed_files: int = 0
    unchanged_files: int = 0
    pending_files: int = 0
    failed_files: int = 0
    deleted_files: int = 0
    batch_size: int = 0
    run_id: str | None = None
    status: str = "completed"

    @property
    def discovered_files(self) -> int:
        return self.scanned_files


@dataclass(slots=True)
class KnowledgeIndexRun:
    run_id: str
    status: str
    roots: list[str]
    started_at: str
    finished_at: str | None
    batch_size: int
    refresh: bool
    scanned_files: int
    processed_files: int
    indexed_files: int
    unchanged_files: int
    skipped_files: int
    failed_files: int
    deleted_files: int
    pending_files: int
    message: str = ""


@dataclass(slots=True)
class KnowledgeStatus:
    roots: list[str]
    indexed_entries: int
    discovered_files: int
    indexed_files: int
    pending_files: int
    skipped_files: int
    error_files: int
    deleted_files: int
    last_run: KnowledgeIndexRun | None = None
    recent_runs: list[KnowledgeIndexRun] = field(default_factory=list)


@dataclass(slots=True)
class KnowledgeQueryPlan:
    original_query: str
    query_variants: tuple[str, ...]
    core_terms: tuple[str, ...]


@dataclass(slots=True)
class KnowledgeSearchResult:
    records: list[KnowledgeRecord]
    plan: KnowledgeQueryPlan
    candidate_count: int = 0


@dataclass(slots=True)
class _IndexCounters:
    scanned_files: int = 0
    processed_files: int = 0
    indexed_files: int = 0
    unchanged_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    deleted_files: int = 0
    pending_files: int = 0


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
        embedding_batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
        logger: AppLogger | None = None,
    ) -> None:
        self._db_path = db_path
        self._encoder = encoder
        self._default_roots = tuple(default_roots)
        self._vault_roots = tuple(vault_roots)
        self._auto_index_on_search = auto_index_on_search
        self._max_files_per_root = max_files_per_root
        self._max_file_bytes = max_file_bytes
        self._embedding_batch_size = max(1, embedding_batch_size)
        self._logger = logger
        self._fts_enabled = False
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

    def index_default_roots(
        self,
        *,
        batch_size: int | None = None,
        refresh: bool = True,
    ) -> KnowledgeIndexResult:
        return self.run_once(
            [Path(root).expanduser() for root in self._default_roots],
            batch_size=batch_size,
            refresh=refresh,
        )

    def index_vault_roots(
        self,
        *,
        batch_size: int | None = None,
        refresh: bool = True,
    ) -> KnowledgeIndexResult:
        return self.run_once(
            [Path(root).expanduser() for root in self._vault_roots],
            batch_size=batch_size,
            refresh=refresh,
        )

    def index_paths(
        self,
        paths: Sequence[Path | str],
        *,
        batch_size: int | None = None,
        refresh: bool = True,
    ) -> KnowledgeIndexResult:
        return self.run_once(paths, batch_size=batch_size, refresh=refresh)

    def run_once(
        self,
        paths: Sequence[Path | str] | None = None,
        *,
        batch_size: int | None = None,
        refresh: bool = True,
    ) -> KnowledgeIndexResult:
        resolved_paths = self._selected_paths(paths)
        roots = [str(root) for root in resolved_paths]
        effective_batch_size = self._resolve_batch_size(batch_size)
        run_id = self._start_run(roots, batch_size=effective_batch_size, refresh=refresh)

        counters = _IndexCounters()
        try:
            if refresh:
                discovery = self._discover_paths_internal(resolved_paths, run_id=run_id)
                counters.scanned_files += discovery.scanned_files
                counters.unchanged_files += discovery.unchanged_files
                counters.skipped_files += discovery.skipped_files
                counters.failed_files += discovery.failed_files
                counters.deleted_files += discovery.deleted_files
                counters.pending_files = discovery.pending_files
            ingest = self._ingest_pending_internal(
                resolved_paths,
                batch_size=effective_batch_size,
                run_id=run_id,
            )
            counters.processed_files += ingest.processed_files
            counters.indexed_files += ingest.indexed_files
            counters.skipped_files += ingest.skipped_files
            counters.failed_files += ingest.failed_files
            counters.deleted_files += ingest.deleted_files
            counters.pending_files = ingest.pending_files
            result = KnowledgeIndexResult(
                scanned_files=counters.scanned_files,
                indexed_files=counters.indexed_files,
                skipped_files=counters.skipped_files,
                roots=roots,
                processed_files=counters.processed_files,
                unchanged_files=counters.unchanged_files,
                pending_files=counters.pending_files,
                failed_files=counters.failed_files,
                deleted_files=counters.deleted_files,
                batch_size=effective_batch_size,
                run_id=run_id,
                status="completed",
            )
            self._finish_run(run_id, result)
        except Exception as exc:
            result = KnowledgeIndexResult(
                scanned_files=counters.scanned_files,
                indexed_files=counters.indexed_files,
                skipped_files=counters.skipped_files,
                roots=roots,
                processed_files=counters.processed_files,
                unchanged_files=counters.unchanged_files,
                pending_files=self._count_files_by_status(PENDING_STATUS, roots=roots),
                failed_files=counters.failed_files,
                deleted_files=counters.deleted_files,
                batch_size=effective_batch_size,
                run_id=run_id,
                status="failed",
            )
            self._finish_run(run_id, result, message=str(exc))
            raise

        if self._logger is not None:
            self._logger.log(
                "knowledge_indexed",
                run_id=result.run_id,
                scanned_files=result.scanned_files,
                processed_files=result.processed_files,
                indexed_files=result.indexed_files,
                unchanged_files=result.unchanged_files,
                skipped_files=result.skipped_files,
                failed_files=result.failed_files,
                deleted_files=result.deleted_files,
                pending_files=result.pending_files,
                batch_size=result.batch_size,
                roots=result.roots,
            )
        return result

    def discover_paths(
        self,
        paths: Sequence[Path | str] | None = None,
    ) -> KnowledgeDiscoveryResult:
        resolved_paths = self._selected_paths(paths)
        roots = [str(root) for root in resolved_paths]
        run_id = self._start_run(roots, batch_size=0, refresh=True)
        try:
            result = self._discover_paths_internal(resolved_paths, run_id=run_id)
            empty_result = KnowledgeIndexResult(
                scanned_files=result.scanned_files,
                indexed_files=0,
                skipped_files=result.skipped_files,
                roots=result.roots,
                processed_files=0,
                unchanged_files=result.unchanged_files,
                pending_files=result.pending_files,
                failed_files=result.failed_files,
                deleted_files=result.deleted_files,
                batch_size=0,
                run_id=run_id,
                status="completed",
            )
            self._finish_run(run_id, empty_result, message="discovery_only")
            return result
        except Exception as exc:
            empty_result = KnowledgeIndexResult(
                scanned_files=0,
                indexed_files=0,
                skipped_files=0,
                roots=roots,
                processed_files=0,
                unchanged_files=0,
                pending_files=self._count_files_by_status(PENDING_STATUS, roots=roots),
                failed_files=0,
                deleted_files=0,
                batch_size=0,
                run_id=run_id,
                status="failed",
            )
            self._finish_run(run_id, empty_result, message=str(exc))
            raise

    def ingest_pending_batch(
        self,
        paths: Sequence[Path | str] | None = None,
        *,
        batch_size: int | None = None,
    ) -> KnowledgeIndexResult:
        resolved_paths = self._selected_paths(paths)
        roots = [str(root) for root in resolved_paths]
        effective_batch_size = self._resolve_batch_size(batch_size)
        run_id = self._start_run(roots, batch_size=effective_batch_size, refresh=False)
        try:
            result = self._ingest_pending_internal(
                resolved_paths,
                batch_size=effective_batch_size,
                run_id=run_id,
            )
            final = KnowledgeIndexResult(
                scanned_files=0,
                indexed_files=result.indexed_files,
                skipped_files=result.skipped_files,
                roots=roots,
                processed_files=result.processed_files,
                unchanged_files=0,
                pending_files=result.pending_files,
                failed_files=result.failed_files,
                deleted_files=result.deleted_files,
                batch_size=effective_batch_size,
                run_id=run_id,
                status="completed",
            )
            self._finish_run(run_id, final)
            return final
        except Exception as exc:
            failed = KnowledgeIndexResult(
                scanned_files=0,
                indexed_files=0,
                skipped_files=0,
                roots=roots,
                processed_files=0,
                unchanged_files=0,
                pending_files=self._count_files_by_status(PENDING_STATUS, roots=roots),
                failed_files=0,
                deleted_files=0,
                batch_size=effective_batch_size,
                run_id=run_id,
                status="failed",
            )
            self._finish_run(run_id, failed, message=str(exc))
            raise

    def status(
        self,
        roots: Sequence[Path | str] | None = None,
        *,
        limit_runs: int = 5,
    ) -> KnowledgeStatus:
        resolved_roots = self._selected_paths(roots, prefer_all_when_empty=True)
        root_strings = [str(root) for root in resolved_roots]
        where_clause, params = self._root_filter_clause(root_strings, table_alias="knowledge_files")

        grouped = self._conn.execute(
            f"""
            SELECT last_index_status, COUNT(*) AS count
            FROM knowledge_files
            {where_clause}
            GROUP BY last_index_status
            """,
            params,
        ).fetchall()
        counts = {str(row["last_index_status"]): int(row["count"]) for row in grouped}

        indexed_entries_row = self._conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM knowledge_entries
            {where_clause.replace('knowledge_files', 'knowledge_entries')}
            """,
            params,
        ).fetchone()
        recent_runs = self._recent_runs(limit_runs)

        return KnowledgeStatus(
            roots=root_strings,
            indexed_entries=0 if indexed_entries_row is None else int(indexed_entries_row["count"]),
            discovered_files=sum(counts.values()),
            indexed_files=counts.get(INDEXED_STATUS, 0),
            pending_files=counts.get(PENDING_STATUS, 0),
            skipped_files=counts.get(SKIPPED_STATUS, 0),
            error_files=counts.get(ERROR_STATUS, 0),
            deleted_files=counts.get(DELETED_STATUS, 0),
            last_run=recent_runs[0] if recent_runs else None,
            recent_runs=recent_runs,
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        roots: Sequence[str] | None = None,
        suffixes: Sequence[str] | None = None,
    ) -> list[KnowledgeRecord]:
        return self.search_details(
            query,
            limit=limit,
            roots=roots,
            suffixes=suffixes,
        ).records

    def search_details(
        self,
        query: str,
        *,
        limit: int = 5,
        roots: Sequence[str] | None = None,
        suffixes: Sequence[str] | None = None,
    ) -> KnowledgeSearchResult:
        if roots and self._auto_index_on_search:
            self.ingest_pending_batch(roots)
        elif self.count() == 0 and self._auto_index_on_search and self._default_roots:
            self.run_once(self._default_roots)
        elif self._auto_index_on_search and self._has_pending(roots or self._default_roots):
            self.ingest_pending_batch(roots or self._default_roots)

        plan = _build_query_plan(query)
        candidate_rows = self._candidate_rows_for_plan(
            plan,
            roots=roots,
            suffixes=suffixes,
            candidate_limit=max(limit * 25, DEFAULT_CANDIDATE_WINDOW),
        )
        if not candidate_rows:
            return KnowledgeSearchResult(records=[], plan=plan, candidate_count=0)

        query_matrix = np.vstack(
            [
                _normalize_vector(vector)
                for vector in self._encoder.encode_texts(list(plan.query_variants))
            ]
        )
        matrix = np.vstack(
            [
                _normalize_vector(
                    np.asarray(json.loads(str(row["embedding_json"])), dtype=np.float32)
                )
                for row in candidate_rows
            ]
        )
        semantic_scores = matrix @ query_matrix.T

        results: list[KnowledgeRecord] = []
        for row, semantic_row in zip(candidate_rows, semantic_scores.tolist(), strict=True):
            semantic_score = max(semantic_row) if semantic_row else 0.0
            title = str(row["title"])
            excerpt = str(row["excerpt"])
            path = str(row["path"])
            relative_path = str(row["relative_path"])
            searchable = " ".join((title, excerpt, path, relative_path)).lower()
            matched_terms = tuple(term for term in plan.core_terms if term in searchable)
            term_coverage = (
                len(matched_terms) / len(plan.core_terms) if plan.core_terms else 0.0
            )
            lexical_bonus = max(
                (
                    self._lexical_bonus(
                        variant.lower(),
                        _tokenize_query(variant),
                        title=title,
                        excerpt=excerpt,
                        path=path,
                        relative_path=relative_path,
                        lexical_rank=_coerce_float(row["lexical_rank"]),
                    )
                    for variant in plan.query_variants
                ),
                default=0.0,
            )
            phrase_bonus = max(
                (
                    _exact_variant_bonus(
                        variant,
                        title=title,
                        excerpt=excerpt,
                        path=path,
                        relative_path=relative_path,
                    )
                    for variant in plan.query_variants
                ),
                default=0.0,
            )
            coverage_bonus = min(term_coverage, 1.0) * 0.18
            results.append(
                KnowledgeRecord(
                    path=path,
                    title=title,
                    excerpt=excerpt,
                    root=str(row["root"]),
                    content_type=str(row["content_type"]),
                    updated_at=str(row["updated_at"]),
                    score=round(
                        float(semantic_score + lexical_bonus + phrase_bonus + coverage_bonus),
                        4,
                    ),
                    relative_path=relative_path,
                    suffix=str(row["suffix"]),
                    file_size=int(row["file_size"]),
                    modified_at=str(row["modified_at"]),
                    indexed_at=str(row["indexed_at"]),
                    status=INDEXED_STATUS,
                    matched_terms=matched_terms,
                    term_coverage=round(term_coverage, 4),
                )
            )
        results.sort(key=lambda item: (item.score or 0.0, item.updated_at), reverse=True)
        if self._logger is not None:
            self._logger.log(
                "knowledge_searched",
                query=query,
                query_variants=list(plan.query_variants),
                results=min(limit, len(results)),
                indexed_entries=self.count(),
            )
        return KnowledgeSearchResult(
            records=results[:limit],
            plan=plan,
            candidate_count=len(candidate_rows),
        )

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

    def _discover_paths_internal(
        self,
        paths: Sequence[Path],
        *,
        run_id: str,
    ) -> KnowledgeDiscoveryResult:
        counters = _IndexCounters()
        roots = [str(path) for path in paths]
        seen_at = _utc_now()

        for root in paths:
            if root.exists():
                for path in self._iter_candidates(root):
                    counters.scanned_files += 1
                    try:
                        stat_result = path.stat()
                    except OSError as exc:
                        counters.failed_files += 1
                        self._mark_path_error(path, root=root, run_id=run_id, error=str(exc))
                        continue

                    outcome = self._record_discovery(
                        path=path,
                        root=root,
                        stat_result=stat_result,
                        run_id=run_id,
                        seen_at=seen_at,
                    )
                    if outcome == INDEXED_STATUS:
                        counters.unchanged_files += 1
                    elif outcome == PENDING_STATUS:
                        pass
                    elif outcome == SKIPPED_STATUS:
                        counters.skipped_files += 1
                    elif outcome == ERROR_STATUS:
                        counters.failed_files += 1
            counters.deleted_files += self._mark_missing_files(
                root=root,
                run_id=run_id,
                seen_at=seen_at,
            )
            counters.pending_files = self._count_files_by_status(PENDING_STATUS, roots=roots)
            self._update_run_counts(run_id, counters)

        result = KnowledgeDiscoveryResult(
            scanned_files=counters.scanned_files,
            unchanged_files=counters.unchanged_files,
            pending_files=self._count_files_by_status(PENDING_STATUS, roots=roots),
            skipped_files=counters.skipped_files,
            failed_files=counters.failed_files,
            deleted_files=counters.deleted_files,
            roots=roots,
            run_id=run_id,
            status="completed",
        )
        return result

    def _ingest_pending_internal(
        self,
        paths: Sequence[Path],
        *,
        batch_size: int,
        run_id: str,
    ) -> KnowledgeIndexResult:
        roots = [str(path) for path in paths]
        pending_rows = self._pending_rows(roots=roots, limit=batch_size)
        counters = _IndexCounters()

        for chunk in _chunked(pending_rows, size=self._embedding_batch_size):
            prepared: list[tuple[sqlite3.Row, str]] = []
            for row in chunk:
                path = Path(str(row["path"]))
                if not path.exists():
                    counters.deleted_files += 1
                    self._mark_deleted(path, seen_at=_utc_now())
                    continue
                try:
                    excerpt = self._extract_excerpt(path)
                except ValueError as exc:
                    counters.skipped_files += 1
                    self._mark_skipped(
                        path=path,
                        reason=str(exc),
                        updated_at=_utc_now(),
                    )
                    continue
                except Exception as exc:
                    counters.failed_files += 1
                    self._mark_error(
                        path=path,
                        error=str(exc),
                        updated_at=_utc_now(),
                    )
                    continue
                prepared.append((row, excerpt))

            if not prepared:
                counters.pending_files = self._count_files_by_status(PENDING_STATUS, roots=roots)
                self._update_run_counts(run_id, counters)
                self._conn.commit()
                continue

            embeddings = self._encoder.encode_texts(
                [
                    f"{str(row['title'])}\n\n{excerpt}"
                    for row, excerpt in prepared
                ]
            )
            indexed_at = _utc_now()
            for (row, excerpt), embedding in zip(prepared, embeddings, strict=True):
                path = Path(str(row["path"]))
                self._upsert_entry(
                    path=path,
                    root=str(row["root"]),
                    relative_path=str(row["relative_path"]),
                    title=str(row["title"]),
                    excerpt=excerpt,
                    suffix=str(row["suffix"]),
                    mtime=float(row["mtime"]),
                    file_size=int(row["file_size"]),
                    embedding=embedding,
                    indexed_at=indexed_at,
                )
                self._mark_indexed(path=path, indexed_at=indexed_at)
                counters.indexed_files += 1
                counters.processed_files += 1
            counters.pending_files = self._count_files_by_status(PENDING_STATUS, roots=roots)
            self._update_run_counts(run_id, counters)
            self._conn.commit()

        result = KnowledgeIndexResult(
            scanned_files=0,
            indexed_files=counters.indexed_files,
            skipped_files=counters.skipped_files,
            roots=roots,
            processed_files=counters.processed_files,
            unchanged_files=0,
            pending_files=self._count_files_by_status(PENDING_STATUS, roots=roots),
            failed_files=counters.failed_files,
            deleted_files=counters.deleted_files,
            batch_size=batch_size,
            run_id=run_id,
            status="completed",
        )
        return result

    def _candidate_rows_for_plan(
        self,
        plan: KnowledgeQueryPlan,
        *,
        roots: Sequence[str] | None,
        suffixes: Sequence[str] | None,
        candidate_limit: int,
    ) -> list[sqlite3.Row]:
        resolved_roots = [
            str(root)
            for root in self._selected_paths(roots, prefer_all_when_empty=True)
        ]
        normalized_suffixes = [suffix.lower() for suffix in suffixes or ()]
        by_path: dict[str, sqlite3.Row] = {}

        for variant in plan.query_variants:
            for row in self._lexical_candidate_rows(
                variant,
                roots=resolved_roots,
                suffixes=normalized_suffixes,
                limit=candidate_limit,
            ):
                by_path.setdefault(str(row["path"]), row)
                if len(by_path) >= candidate_limit:
                    break
            if len(by_path) >= candidate_limit:
                break
        if len(by_path) < candidate_limit:
            for row in self._recent_candidate_rows(
                roots=resolved_roots,
                suffixes=normalized_suffixes,
                limit=candidate_limit,
            ):
                by_path.setdefault(str(row["path"]), row)
                if len(by_path) >= candidate_limit:
                    break
        return list(by_path.values())

    def _lexical_candidate_rows(
        self,
        query: str,
        *,
        roots: Sequence[str],
        suffixes: Sequence[str],
        limit: int,
    ) -> list[sqlite3.Row]:
        terms = _tokenize_query(query)
        if not terms:
            return []

        filters, params = self._entry_filters(roots=roots, suffixes=suffixes)
        if self._fts_enabled:
            fts_query = " OR ".join(f"{term}*" for term in terms)
            rows = self._conn.execute(
                f"""
                SELECT
                    knowledge_entries.path,
                    knowledge_entries.title,
                    knowledge_entries.excerpt,
                    knowledge_entries.root,
                    knowledge_entries.content_type,
                    knowledge_entries.updated_at,
                    knowledge_entries.embedding_json,
                    knowledge_entries.relative_path,
                    knowledge_entries.suffix,
                    knowledge_entries.file_size,
                    knowledge_entries.modified_at,
                    knowledge_entries.indexed_at,
                    bm25(knowledge_fts, 3.0, 2.0, 1.0, 0.5, 0.2) AS lexical_rank
                FROM knowledge_fts
                JOIN knowledge_entries ON knowledge_entries.path = knowledge_fts.path
                WHERE knowledge_fts MATCH ? {filters}
                ORDER BY lexical_rank ASC, knowledge_entries.updated_at DESC
                LIMIT ?
                """,
                (fts_query, *params, limit),
            ).fetchall()
            if rows:
                return rows

        like_clauses: list[str] = []
        like_params: list[Any] = []
        for term in terms:
            pattern = f"%{term}%"
            like_clauses.append(
                "("
                "lower(knowledge_entries.title) LIKE ? OR "
                "lower(knowledge_entries.relative_path) LIKE ? OR "
                "lower(knowledge_entries.path) LIKE ? OR "
                "lower(knowledge_entries.excerpt) LIKE ?"
                ")"
            )
            like_params.extend((pattern, pattern, pattern, pattern))

        return self._conn.execute(
            f"""
            SELECT
                knowledge_entries.path,
                knowledge_entries.title,
                knowledge_entries.excerpt,
                knowledge_entries.root,
                knowledge_entries.content_type,
                knowledge_entries.updated_at,
                knowledge_entries.embedding_json,
                knowledge_entries.relative_path,
                knowledge_entries.suffix,
                knowledge_entries.file_size,
                knowledge_entries.modified_at,
                knowledge_entries.indexed_at,
                NULL AS lexical_rank
            FROM knowledge_entries
            WHERE ({' OR '.join(like_clauses)}) {filters}
            ORDER BY knowledge_entries.updated_at DESC
            LIMIT ?
            """,
            (*like_params, *params, limit),
        ).fetchall()

    def _recent_candidate_rows(
        self,
        *,
        roots: Sequence[str],
        suffixes: Sequence[str],
        limit: int,
    ) -> list[sqlite3.Row]:
        filters, params = self._entry_filters(roots=roots, suffixes=suffixes)
        return self._conn.execute(
            f"""
            SELECT
                path,
                title,
                excerpt,
                root,
                content_type,
                updated_at,
                embedding_json,
                relative_path,
                suffix,
                file_size,
                modified_at,
                indexed_at,
                NULL AS lexical_rank
            FROM knowledge_entries
            WHERE 1 = 1 {filters}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()

    def _lexical_bonus(
        self,
        lowered_query: str,
        terms: Sequence[str],
        *,
        title: str,
        excerpt: str,
        path: str,
        relative_path: str,
        lexical_rank: float | None,
    ) -> float:
        title_lower = title.lower()
        excerpt_lower = excerpt.lower()
        path_lower = path.lower()
        relative_lower = relative_path.lower()
        bonus = 0.0

        if lowered_query and lowered_query in title_lower:
            bonus += 0.16
        if lowered_query and lowered_query in relative_lower:
            bonus += 0.12
        if lowered_query and lowered_query in path_lower:
            bonus += 0.08
        if lowered_query and lowered_query in excerpt_lower:
            bonus += 0.06

        if terms:
            title_hits = sum(1 for term in terms if term in title_lower)
            path_hits = sum(1 for term in terms if term in relative_lower or term in path_lower)
            excerpt_hits = sum(1 for term in terms if term in excerpt_lower)
            term_count = len(terms)
            bonus += 0.08 * (title_hits / term_count)
            bonus += 0.06 * (path_hits / term_count)
            bonus += 0.04 * min(excerpt_hits / term_count, 1.0)

        if lexical_rank is not None:
            bonus += max(0.0, 0.08 - min(lexical_rank, 8.0) * 0.01)
        return bonus

    def _iter_candidates(self, root: Path) -> Iterable[Path]:
        if root.is_file():
            if root.suffix.lower() in INDEXABLE_EXTENSIONS and not self._path_is_ignored(root):
                yield root
            return

        for directory, dirnames, filenames in os.walk(root, topdown=True):
            current_dir = Path(directory)
            dirnames[:] = [
                name
                for name in dirnames
                if name not in IGNORED_DIRS and not self._path_is_ignored(current_dir / name)
            ]
            for filename in filenames:
                path = current_dir / filename
                if self._path_is_ignored(path):
                    continue
                if path.suffix.lower() not in INDEXABLE_EXTENSIONS:
                    continue
                yield path

    def _path_is_ignored(self, path: Path) -> bool:
        if any(part in IGNORED_DIRS for part in path.parts):
            return True
        path_text = f"/{path.as_posix().lstrip('/')}/"
        return any(fragment in path_text for fragment in IGNORED_PATH_FRAGMENTS)

    def _extract_excerpt(self, path: Path) -> str:
        result = read_file(str(path))
        content = str(result.payload.get("content", "")).strip()
        if not content:
            raise ValueError("empty_content")
        compact = " ".join(content.split())
        excerpt = compact[:1800]
        if not excerpt:
            raise ValueError("empty_content")
        return excerpt

    def _record_discovery(
        self,
        *,
        path: Path,
        root: Path,
        stat_result: os.stat_result,
        run_id: str,
        seen_at: str,
    ) -> str:
        suffix = path.suffix.lower()
        if suffix not in INDEXABLE_EXTENSIONS:
            return SKIPPED_STATUS
        root_string = str(root)
        path_string = str(path)
        relative_path = self._relative_path(path=path, root=root)
        title = path.name
        content_type = suffix.lstrip(".") or "text"
        mtime = float(stat_result.st_mtime)
        mtime_ns = int(getattr(stat_result, "st_mtime_ns", int(mtime * 1_000_000_000)))
        file_size = int(stat_result.st_size)
        fingerprint = f"{mtime_ns}:{file_size}"
        existing = self._file_state(path_string)

        if file_size > self._max_file_bytes:
            self._upsert_file_state(
                path=path_string,
                root=root_string,
                relative_path=relative_path,
                title=title,
                suffix=suffix,
                content_type=content_type,
                mtime=mtime,
                mtime_ns=mtime_ns,
                file_size=file_size,
                fingerprint=fingerprint,
                status=SKIPPED_STATUS,
                run_id=run_id,
                updated_at=seen_at,
                last_error="",
                skip_reason="file_too_large",
                indexed_at=None if existing is None else existing["indexed_at"],
            )
            self._delete_entry(Path(path_string))
            return SKIPPED_STATUS

        if (
            existing is not None
            and str(existing["fingerprint"]) == fingerprint
            and str(existing["last_index_status"]) == INDEXED_STATUS
        ):
            self._upsert_file_state(
                path=path_string,
                root=root_string,
                relative_path=relative_path,
                title=title,
                suffix=suffix,
                content_type=content_type,
                mtime=mtime,
                mtime_ns=mtime_ns,
                file_size=file_size,
                fingerprint=fingerprint,
                status=INDEXED_STATUS,
                run_id=run_id,
                updated_at=seen_at,
                last_error="",
                skip_reason="",
                indexed_at=existing["indexed_at"],
            )
            return INDEXED_STATUS

        self._upsert_file_state(
            path=path_string,
            root=root_string,
            relative_path=relative_path,
            title=title,
            suffix=suffix,
            content_type=content_type,
            mtime=mtime,
            mtime_ns=mtime_ns,
            file_size=file_size,
            fingerprint=fingerprint,
            status=PENDING_STATUS,
            run_id=run_id,
            updated_at=seen_at,
            last_error="",
            skip_reason="",
            indexed_at=None,
        )
        self._delete_entry(path)
        return PENDING_STATUS

    def _relative_path(self, *, path: Path, root: Path) -> str:
        if root.is_file():
            return path.name
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.name

    def _mark_path_error(self, path: Path, *, root: Path, run_id: str, error: str) -> None:
        suffix = path.suffix.lower()
        updated_at = _utc_now()
        self._upsert_file_state(
            path=str(path),
            root=str(root),
            relative_path=self._relative_path(path=path, root=root),
            title=path.name,
            suffix=suffix,
            content_type=suffix.lstrip(".") or "text",
            mtime=0.0,
            mtime_ns=0,
            file_size=0,
            fingerprint="",
            status=ERROR_STATUS,
            run_id=run_id,
            updated_at=updated_at,
            last_error=error,
            skip_reason="",
            indexed_at=None,
        )
        self._delete_entry(path)

    def _mark_missing_files(self, *, root: Path, run_id: str, seen_at: str) -> int:
        rows = self._conn.execute(
            """
            SELECT path
            FROM knowledge_files
            WHERE root = ?
              AND last_seen_run_id != ?
              AND last_index_status != ?
            """,
            (str(root), run_id, DELETED_STATUS),
        ).fetchall()
        if not rows:
            return 0
        for row in rows:
            self._mark_deleted(Path(str(row["path"])), seen_at=seen_at)
        self._conn.commit()
        return len(rows)

    def _mark_deleted(self, path: Path, *, seen_at: str) -> None:
        self._conn.execute(
            """
            UPDATE knowledge_files
            SET last_index_status = ?,
                updated_at = ?,
                last_error = '',
                skip_reason = 'file_missing'
            WHERE path = ?
            """,
            (DELETED_STATUS, seen_at, str(path)),
        )
        self._delete_entry(path)

    def _mark_skipped(self, *, path: Path, reason: str, updated_at: str) -> None:
        self._conn.execute(
            """
            UPDATE knowledge_files
            SET last_index_status = ?,
                updated_at = ?,
                last_error = '',
                skip_reason = ?
            WHERE path = ?
            """,
            (SKIPPED_STATUS, updated_at, reason, str(path)),
        )
        self._delete_entry(path)

    def _mark_error(self, *, path: Path, error: str, updated_at: str) -> None:
        self._conn.execute(
            """
            UPDATE knowledge_files
            SET last_index_status = ?,
                updated_at = ?,
                last_error = ?,
                skip_reason = ''
            WHERE path = ?
            """,
            (ERROR_STATUS, updated_at, error, str(path)),
        )
        self._delete_entry(path)

    def _mark_indexed(self, *, path: Path, indexed_at: str) -> None:
        self._conn.execute(
            """
            UPDATE knowledge_files
            SET last_index_status = ?,
                indexed_at = ?,
                updated_at = ?,
                last_error = '',
                skip_reason = ''
            WHERE path = ?
            """,
            (INDEXED_STATUS, indexed_at, indexed_at, str(path)),
        )

    def _file_state(self, path: str) -> sqlite3.Row | None:
        row = self._conn.execute(
            """
            SELECT path, fingerprint, last_index_status, indexed_at
            FROM knowledge_files
            WHERE path = ?
            """,
            (path,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def _upsert_file_state(
        self,
        *,
        path: str,
        root: str,
        relative_path: str,
        title: str,
        suffix: str,
        content_type: str,
        mtime: float,
        mtime_ns: int,
        file_size: int,
        fingerprint: str,
        status: str,
        run_id: str,
        updated_at: str,
        last_error: str,
        skip_reason: str,
        indexed_at: Any,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO knowledge_files (
                path,
                root,
                relative_path,
                title,
                suffix,
                content_type,
                mtime,
                mtime_ns,
                file_size,
                fingerprint,
                last_index_status,
                discovered_at,
                last_seen_at,
                last_seen_run_id,
                indexed_at,
                updated_at,
                last_error,
                skip_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                root = excluded.root,
                relative_path = excluded.relative_path,
                title = excluded.title,
                suffix = excluded.suffix,
                content_type = excluded.content_type,
                mtime = excluded.mtime,
                mtime_ns = excluded.mtime_ns,
                file_size = excluded.file_size,
                fingerprint = excluded.fingerprint,
                last_index_status = excluded.last_index_status,
                last_seen_at = excluded.last_seen_at,
                last_seen_run_id = excluded.last_seen_run_id,
                indexed_at = COALESCE(excluded.indexed_at, knowledge_files.indexed_at),
                updated_at = excluded.updated_at,
                last_error = excluded.last_error,
                skip_reason = excluded.skip_reason
            """,
            (
                path,
                root,
                relative_path,
                title,
                suffix,
                content_type,
                mtime,
                mtime_ns,
                file_size,
                fingerprint,
                status,
                updated_at,
                updated_at,
                run_id,
                indexed_at,
                updated_at,
                last_error,
                skip_reason,
            ),
        )

    def _pending_rows(self, *, roots: Sequence[str], limit: int) -> list[sqlite3.Row]:
        where_clause, params = self._root_filter_clause(roots, table_alias="knowledge_files")
        suffix_clause = where_clause.replace("WHERE", "AND", 1) if where_clause else ""
        return self._conn.execute(
            f"""
            SELECT
                path,
                root,
                relative_path,
                title,
                suffix,
                content_type,
                mtime,
                mtime_ns,
                file_size
            FROM knowledge_files
            WHERE last_index_status = ? {suffix_clause}
            ORDER BY mtime_ns DESC, file_size ASC, path ASC
            LIMIT ?
            """,
            (PENDING_STATUS, *params, limit),
        ).fetchall()

    def _count_files_by_status(
        self,
        status: str,
        *,
        roots: Sequence[str] | None = None,
    ) -> int:
        where_clause, params = self._root_filter_clause(roots or (), table_alias="knowledge_files")
        suffix_clause = where_clause.replace("WHERE", "AND", 1) if where_clause else ""
        row = self._conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM knowledge_files
            WHERE last_index_status = ? {suffix_clause}
            """,
            (status, *params),
        ).fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def _has_pending(self, roots: Sequence[str] | Sequence[Path] | None) -> bool:
        root_strings = [
            str(path)
            for path in self._selected_paths(roots, prefer_all_when_empty=True)
        ]
        return self._count_files_by_status(PENDING_STATUS, roots=root_strings) > 0

    def _upsert_entry(
        self,
        *,
        path: Path,
        root: str,
        relative_path: str,
        title: str,
        excerpt: str,
        suffix: str,
        mtime: float,
        file_size: int,
        embedding: np.ndarray,
        indexed_at: str,
    ) -> None:
        modified_at = _iso_from_mtime(mtime)
        self._conn.execute(
            """
            INSERT INTO knowledge_entries (
                path,
                root,
                relative_path,
                title,
                excerpt,
                content_type,
                suffix,
                mtime,
                file_size,
                embedding_json,
                modified_at,
                indexed_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                root = excluded.root,
                relative_path = excluded.relative_path,
                title = excluded.title,
                excerpt = excluded.excerpt,
                content_type = excluded.content_type,
                suffix = excluded.suffix,
                mtime = excluded.mtime,
                file_size = excluded.file_size,
                embedding_json = excluded.embedding_json,
                modified_at = excluded.modified_at,
                indexed_at = excluded.indexed_at,
                updated_at = excluded.updated_at
            """,
            (
                str(path),
                root,
                relative_path,
                title,
                excerpt,
                suffix.lstrip(".") or "text",
                suffix,
                mtime,
                file_size,
                json.dumps(embedding.tolist(), ensure_ascii=False),
                modified_at,
                indexed_at,
                indexed_at,
            ),
        )
        if self._fts_enabled:
            self._conn.execute("DELETE FROM knowledge_fts WHERE path = ?", (str(path),))
            self._conn.execute(
                """
                INSERT INTO knowledge_fts (path, title, excerpt, relative_path, root)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(path), title, excerpt, relative_path, root),
            )

    def _delete_entry(self, path: Path) -> None:
        self._conn.execute("DELETE FROM knowledge_entries WHERE path = ?", (str(path),))
        if self._fts_enabled:
            self._conn.execute("DELETE FROM knowledge_fts WHERE path = ?", (str(path),))

    def _start_run(self, roots: Sequence[str], *, batch_size: int, refresh: bool) -> str:
        run_id = str(uuid4())
        started_at = _utc_now()
        self._conn.execute(
            """
            INSERT INTO knowledge_index_runs (
                run_id,
                roots_json,
                status,
                batch_size,
                refresh,
                started_at,
                finished_at,
                scanned_files,
                processed_files,
                indexed_files,
                unchanged_files,
                skipped_files,
                failed_files,
                deleted_files,
                pending_files,
                message
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 0, 0, '')
            """,
            (
                run_id,
                json.dumps(list(roots), ensure_ascii=False),
                "running",
                batch_size,
                1 if refresh else 0,
                started_at,
            ),
        )
        self._conn.commit()
        return run_id

    def _update_run_counts(self, run_id: str, counters: _IndexCounters) -> None:
        self._conn.execute(
            """
            UPDATE knowledge_index_runs
            SET scanned_files = ?,
                processed_files = ?,
                indexed_files = ?,
                unchanged_files = ?,
                skipped_files = ?,
                failed_files = ?,
                deleted_files = ?,
                pending_files = ?
            WHERE run_id = ?
            """,
            (
                counters.scanned_files,
                counters.processed_files,
                counters.indexed_files,
                counters.unchanged_files,
                counters.skipped_files,
                counters.failed_files,
                counters.deleted_files,
                counters.pending_files,
                run_id,
            ),
        )
        self._conn.commit()

    def _finish_run(
        self,
        run_id: str,
        result: KnowledgeIndexResult,
        *,
        message: str = "",
    ) -> None:
        self._conn.execute(
            """
            UPDATE knowledge_index_runs
            SET status = ?,
                finished_at = ?,
                scanned_files = ?,
                processed_files = ?,
                indexed_files = ?,
                unchanged_files = ?,
                skipped_files = ?,
                failed_files = ?,
                deleted_files = ?,
                pending_files = ?,
                message = ?
            WHERE run_id = ?
            """,
            (
                result.status,
                _utc_now(),
                result.scanned_files,
                result.processed_files,
                result.indexed_files,
                result.unchanged_files,
                result.skipped_files,
                result.failed_files,
                result.deleted_files,
                result.pending_files,
                message,
                run_id,
            ),
        )
        self._conn.commit()

    def _recent_runs(self, limit: int) -> list[KnowledgeIndexRun]:
        rows = self._conn.execute(
            """
            SELECT
                run_id,
                roots_json,
                status,
                started_at,
                finished_at,
                batch_size,
                refresh,
                scanned_files,
                processed_files,
                indexed_files,
                unchanged_files,
                skipped_files,
                failed_files,
                deleted_files,
                pending_files,
                message
            FROM knowledge_index_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            KnowledgeIndexRun(
                run_id=str(row["run_id"]),
                status=str(row["status"]),
                roots=list(json.loads(str(row["roots_json"]))),
                started_at=str(row["started_at"]),
                finished_at=None if row["finished_at"] is None else str(row["finished_at"]),
                batch_size=int(row["batch_size"]),
                refresh=bool(row["refresh"]),
                scanned_files=int(row["scanned_files"]),
                processed_files=int(row["processed_files"]),
                indexed_files=int(row["indexed_files"]),
                unchanged_files=int(row["unchanged_files"]),
                skipped_files=int(row["skipped_files"]),
                failed_files=int(row["failed_files"]),
                deleted_files=int(row["deleted_files"]),
                pending_files=int(row["pending_files"]),
                message=str(row["message"]),
            )
            for row in rows
        ]

    def _selected_paths(
        self,
        paths: Sequence[Path | str] | None,
        *,
        prefer_all_when_empty: bool = False,
    ) -> list[Path]:
        if paths is None:
            raw_paths: Sequence[Path | str]
            if self._default_roots:
                raw_paths = self._default_roots
            elif prefer_all_when_empty:
                raw_paths = self._known_roots()
            else:
                raw_paths = ()
        else:
            raw_paths = paths

        resolved: list[Path] = []
        seen: set[str] = set()
        for raw_path in raw_paths:
            path = Path(raw_path).expanduser().resolve()
            path_string = str(path)
            if path_string in seen:
                continue
            seen.add(path_string)
            resolved.append(path)
        return resolved

    def _known_roots(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT root FROM knowledge_files ORDER BY root ASC"
        ).fetchall()
        return [str(row["root"]) for row in rows]

    def _resolve_batch_size(self, batch_size: int | None) -> int:
        if batch_size is not None and batch_size > 0:
            return batch_size
        if self._max_files_per_root > 0:
            return self._max_files_per_root
        return DEFAULT_CANDIDATE_WINDOW

    def _root_filter_clause(
        self,
        roots: Sequence[str],
        *,
        table_alias: str,
    ) -> tuple[str, tuple[Any, ...]]:
        unique_roots = [root for root in roots if root]
        if not unique_roots:
            return "", ()
        placeholders = ", ".join("?" for _ in unique_roots)
        return f"WHERE {table_alias}.root IN ({placeholders})", tuple(unique_roots)

    def _entry_filters(
        self,
        *,
        roots: Sequence[str],
        suffixes: Sequence[str],
    ) -> tuple[str, tuple[Any, ...]]:
        clauses: list[str] = []
        params: list[Any] = []
        if roots:
            placeholders = ", ".join("?" for _ in roots)
            clauses.append(f"knowledge_entries.root IN ({placeholders})")
            params.extend(roots)
        if suffixes:
            placeholders = ", ".join("?" for _ in suffixes)
            clauses.append(f"knowledge_entries.suffix IN ({placeholders})")
            params.extend(suffixes)
        if not clauses:
            return "", ()
        return " AND " + " AND ".join(clauses), tuple(params)

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            self._db_path,
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                path TEXT PRIMARY KEY,
                root TEXT NOT NULL,
                relative_path TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                content_type TEXT NOT NULL,
                suffix TEXT NOT NULL DEFAULT '',
                mtime REAL NOT NULL,
                file_size INTEGER NOT NULL,
                embedding_json TEXT NOT NULL,
                modified_at TEXT NOT NULL DEFAULT '',
                indexed_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )
        self._ensure_columns(
            conn,
            table_name="knowledge_entries",
            columns={
                "relative_path": "TEXT NOT NULL DEFAULT ''",
                "suffix": "TEXT NOT NULL DEFAULT ''",
                "modified_at": "TEXT NOT NULL DEFAULT ''",
                "indexed_at": "TEXT NOT NULL DEFAULT ''",
            },
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_files (
                path TEXT PRIMARY KEY,
                root TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                title TEXT NOT NULL,
                suffix TEXT NOT NULL,
                content_type TEXT NOT NULL,
                mtime REAL NOT NULL,
                mtime_ns INTEGER NOT NULL,
                file_size INTEGER NOT NULL,
                fingerprint TEXT NOT NULL,
                last_index_status TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_seen_run_id TEXT NOT NULL,
                indexed_at TEXT,
                updated_at TEXT NOT NULL,
                last_error TEXT NOT NULL DEFAULT '',
                skip_reason TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_index_runs (
                run_id TEXT PRIMARY KEY,
                roots_json TEXT NOT NULL,
                status TEXT NOT NULL,
                batch_size INTEGER NOT NULL,
                refresh INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                scanned_files INTEGER NOT NULL,
                processed_files INTEGER NOT NULL,
                indexed_files INTEGER NOT NULL,
                unchanged_files INTEGER NOT NULL,
                skipped_files INTEGER NOT NULL,
                failed_files INTEGER NOT NULL,
                deleted_files INTEGER NOT NULL,
                pending_files INTEGER NOT NULL,
                message TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_entries_updated_at
            ON knowledge_entries (updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_entries_root_suffix
            ON knowledge_entries (root, suffix, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_files_root_status
            ON knowledge_files (root, last_index_status, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_runs_started_at
            ON knowledge_index_runs (started_at DESC)
            """
        )

        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                USING fts5(path, title, excerpt, relative_path, root)
                """
            )
            self._fts_enabled = True
        except sqlite3.OperationalError:
            self._fts_enabled = False

        try:
            self._backfill_legacy_rows(conn)
            if self._fts_enabled:
                self._sync_fts(conn)
            conn.commit()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            conn.rollback()
            if self._logger is not None:
                self._logger.log(
                    "knowledge_connect_maintenance_skipped",
                    reason="database_locked",
                )
        return conn

    def _ensure_columns(
        self,
        conn: sqlite3.Connection,
        *,
        table_name: str,
        columns: dict[str, str],
    ) -> None:
        existing = {
            str(row["name"])
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, ddl in columns.items():
            if column_name in existing:
                continue
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def _backfill_legacy_rows(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT
                path,
                root,
                relative_path,
                title,
                excerpt,
                content_type,
                suffix,
                mtime,
                file_size,
                indexed_at,
                updated_at
            FROM knowledge_entries
            ORDER BY updated_at DESC
            """
        ).fetchall()
        for row in rows:
            path = Path(str(row["path"]))
            suffix = str(row["suffix"]) or path.suffix.lower()
            root = str(row["root"])
            relative_path = str(row["relative_path"]) or path.name
            indexed_at = str(row["indexed_at"]) or str(row["updated_at"])
            modified_at = str(row["modified_at"]) if "modified_at" in row else ""
            if not modified_at:
                conn.execute(
                    """
                    UPDATE knowledge_entries
                    SET suffix = ?, relative_path = ?, modified_at = ?, indexed_at = ?
                    WHERE path = ?
                    """,
                    (
                        suffix,
                        relative_path,
                        _iso_from_mtime(float(row["mtime"])),
                        indexed_at,
                        str(row["path"]),
                    ),
                )
            file_row = conn.execute(
                "SELECT path FROM knowledge_files WHERE path = ?",
                (str(row["path"]),),
            ).fetchone()
            if file_row is not None:
                continue
            mtime = float(row["mtime"])
            file_size = int(row["file_size"])
            mtime_ns = int(mtime * 1_000_000_000)
            timestamp = indexed_at or str(row["updated_at"])
            conn.execute(
                """
                INSERT INTO knowledge_files (
                    path,
                    root,
                    relative_path,
                    title,
                    suffix,
                    content_type,
                    mtime,
                    mtime_ns,
                    file_size,
                    fingerprint,
                    last_index_status,
                    discovered_at,
                    last_seen_at,
                    last_seen_run_id,
                    indexed_at,
                    updated_at,
                    last_error,
                    skip_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '')
                """,
                (
                    str(row["path"]),
                    root,
                    relative_path,
                    str(row["title"]),
                    suffix,
                    str(row["content_type"]),
                    mtime,
                    mtime_ns,
                    file_size,
                    f"{mtime_ns}:{file_size}",
                    INDEXED_STATUS,
                    timestamp,
                    timestamp,
                    "legacy",
                    indexed_at,
                    str(row["updated_at"]),
                ),
            )

    def _sync_fts(self, conn: sqlite3.Connection) -> None:
        entry_count = conn.execute("SELECT COUNT(*) AS count FROM knowledge_entries").fetchone()
        fts_count = conn.execute("SELECT COUNT(*) AS count FROM knowledge_fts").fetchone()
        if entry_count is None or fts_count is None:
            return
        if int(entry_count["count"]) == int(fts_count["count"]):
            return
        conn.execute("DELETE FROM knowledge_fts")
        conn.execute(
            """
            INSERT INTO knowledge_fts (path, title, excerpt, relative_path, root)
            SELECT path, title, excerpt, relative_path, root
            FROM knowledge_entries
            """
        )


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return np.asarray(vector, dtype=np.float32)
    return np.asarray(vector / norm, dtype=np.float32)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _iso_from_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat()


def _tokenize_query(query: str) -> list[str]:
    return [token for token in re.findall(r"[0-9A-Za-zÀ-ÿ_]+", query.lower()) if token]


KNOWLEDGE_QUERY_STOPWORDS = {
    "a",
    "al",
    "alguna",
    "alguno",
    "apunte",
    "apuntes",
    "archivo",
    "archivos",
    "book",
    "busca",
    "buscar",
    "carpeta",
    "carpetas",
    "con",
    "cuál",
    "cual",
    "cuáles",
    "cuales",
    "de",
    "del",
    "dime",
    "document",
    "documento",
    "documentos",
    "el",
    "en",
    "encuentra",
    "escritorio",
    "esta",
    "este",
    "favor",
    "file",
    "files",
    "find",
    "folder",
    "hazme",
    "la",
    "las",
    "leer",
    "libro",
    "libros",
    "lo",
    "los",
    "me",
    "mi",
    "mis",
    "mira",
    "muestrame",
    "muéstrame",
    "nota",
    "notas",
    "notes",
    "para",
    "pdf",
    "por",
    "que",
    "qué",
    "quiero",
    "relacionado",
    "sobre",
    "the",
    "todo",
    "todos",
    "una",
    "uno",
    "unos",
    "ver",
}


def _build_query_plan(query: str) -> KnowledgeQueryPlan:
    normalized = " ".join(query.split()).strip()
    variants: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        compact = " ".join(candidate.split()).strip()
        if not compact:
            return
        key = compact.casefold()
        if key in seen:
            return
        seen.add(key)
        variants.append(compact)

    add(normalized)
    for match in re.finditer(r'"([^"]+)"|\'([^\']+)\'', normalized):
        phrase = match.group(1) or match.group(2) or ""
        add(phrase)

    for raw_token in re.findall(r"[0-9A-Za-zÀ-ÿ_.-]+", normalized):
        if "." not in raw_token:
            continue
        stem = Path(raw_token).stem.replace("-", " ").replace("_", " ")
        add(stem)

    core_terms = [
        token
        for token in _tokenize_query(normalized)
        if len(token) > 2 and token not in KNOWLEDGE_QUERY_STOPWORDS
    ]
    if core_terms:
        add(" ".join(core_terms[:8]))
        if len(core_terms) >= 2:
            add(" ".join(core_terms[:2]))
            add(" ".join(core_terms[-2:]))
        if len(core_terms) >= 3:
            add(" ".join(core_terms[:3]))

    if len(variants) > 6:
        variants = variants[:6]

    return KnowledgeQueryPlan(
        original_query=normalized,
        query_variants=tuple(variants or [normalized]),
        core_terms=tuple(core_terms[:8]),
    )


def _exact_variant_bonus(
    variant: str,
    *,
    title: str,
    excerpt: str,
    path: str,
    relative_path: str,
) -> float:
    lowered = variant.casefold().strip()
    if len(lowered) < 4:
        return 0.0
    bonus = 0.0
    title_lower = title.casefold()
    excerpt_lower = excerpt.casefold()
    path_lower = path.casefold()
    relative_lower = relative_path.casefold()
    if lowered in title_lower:
        bonus += 0.18
    if lowered in relative_lower:
        bonus += 0.14
    if lowered in path_lower:
        bonus += 0.10
    if lowered in excerpt_lower:
        bonus += 0.06
    return bonus


def _chunked(rows: Sequence[sqlite3.Row], *, size: int) -> Iterable[list[sqlite3.Row]]:
    for index in range(0, len(rows), size):
        yield list(rows[index : index + size])


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def install_knowledge_launch_agent(
    *,
    adv_command: str,
    interval_minutes: int = 60,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    roots: Sequence[str] = (),
) -> Path:
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agents_dir / "com.adv-archon.knowledge.plist"
    program_arguments = [adv_command, "knowledge", "run-batch", str(batch_size), *roots]
    plist_path.write_bytes(
        plistlib.dumps(
            {
                "Label": "com.adv-archon.knowledge",
                "ProgramArguments": program_arguments,
                "StartInterval": interval_minutes * 60,
                "RunAtLoad": True,
            }
        )
    )
    subprocess.run(["launchctl", "unload", str(plist_path)], check=False, capture_output=True)
    completed = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "No he podido cargar el launch agent.")
    return plist_path
