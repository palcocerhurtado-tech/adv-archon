from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import numpy as np

from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import EmbeddingEncoder


@dataclass(slots=True)
class WebLibraryRecord:
    id: int
    url: str
    canonical_url: str
    title: str
    source: str
    domain: str
    source_type: str
    snippet: str
    text: str
    tags: list[str]
    metadata: dict[str, Any]
    freshness_ttl_hours: int
    freshness_state: str
    age_hours: float
    refresh_count: int
    created_at: str
    updated_at: str
    last_refreshed_at: str
    stale_after: str
    published_at: str | None
    score: float | None = None


@dataclass(slots=True)
class WebLibraryIngestResult:
    added: int
    updated: int
    skipped: int
    records: list[WebLibraryRecord]


class WebLibraryStore:
    def __init__(
        self,
        db_path: Path,
        *,
        encoder: EmbeddingEncoder | None = None,
        persist: bool = True,
        logger: AppLogger | None = None,
        max_text_chars: int = 16_000,
        max_snippet_chars: int = 480,
    ) -> None:
        self._db_path = db_path
        self._encoder = encoder
        self._persist = persist
        self._logger = logger
        self._max_text_chars = max_text_chars
        self._max_snippet_chars = max_snippet_chars
        self._conn = self._connect()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS count FROM web_library_entries").fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def upsert_entry(
        self,
        *,
        url: str,
        title: str | None = None,
        text: str = "",
        snippet: str | None = None,
        tags: Sequence[str] | None = None,
        source: str | None = None,
        source_type: str = "page",
        freshness_ttl_hours: int = 168,
        published_at: str | datetime | None = None,
        captured_at: str | datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> WebLibraryRecord:
        record, _created = self._upsert_entry(
            url=url,
            title=title,
            text=text,
            snippet=snippet,
            tags=tags,
            source=source,
            source_type=source_type,
            freshness_ttl_hours=freshness_ttl_hours,
            published_at=published_at,
            captured_at=captured_at,
            metadata=metadata,
        )
        return record

    def ingest_search_results(
        self,
        query: str,
        results: Sequence[Mapping[str, Any]],
        *,
        tags: Sequence[str] | None = None,
        freshness_ttl_hours: int = 72,
        captured_at: str | datetime | None = None,
    ) -> WebLibraryIngestResult:
        added = 0
        updated = 0
        skipped = 0
        records: list[WebLibraryRecord] = []
        base_tags = list(tags or ())

        for rank, item in enumerate(results, start=1):
            raw_url = str(item.get("url") or item.get("href") or "").strip()
            if not raw_url:
                skipped += 1
                continue
            raw_title = str(item.get("title") or "").strip() or None
            raw_snippet = str(item.get("snippet") or item.get("body") or "").strip() or None
            raw_source = str(item.get("source") or item.get("provider") or "").strip() or None
            raw_metadata: dict[str, Any] = {
                "captured_from": "search",
                "search_rank": rank,
            }
            clean_query = query.strip()
            if clean_query:
                raw_metadata["queries"] = [clean_query]

            entry_tags = [*base_tags]
            record, created = self._upsert_entry(
                url=raw_url,
                title=raw_title,
                text="",
                snippet=raw_snippet,
                tags=entry_tags,
                source=raw_source,
                source_type="search_result",
                freshness_ttl_hours=freshness_ttl_hours,
                published_at=None,
                captured_at=captured_at,
                metadata=raw_metadata,
            )
            records.append(record)
            if created:
                added += 1
            else:
                updated += 1

        if self._logger is not None:
            self._logger.log(
                "web_library_ingested_search_results",
                query=query,
                added=added,
                updated=updated,
                skipped=skipped,
            )
        return WebLibraryIngestResult(
            added=added,
            updated=updated,
            skipped=skipped,
            records=records,
        )

    def get_by_url(self, url: str) -> WebLibraryRecord | None:
        canonical_url = _canonicalize_url(url)
        row = self._conn.execute(
            "SELECT * FROM web_library_entries WHERE canonical_url = ?",
            (canonical_url,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        tags: Sequence[str] | None = None,
        include_stale: bool = True,
    ) -> list[WebLibraryRecord]:
        rows = self._conn.execute(
            "SELECT * FROM web_library_entries ORDER BY updated_at DESC"
        ).fetchall()
        if not rows:
            return []

        clean_query = query.strip()
        query_terms = _tokenize(clean_query)
        required_tags = set(_normalize_tags(tags or []))
        query_vector = self._encode_query(clean_query)

        ranked: list[WebLibraryRecord] = []
        for row in rows:
            record = self._row_to_record(row)
            record_tags = set(record.tags)
            if required_tags and not required_tags.issubset(record_tags):
                continue
            if not include_stale and record.freshness_state != "fresh":
                continue

            score = self._score_record(
                row,
                record,
                query=clean_query,
                query_terms=query_terms,
                required_tags=required_tags,
                query_vector=query_vector,
            )
            if clean_query and score <= 0 and query_vector is None:
                continue
            record.score = round(score, 4) if clean_query else None
            ranked.append(record)

        ranked.sort(
            key=lambda item: (
                item.score if item.score is not None else 0.0,
                1 if item.freshness_state == "fresh" else 0,
                item.last_refreshed_at,
                item.updated_at,
            ),
            reverse=True,
        )
        if not clean_query:
            ranked.sort(
                key=lambda item: (
                    1 if item.freshness_state == "fresh" else 0,
                    item.last_refreshed_at,
                    item.updated_at,
                ),
                reverse=True,
            )
        if self._logger is not None:
            self._logger.log(
                "web_library_searched",
                query=query,
                tags=list(required_tags),
                include_stale=include_stale,
                results=min(limit, len(ranked)),
            )
        return ranked[:limit]

    def _upsert_entry(
        self,
        *,
        url: str,
        title: str | None,
        text: str,
        snippet: str | None,
        tags: Sequence[str] | None,
        source: str | None,
        source_type: str,
        freshness_ttl_hours: int,
        published_at: str | datetime | None,
        captured_at: str | datetime | None,
        metadata: Mapping[str, Any] | None,
    ) -> tuple[WebLibraryRecord, bool]:
        clean_url = url.strip()
        if not clean_url:
            raise ValueError("Web library entries need a URL.")
        canonical_url = _canonicalize_url(clean_url)

        provided_title = (title or "").strip()
        provided_text = self._trim_text(text)
        provided_snippet = self._trim_snippet(snippet or "")
        if not provided_text and not provided_snippet:
            raise ValueError("Web library entries need snippet or text.")

        normalized_ttl = max(int(freshness_ttl_hours), 1)
        clean_source_type = source_type.strip() or "page"
        clean_source = (source or "").strip()
        clean_tags = _normalize_tags(tags or [])
        clean_metadata = dict(metadata or {})

        captured_dt = _coerce_datetime(captured_at)
        published_text = _coerce_datetime_text(published_at)
        now = _now_utc()

        existing = self._conn.execute(
            """
            SELECT *
            FROM web_library_entries
            WHERE canonical_url = ?
            """,
            (canonical_url,),
        ).fetchone()

        if existing is None:
            effective_title = provided_title or _infer_title(canonical_url)
            effective_text = provided_text
            effective_snippet = provided_snippet or _build_snippet(
                effective_text,
                max_chars=self._max_snippet_chars,
            )
            effective_source = clean_source or _infer_source(canonical_url)
            effective_tags = clean_tags
            effective_metadata = clean_metadata
            effective_refresh_dt = captured_dt
            effective_ttl = normalized_ttl
            refresh_count = 1
            created_at = now.isoformat()
        else:
            existing_title = str(existing["title"])
            existing_text = str(existing["text"])
            existing_snippet = str(existing["snippet"])
            existing_source = str(existing["source"])
            existing_tags = json.loads(str(existing["tags_json"]))
            existing_metadata = json.loads(str(existing["metadata_json"]))
            existing_refresh_dt = _coerce_datetime(str(existing["last_refreshed_at"]))
            existing_ttl = int(existing["freshness_ttl_hours"])
            refresh_count = int(existing["refresh_count"]) + 1
            created_at = str(existing["created_at"])

            effective_title = provided_title or existing_title or _infer_title(canonical_url)
            effective_text = provided_text or existing_text
            effective_snippet = provided_snippet or existing_snippet or _build_snippet(
                effective_text,
                max_chars=self._max_snippet_chars,
            )
            effective_source = clean_source or existing_source or _infer_source(canonical_url)
            effective_tags = _normalize_tags([*existing_tags, *clean_tags])
            effective_metadata = _merge_metadata(existing_metadata, clean_metadata)

            if captured_dt >= existing_refresh_dt:
                effective_refresh_dt = captured_dt
                effective_ttl = normalized_ttl
            else:
                effective_refresh_dt = existing_refresh_dt
                effective_ttl = existing_ttl
            if published_text is None:
                published_text = (
                    str(existing["published_at"]) if existing["published_at"] is not None else None
                )

        if not effective_text and not effective_snippet:
            raise ValueError("Web library entries need snippet or text.")

        stale_after = effective_refresh_dt + timedelta(hours=effective_ttl)
        embedding = self._encode_entry(
            title=effective_title,
            snippet=effective_snippet,
            text=effective_text,
            tags=effective_tags,
            source=effective_source,
        )
        text_hash = _hash_document(
            title=effective_title,
            snippet=effective_snippet,
            text=effective_text,
        )

        self._conn.execute(
            """
            INSERT INTO web_library_entries (
                canonical_url,
                url,
                title,
                source,
                domain,
                source_type,
                snippet,
                text,
                tags_json,
                metadata_json,
                text_hash,
                freshness_ttl_hours,
                created_at,
                updated_at,
                last_refreshed_at,
                stale_after,
                published_at,
                refresh_count,
                embedding_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_url) DO UPDATE SET
                url = excluded.url,
                title = excluded.title,
                source = excluded.source,
                domain = excluded.domain,
                source_type = excluded.source_type,
                snippet = excluded.snippet,
                text = excluded.text,
                tags_json = excluded.tags_json,
                metadata_json = excluded.metadata_json,
                text_hash = excluded.text_hash,
                freshness_ttl_hours = excluded.freshness_ttl_hours,
                updated_at = excluded.updated_at,
                last_refreshed_at = excluded.last_refreshed_at,
                stale_after = excluded.stale_after,
                published_at = excluded.published_at,
                refresh_count = excluded.refresh_count,
                embedding_json = excluded.embedding_json
            """,
            (
                canonical_url,
                clean_url,
                effective_title,
                effective_source,
                urlparse(canonical_url).netloc,
                clean_source_type,
                effective_snippet,
                effective_text,
                json.dumps(effective_tags, ensure_ascii=False),
                json.dumps(effective_metadata, ensure_ascii=False),
                text_hash,
                effective_ttl,
                created_at,
                now.isoformat(),
                effective_refresh_dt.isoformat(),
                stale_after.isoformat(),
                published_text,
                refresh_count,
                json.dumps(embedding.tolist()) if embedding is not None else "[]",
            ),
        )
        self._conn.commit()

        record = self.get_by_url(canonical_url)
        if record is None:
            raise RuntimeError("The stored web library entry could not be reloaded.")
        created = existing is None
        if self._logger is not None:
            self._logger.log(
                "web_library_upserted",
                url=record.canonical_url,
                source_type=record.source_type,
                created=created,
                freshness_state=record.freshness_state,
                tags=record.tags,
            )
        return record, created

    def _encode_query(self, query: str) -> np.ndarray | None:
        if self._encoder is None:
            return None
        clean_query = query.strip()
        if not clean_query:
            return None
        encoded = self._encoder.encode_texts([clean_query])
        if encoded.size == 0:
            return None
        return _normalize_vector(encoded[0])

    def _encode_entry(
        self,
        *,
        title: str,
        snippet: str,
        text: str,
        tags: Sequence[str],
        source: str,
    ) -> np.ndarray | None:
        if self._encoder is None:
            return None
        payload = "\n\n".join(
            fragment
            for fragment in [
                title.strip(),
                snippet.strip(),
                text[:3000].strip(),
                " ".join(tags).strip(),
                source.strip(),
            ]
            if fragment
        )
        if not payload:
            return None
        encoded = self._encoder.encode_texts([payload])
        if encoded.size == 0:
            return None
        return _normalize_vector(encoded[0])

    def _score_record(
        self,
        row: sqlite3.Row,
        record: WebLibraryRecord,
        *,
        query: str,
        query_terms: Sequence[str],
        required_tags: set[str],
        query_vector: np.ndarray | None,
    ) -> float:
        if not query:
            return 0.0

        lowered_query = query.lower()
        title = record.title.lower()
        snippet = record.snippet.lower()
        text = record.text.lower()
        canonical_url = record.canonical_url.lower()
        domain = record.domain.lower()
        tag_text = " ".join(record.tags).lower()

        semantic = 0.0
        if query_vector is not None:
            embedding_payload = str(row["embedding_json"])
            if embedding_payload and embedding_payload != "[]":
                candidate = np.asarray(json.loads(embedding_payload), dtype=np.float32)
                if candidate.size and candidate.shape == query_vector.shape:
                    semantic = float(_normalize_vector(candidate) @ query_vector)

        lexical = 0.0
        if lowered_query in title:
            lexical += 0.24
        if lowered_query in snippet:
            lexical += 0.15
        if lowered_query in text:
            lexical += 0.09
        if lowered_query in canonical_url or lowered_query in domain:
            lexical += 0.06
        if lowered_query in tag_text:
            lexical += 0.08

        for term in query_terms:
            if term in title:
                lexical += 0.09
            if term in snippet:
                lexical += 0.05
            if term in text:
                lexical += 0.02
            if term in tag_text:
                lexical += 0.03

        freshness_bonus = 0.04 if record.freshness_state == "fresh" else -0.02
        tag_bonus = 0.03 * len(required_tags.intersection(record.tags))
        return semantic + lexical + freshness_bonus + tag_bonus

    def _row_to_record(self, row: sqlite3.Row) -> WebLibraryRecord:
        last_refreshed_at = str(row["last_refreshed_at"])
        refreshed_dt = _coerce_datetime(last_refreshed_at)
        age_hours = max((_now_utc() - refreshed_dt).total_seconds() / 3600.0, 0.0)
        stale_after = str(row["stale_after"])
        freshness_state = (
            "fresh" if _coerce_datetime(stale_after) >= _now_utc() else "stale"
        )
        return WebLibraryRecord(
            id=int(row["id"]),
            url=str(row["url"]),
            canonical_url=str(row["canonical_url"]),
            title=str(row["title"]),
            source=str(row["source"]),
            domain=str(row["domain"]),
            source_type=str(row["source_type"]),
            snippet=str(row["snippet"]),
            text=str(row["text"]),
            tags=list(json.loads(str(row["tags_json"]))),
            metadata=dict(json.loads(str(row["metadata_json"]))),
            freshness_ttl_hours=int(row["freshness_ttl_hours"]),
            freshness_state=freshness_state,
            age_hours=round(age_hours, 3),
            refresh_count=int(row["refresh_count"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            last_refreshed_at=last_refreshed_at,
            stale_after=stale_after,
            published_at=str(row["published_at"]) if row["published_at"] is not None else None,
        )

    def _trim_text(self, text: str) -> str:
        return text.strip()[: self._max_text_chars]

    def _trim_snippet(self, snippet: str) -> str:
        return _compact_whitespace(snippet)[: self._max_snippet_chars]

    def _connect(self) -> sqlite3.Connection:
        if self._persist:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path, timeout=30.0)
        else:
            conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        if self._persist:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS web_library_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_url TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                domain TEXT NOT NULL,
                source_type TEXT NOT NULL,
                snippet TEXT NOT NULL,
                text TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                freshness_ttl_hours INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_refreshed_at TEXT NOT NULL,
                stale_after TEXT NOT NULL,
                published_at TEXT,
                refresh_count INTEGER NOT NULL,
                embedding_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_web_library_updated_at
            ON web_library_entries (updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_web_library_domain
            ON web_library_entries (domain)
            """
        )
        return conn


def _canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL for web library entry: {url}")

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError(f"Invalid URL for web library entry: {url}")

    default_port = (scheme == "http" and parsed.port == 80) or (
        scheme == "https" and parsed.port == 443
    )
    if parsed.port is not None and not default_port:
        netloc = f"{hostname}:{parsed.port}"
    else:
        netloc = hostname

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def _infer_title(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.rstrip("/").split("/")[-1].strip()
    if slug:
        humanized = slug.replace("-", " ").replace("_", " ").strip()
        return humanized or parsed.netloc
    return parsed.netloc


def _infer_source(url: str) -> str:
    return urlparse(url).netloc


def _coerce_datetime(value: str | datetime | None) -> datetime:
    if value is None:
        return _now_utc()
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    normalized = value.strip()
    if not normalized:
        return _now_utc()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _coerce_datetime_text(value: str | datetime | None) -> str | None:
    if value is None:
        return None
    return _coerce_datetime(value).isoformat()


def _normalize_tags(tags: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        clean = _compact_whitespace(tag).lower()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        normalized.append(clean)
    return normalized


def _compact_whitespace(text: str) -> str:
    return " ".join(text.split())


def _build_snippet(text: str, *, max_chars: int) -> str:
    compact = _compact_whitespace(text)
    return compact[:max_chars]


def _merge_metadata(
    existing: Mapping[str, Any],
    incoming: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], list) and isinstance(value, list):
            seen: list[Any] = []
            for item in [*merged[key], *value]:
                if item not in seen:
                    seen.append(item)
            merged[key] = seen
            continue
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_metadata(
                dict(merged[key]),
                value,
            )
            continue
        merged[key] = value
    return merged


def _hash_document(*, title: str, snippet: str, text: str) -> str:
    payload = "\n\n".join([title, snippet, text]).encode("utf-8")
    return sha256(payload).hexdigest()


def _tokenize(query: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for chunk in query.lower().replace("/", " ").replace("-", " ").split():
        token = chunk.strip()
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return np.asarray(vector, dtype=np.float32)
    return np.asarray(vector / norm, dtype=np.float32)


def _now_utc() -> datetime:
    return datetime.now(UTC)
