from pathlib import Path

import numpy as np
import pytest

from adv_archon.core.memory import MemoryStore


class FakeEncoder:
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            lowered = text.lower()
            vector = np.array(
                [
                    1.0 if "python" in lowered else 0.0,
                    1.0 if "espanol" in lowered or "spanish" in lowered else 0.0,
                    float(len(lowered) % 7 + 1),
                ],
                dtype=np.float32,
            )
            norm = np.linalg.norm(vector)
            rows.append(vector if norm == 0 else vector / norm)
        return np.vstack(rows)


def test_memory_store_remember_recall_and_forget(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db", encoder=FakeEncoder())

    first = store.remember("Pablo prefiere trabajar en Python", ["language", "code"])
    store.remember("Responder por defecto en espanol", ["language"])

    recalled = store.recall("python", limit=1)

    assert recalled[0].id == first.id
    assert recalled[0].content == "Pablo prefiere trabajar en Python"

    deleted = store.forget_by_ids([first.id])

    assert deleted == 1
    assert store.get_by_id(first.id) is None


def test_memory_store_incognito_is_read_only(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db", persist=False, encoder=FakeEncoder())

    with pytest.raises(PermissionError):
        store.remember("No persistir esto")
