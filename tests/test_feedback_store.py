from __future__ import annotations

import json
from pathlib import Path

from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.feedback_store import FeedbackStore


def _make_exp(tmp_path: Path):
    store = ExpedienteStore(tmp_path / "expedientes.db")
    exp = store.create(
        title="Cambio de uso",
        address="Calle Mayor 1, Madrid",
        municipality="Madrid",
        province="Madrid",
        cadastral_ref="7537903VK4873N0001OU",
        case_type="cambio_uso_vivienda",
    )
    exp.plan_path = "/tmp/plano.pdf"
    exp.site_context = json.dumps(
        {
            "cadastral_ref": exp.cadastral_ref,
            "legal_checks": [{"title": "PGOU municipal", "status": "ready"}],
        },
        ensure_ascii=False,
    )
    return exp


def test_add_example_exports_approved_alpaca_dataset(tmp_path: Path) -> None:
    exp = _make_exp(tmp_path)
    store = FeedbackStore(tmp_path / "feedback.db")
    analysis = {
        "verdict": "CONDICIONADO",
        "summary": "Cambio de uso condicionado a confirmar ordenanza.",
        "next_steps": ["Confirmar habitabilidad y uso residencial."],
    }

    example_id = store.add_example(
        expediente=exp,
        analysis=analysis,
        judge_result={"score": 84, "flags": [], "verdict": "APTO"},
    )
    result = store.export_alpaca(tmp_path / "dataset.jsonl")

    assert example_id > 0
    assert result.examples_exported == 1
    line = result.output_path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["instruction"] == "Analiza el cumplimiento urbanístico:"
    assert "MUNICIPIO: Madrid" in payload["input"]
    assert "Cambio de uso" in payload["input"]
    assert "CONDICIONADO" in payload["output"]


def test_low_score_example_is_stored_but_not_exported(tmp_path: Path) -> None:
    exp = _make_exp(tmp_path)
    store = FeedbackStore(tmp_path / "feedback.db")

    store.add_example(
        expediente=exp,
        analysis="Análisis débil",
        judge_result={"score": 42, "flags": ["Falta normativa"], "verdict": "REVISAR"},
    )
    result = store.export_alpaca(tmp_path / "dataset.jsonl")

    assert store.count() == 1
    assert store.count(approved_only=True) == 0
    assert result.examples_exported == 0
    assert result.output_path.read_text(encoding="utf-8") == ""


def test_add_from_expediente_reads_quality_from_analysis_result(tmp_path: Path) -> None:
    exp = _make_exp(tmp_path)
    exp.analysis_result = json.dumps(
        {
            "summary": "Informe claro.",
            "quality": {"score": 91, "flags": [], "verdict": "APTO"},
        },
        ensure_ascii=False,
    )
    store = FeedbackStore(tmp_path / "feedback.db")

    first_id = store.add_from_expediente(exp)
    second_id = store.add_from_expediente(exp)

    assert first_id == second_id
    assert store.count() == 1
    assert store.count(approved_only=True) == 1
