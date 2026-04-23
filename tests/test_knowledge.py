from pathlib import Path

import numpy as np

from adv_archon.core.knowledge import KnowledgeStore
from adv_archon.tools.knowledge_tools import KnowledgeTools


class FakeEncoder:
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            lowered = text.lower()
            vector = np.array(
                [
                    1.0 if "acme" in lowered else 0.0,
                    1.0 if "python" in lowered else 0.0,
                    1.0 if "roadmap" in lowered else 0.0,
                    float((len(lowered) % 5) + 1),
                ],
                dtype=np.float32,
            )
            norm = np.linalg.norm(vector)
            rows.append(vector if norm == 0 else vector / norm)
        return np.vstack(rows)


class FlatEncoder:
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        rows = [np.array([1.0, 1.0, 1.0], dtype=np.float32) for _text in texts]
        return np.vstack(rows)


def test_knowledge_store_run_once_tracks_backlog_and_status(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("one.md", "two.md", "three.md"):
        (docs / name).write_text(f"Acme y Python en {name}", encoding="utf-8")

    store = KnowledgeStore(
        tmp_path / "knowledge.db",
        encoder=FakeEncoder(),
        default_roots=[str(docs)],
        auto_index_on_search=False,
        max_files_per_root=1,
        embedding_batch_size=1,
    )

    result = store.run_once([docs])
    status_after_first_run = store.status([str(docs)])
    flush_backlog = store.ingest_pending_batch([str(docs)], batch_size=5)
    status_after_flush = store.status([str(docs)])

    assert result.scanned_files == 3
    assert result.indexed_files == 1
    assert result.pending_files == 2
    assert result.processed_files == 1
    assert store.count() == 3
    assert status_after_first_run.discovered_files == 3
    assert status_after_first_run.indexed_files == 1
    assert status_after_first_run.pending_files == 2
    assert status_after_first_run.last_run is not None
    assert status_after_first_run.last_run.processed_files == 1
    assert flush_backlog.indexed_files == 2
    assert flush_backlog.pending_files == 0
    assert status_after_flush.pending_files == 0


def test_knowledge_store_search_reranks_lexically_and_returns_metadata(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "acme-roadmap.md").write_text("Resumen ejecutivo del trimestre", encoding="utf-8")
    (docs / "meeting-notes.md").write_text(
        "Notas varias con roadmap en un parrafo",
        encoding="utf-8",
    )

    store = KnowledgeStore(
        tmp_path / "knowledge.db",
        encoder=FlatEncoder(),
        default_roots=[str(docs)],
        auto_index_on_search=False,
        max_files_per_root=10,
    )

    store.run_once([docs])
    results = store.search("roadmap", limit=2, roots=[str(docs)])

    assert results[0].title == "acme-roadmap.md"
    assert results[0].relative_path == "acme-roadmap.md"
    assert results[0].suffix == ".md"
    assert results[0].file_size > 0
    assert results[0].modified_at
    assert results[0].indexed_at
    assert "roadmap" in results[0].matched_terms


def test_knowledge_store_search_vault_filters_markdown_and_handles_deleted_files(
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    docs.mkdir()
    vault.mkdir()
    todo = docs / "todo.txt"
    note = vault / "acme-vault.md"
    todo.write_text("Acme en texto plano", encoding="utf-8")
    note.write_text("Acme desde Obsidian con Python y estrategia.", encoding="utf-8")

    store = KnowledgeStore(
        tmp_path / "knowledge.db",
        encoder=FakeEncoder(),
        default_roots=[str(docs), str(vault)],
        vault_roots=[str(vault)],
        auto_index_on_search=False,
        max_files_per_root=20,
    )

    store.run_once([docs, vault])
    vault_results = store.search_vault("acme python", limit=5, roots=[str(vault)])
    note.unlink()
    rerun = store.run_once([vault])
    status = store.status([str(vault)])
    after_delete = store.search_vault("acme python", limit=5, roots=[str(vault)])

    assert len(vault_results) == 1
    assert vault_results[0].title == "acme-vault.md"
    assert rerun.deleted_files == 1
    assert status.deleted_files == 1
    assert after_delete == []


def test_knowledge_tools_expose_discover_ingest_and_status(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "alpha.md").write_text("Acme alpha", encoding="utf-8")
    (docs / "beta.md").write_text("Acme beta", encoding="utf-8")

    store = KnowledgeStore(
        tmp_path / "knowledge.db",
        encoder=FakeEncoder(),
        auto_index_on_search=False,
        max_files_per_root=1,
        embedding_batch_size=1,
    )
    tools = KnowledgeTools(store)

    discover = tools.knowledge_discover([str(docs)]).payload
    ingest = tools.knowledge_ingest_batch([str(docs)], batch_size=1).payload
    status = tools.knowledge_status([str(docs)]).payload
    search = tools.knowledge_search("acme", limit=5, roots=[str(docs)]).payload

    assert discover["scanned_files"] == 2
    assert discover["pending_files"] == 2
    assert ingest["processed_files"] == 1
    assert ingest["indexed_files"] == 1
    assert ingest["pending_files"] == 1
    assert status["indexed_files"] == 1
    assert status["pending_files"] == 1
    assert status["recent_runs"]
    assert search["status"]["indexed_files"] == 1
    assert len(search["results"]) == 1


def test_knowledge_store_uses_sqlite_wal_mode_for_persistent_db(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "knowledge.db", encoder=FakeEncoder())

    journal_mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    busy_timeout = store._conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) == 30000
