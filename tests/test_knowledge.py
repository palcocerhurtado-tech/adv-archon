from pathlib import Path

import numpy as np

from adv_archon.core.knowledge import KnowledgeStore


class FakeEncoder:
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            lowered = text.lower()
            vector = np.array(
                [
                    1.0 if "acme" in lowered else 0.0,
                    1.0 if "python" in lowered else 0.0,
                    float((len(lowered) % 5) + 1),
                ],
                dtype=np.float32,
            )
            norm = np.linalg.norm(vector)
            rows.append(vector if norm == 0 else vector / norm)
        return np.vstack(rows)


def test_knowledge_store_indexes_and_searches(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "acme-notes.md").write_text(
        "Acme quiere automatizar reporting con Python y agentes.",
        encoding="utf-8",
    )
    (docs / "personal.txt").write_text("Lista de la compra", encoding="utf-8")

    store = KnowledgeStore(
        tmp_path / "knowledge.db",
        encoder=FakeEncoder(),
        default_roots=[str(docs)],
        auto_index_on_search=False,
        max_files_per_root=20,
    )

    index_result = store.index_default_roots()
    results = store.search("acme python", limit=1)

    assert index_result.indexed_files >= 1
    assert results[0].title == "acme-notes.md"
    assert "Python" in results[0].excerpt


def test_knowledge_store_search_vault_filters_markdown_roots(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    docs.mkdir()
    vault.mkdir()
    (docs / "todo.txt").write_text("Acme en texto plano", encoding="utf-8")
    (vault / "acme-vault.md").write_text(
        "Acme desde Obsidian con Python y estrategia.",
        encoding="utf-8",
    )

    store = KnowledgeStore(
        tmp_path / "knowledge.db",
        encoder=FakeEncoder(),
        default_roots=[str(docs), str(vault)],
        vault_roots=[str(vault)],
        auto_index_on_search=False,
        max_files_per_root=20,
    )

    store.index_paths([docs, vault])
    results = store.search_vault("acme python", limit=5, roots=[str(vault)])

    assert len(results) == 1
    assert results[0].title == "acme-vault.md"
