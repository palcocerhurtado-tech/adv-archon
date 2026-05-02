from pathlib import Path

import numpy as np
import pytest

from adv_archon.core.memory import MemoryStore
from adv_archon.tools.memory_tools import MemoryTools


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

    first = store.remember(
        "Pablo prefiere trabajar en Python",
        ["language", "code"],
        memory_type="preference",
        namespace="coding",
    )
    store.remember("Responder por defecto en espanol", ["language"])

    recalled = store.recall("python", limit=1)

    assert recalled[0].id == first.id
    assert recalled[0].content == "Pablo prefiere trabajar en Python"
    assert recalled[0].memory_type == "preference"
    assert recalled[0].namespace == "coding"

    deleted = store.forget_by_ids([first.id])

    assert deleted == 1
    assert store.get_by_id(first.id) is None


def test_memory_store_incognito_is_read_only(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db", persist=False, encoder=FakeEncoder())

    with pytest.raises(PermissionError):
        store.remember("No persistir esto")


def test_memory_store_can_filter_by_namespace(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db", encoder=FakeEncoder())

    store.remember("Cliente Acme prefiere entregas semanales", namespace="clients")
    store.remember("Pablo trabaja en Python", namespace="coding")

    recalled = store.recall("python", limit=5, namespace="coding")

    assert len(recalled) == 1
    assert recalled[0].namespace == "coding"


def test_memory_store_supports_categories_importance_and_listing(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db", encoder=FakeEncoder())

    low = store.remember(
        "Pablo explora simbolismo general",
        ["study"],
        category="interests",
        importance=2,
    )
    high = store.remember(
        "Proyecto Archon debe priorizar memoria visible",
        ["roadmap", "important"],
        category="projects",
        importance=5,
        namespace="work",
    )

    listed = store.list_memories(limit=5)
    project_only = store.list_memories(category="projects", limit=5)
    recalled = store.recall("archon", limit=5, min_importance=4)

    assert listed[0].id == high.id
    assert listed[1].id == low.id
    assert project_only[0].category == "projects"
    assert recalled[0].id == high.id
    assert recalled[0].importance == 5


def test_memory_store_update_memory_can_edit_priority_and_category(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db", encoder=FakeEncoder())

    record = store.remember(
        "Pablo estudia grimorios",
        ["study"],
        category="interests",
        importance=2,
    )

    updated = store.update_memory(
        record.id,
        content="Pablo estudia grimorios y cabala",
        tags=["study", "cabala"],
        category="interests",
        importance=5,
        metadata={"note": "alta prioridad"},
    )

    assert updated.content == "Pablo estudia grimorios y cabala"
    assert updated.tags == ["cabala", "study"]
    assert updated.category == "interests"
    assert updated.importance == 5
    assert updated.metadata["note"] == "alta prioridad"


def test_memory_tools_can_list_update_and_forget(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db", encoder=FakeEncoder())
    tools = MemoryTools(store)

    first = tools.remember(
        "Pablo prefiere respuestas directas",
        tags=["style"],
        memory_type="preference",
        category="preferences",
        importance=4,
    ).payload["record"]
    tools.remember(
        "Proyecto ADV ARCHON sigue activo",
        tags=["project"],
        category="projects",
        importance=5,
    )

    listed = tools.list_memories(category="preferences").payload["results"]
    updated = tools.update_memory(first["id"], importance=5).payload["record"]
    forgotten = tools.forget_memories(query="ADV ARCHON").payload

    assert listed[0]["category"] == "preferences"
    assert updated["importance"] == 5
    assert forgotten["deleted"] == 1
