"""Tests for core/episodic_memory.py."""
from __future__ import annotations

from pathlib import Path

from adv_archon.core.episodic_memory import EpisodicMemory


def test_store_and_list_recent(tmp_path: Path) -> None:
    mem = EpisodicMemory(tmp_path / "ep.db")
    mem.store(
        municipality="Madrid",
        case_type="cambio_uso",
        verdict="VIABLE",
        params={"edificabilidad_m2m2": 1.5},
        summary="Cambio de uso en zona residencial.",
    )
    recent = mem.list_recent()
    assert len(recent) == 1
    ep = recent[0]
    assert ep.municipality == "Madrid"
    assert ep.verdict == "VIABLE"
    assert ep.params["edificabilidad_m2m2"] == 1.5


def test_store_multiple_list_returns_most_recent_first(tmp_path: Path) -> None:
    mem = EpisodicMemory(tmp_path / "ep.db")
    for i in range(3):
        mem.store(
            municipality=f"Ciudad{i}",
            case_type="obra_nueva",
            verdict="CONDICIONADO",
            params={},
            summary=f"Caso {i}",
        )
    recent = mem.list_recent(limit=5)
    assert len(recent) == 3
    assert recent[0].municipality == "Ciudad2"


def test_search_similar_returns_closest_embedding(tmp_path: Path) -> None:
    mem = EpisodicMemory(tmp_path / "ep.db")
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.0, 1.0, 0.0]
    mem.store(
        municipality="Sevilla",
        case_type="obra_nueva",
        verdict="VIABLE",
        params={},
        summary="Caso A",
        embedding=vec_a,
    )
    mem.store(
        municipality="Sevilla",
        case_type="obra_nueva",
        verdict="REVISAR",
        params={},
        summary="Caso B",
        embedding=vec_b,
    )
    results = mem.search_similar([0.9, 0.1, 0.0], limit=1)
    assert len(results) == 1
    assert results[0].verdict == "VIABLE"


def test_search_similar_with_no_embeddings_returns_empty(tmp_path: Path) -> None:
    mem = EpisodicMemory(tmp_path / "ep.db")
    mem.store(municipality="X", case_type="y", verdict="z", params={}, summary="s")
    results = mem.search_similar([1.0, 0.0])
    assert results == []


def test_search_similar_filters_by_municipality(tmp_path: Path) -> None:
    mem = EpisodicMemory(tmp_path / "ep.db")
    vec = [1.0, 0.0]
    mem.store(
        municipality="Madrid", case_type="t", verdict="A", params={}, summary="m", embedding=vec
    )
    mem.store(
        municipality="Barcelona", case_type="t", verdict="B", params={}, summary="b", embedding=vec
    )
    results = mem.search_similar([1.0, 0.0], municipality="Madrid")
    assert all(ep.municipality == "Madrid" for ep in results)


def test_episodic_memory_persists_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "ep.db"
    mem1 = EpisodicMemory(db)
    mem1.store(municipality="Toledo", case_type="x", verdict="OK", params={}, summary="s")

    mem2 = EpisodicMemory(db)
    recent = mem2.list_recent()
    assert len(recent) == 1
    assert recent[0].municipality == "Toledo"
