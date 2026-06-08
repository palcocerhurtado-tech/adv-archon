"""Tests for core/param_extractor.py and core/pgou_reranker.py."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from adv_archon.core.param_extractor import ParamExtractor, _empty_params, _parse_json_block
from adv_archon.core.pgou_reranker import PGOUReranker
from adv_archon.core.pgou_store import PGOUChunk

# ── ParamExtractor ────────────────────────────────────────────────────────────


def _mock_llm(response: str) -> MagicMock:
    llm = MagicMock()
    llm.complete_text.return_value = response
    return llm


def test_param_extractor_returns_empty_on_no_chunks() -> None:
    extractor = ParamExtractor(_mock_llm(""))
    result = extractor.extract([])
    assert result == _empty_params()


def test_param_extractor_parses_valid_json() -> None:
    payload = {
        "uso_principal": "Residencial",
        "clasificacion": "suelo urbano consolidado",
        "calificacion": "Z-1",
        "edificabilidad_m2m2": 1.5,
        "ocupacion_pct": 60.0,
        "altura_maxima_m": 10.0,
        "num_plantas": 3,
        "retranqueos_m": "5 m frontal",
        "usos_permitidos": ["vivienda", "comercial"],
        "usos_prohibidos": ["industrial"],
        "condiciones_especiales": "",
        "articulos_referencia": ["Art. 23"],
        "confianza": "alta",
    }
    extractor = ParamExtractor(_mock_llm(json.dumps(payload)))
    result = extractor.extract(["fragmento de PGOU"])
    assert result["uso_principal"] == "Residencial"
    assert result["edificabilidad_m2m2"] == 1.5
    assert result["usos_permitidos"] == ["vivienda", "comercial"]
    assert result["confianza"] == "alta"


def test_param_extractor_returns_empty_on_llm_error() -> None:
    llm = MagicMock()
    llm.complete_text.side_effect = RuntimeError("LLM unavailable")
    extractor = ParamExtractor(llm)
    result = extractor.extract(["some text"])
    assert result == _empty_params()


def test_param_extractor_returns_empty_on_invalid_json() -> None:
    extractor = ParamExtractor(_mock_llm("not json at all"))
    result = extractor.extract(["some text"])
    assert result == _empty_params()


def test_parse_json_block_extracts_embedded_json() -> None:
    text = 'Here is the result: {"key": "value", "n": 42} — done.'
    parsed = _parse_json_block(text)
    assert parsed == {"key": "value", "n": 42}


def test_parse_json_block_returns_empty_on_no_json() -> None:
    assert _parse_json_block("no json here") == {}


# ── PGOUReranker ──────────────────────────────────────────────────────────────


def _make_chunk(text: str, idx: int = 0) -> PGOUChunk:
    return PGOUChunk(
        id=idx,
        municipality="Madrid",
        article_ref=f"Art.{idx}",
        title=f"Chunk {idx}",
        text=text,
        chunk_index=idx,
        source="test",
    )


def test_reranker_returns_empty_on_no_chunks() -> None:
    reranker = PGOUReranker(_mock_llm("5"))
    assert reranker.rerank([], case_description="test") == []


def test_reranker_sorts_by_score_descending() -> None:
    scores = iter([8.0, 3.0, 6.0])

    llm = MagicMock()
    llm.complete_text.side_effect = lambda _: str(next(scores))

    chunks = [_make_chunk(f"text {i}", i) for i in range(3)]
    reranker = PGOUReranker(llm)
    result = reranker.rerank(chunks, case_description="cambio de uso")
    assert result[0].id == 0  # score 8 → first
    assert result[1].id == 2  # score 6 → second
    assert result[2].id == 1  # score 3 → third


def test_reranker_respects_top_k() -> None:
    llm = MagicMock()
    llm.complete_text.return_value = "7"
    chunks = [_make_chunk(f"t{i}", i) for i in range(10)]
    reranker = PGOUReranker(llm)
    result = reranker.rerank(chunks, case_description="x", top_k=3)
    assert len(result) == 3


def test_reranker_falls_back_to_5_on_llm_error() -> None:
    llm = MagicMock()
    llm.complete_text.side_effect = RuntimeError("fail")
    chunks = [_make_chunk("text", 0)]
    reranker = PGOUReranker(llm)
    result = reranker.rerank(chunks, case_description="x")
    assert len(result) == 1
