from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from adv_archon.core.knowledge import KnowledgeStore
from adv_archon.core.memory import MemoryStore


class FakeEncoder:
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        rows: list[np.ndarray] = []
        for text in texts:
            vector = np.array(
                [
                    float(len(text) or 1),
                    1.0 if "pdf" in text.lower() else 0.0,
                    1.0,
                ],
                dtype=np.float32,
            )
            norm = np.linalg.norm(vector)
            rows.append(vector if norm == 0 else vector / norm)
        return np.vstack(rows)


def test_memory_store_can_be_used_from_background_thread(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db", encoder=FakeEncoder())
    store.remember("Resumen del PDF de ACME", ["pdf"])
    errors: list[Exception] = []
    results: list[int] = []

    def worker() -> None:
        try:
            results.append(store.count())
        except Exception as exc:  # pragma: no cover - regression guard
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert errors == []
    assert results == [1]


def test_knowledge_store_can_search_from_background_thread(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "acme.pdf.txt").write_text(
        "Resumen del PDF de ACME con entregables y alcance.",
        encoding="utf-8",
    )
    store = KnowledgeStore(
        tmp_path / "knowledge.db",
        encoder=FakeEncoder(),
        default_roots=[str(docs_dir)],
        auto_index_on_search=False,
        max_files_per_root=10,
    )
    store.run_once([docs_dir])
    errors: list[Exception] = []
    results: list[int] = []

    def worker() -> None:
        try:
            search = store.search_details("resume este pdf de acme", limit=3)
            results.append(len(search.records))
        except Exception as exc:  # pragma: no cover - regression guard
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert errors == []
    assert results == [1]
