from __future__ import annotations

import json
from pathlib import Path

from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.feedback_store import FeedbackStore
from adv_archon.core.training_lab import (
    build_training_lab_status,
    export_feedback_dataset,
    generate_synthetic_dataset,
    render_training_lab_status,
)


class _FakeClient:
    def complete(self, *_args, **_kwargs):
        return (
            json.dumps(
                {
                    "verdict": "VIABLE",
                    "summary": "Caso sintético viable con comprobaciones pendientes.",
                    "annotations": [],
                    "next_steps": ["Confirmar ordenanza municipal."],
                    "confidence": "media",
                },
                ensure_ascii=False,
            ),
            object(),
        )


def _seed_feedback(db_path: Path) -> None:
    exp_store = ExpedienteStore(db_path.parent / "expedientes.db")
    exp = exp_store.create(
        title="Cambio de uso",
        address="Calle Mayor 1",
        municipality="Madrid",
        province="Madrid",
    )
    FeedbackStore(db_path).add_example(
        exp,
        {"summary": "Informe apto"},
        {"score": 88, "flags": [], "verdict": "APTO"},
    )


def test_training_lab_status_reports_feedback_and_templates(tmp_path: Path) -> None:
    feedback_db = tmp_path / "feedback.db"
    _seed_feedback(feedback_db)

    status = build_training_lab_status(
        feedback_db=feedback_db,
        templates_path=Path("data/case_templates.json"),
        synthetic_dataset_path=tmp_path / "synthetic.jsonl",
    )
    rendered = render_training_lab_status(status)

    assert status.feedback.total == 1
    assert status.feedback.approved == 1
    assert status.templates_count == 20
    assert status.fine_tune_ready is True
    assert "Training Lab ADV ARCHON" in rendered


def test_training_lab_exports_feedback_dataset(tmp_path: Path) -> None:
    feedback_db = tmp_path / "feedback.db"
    _seed_feedback(feedback_db)

    result = export_feedback_dataset(
        feedback_db=feedback_db,
        output_path=tmp_path / "real.jsonl",
    )

    assert result.examples_exported == 1
    assert "Informe apto" in result.output_path.read_text(encoding="utf-8")


def test_training_lab_generates_synthetic_dataset(tmp_path: Path) -> None:
    result = generate_synthetic_dataset(
        templates_path=Path("data/case_templates.json"),
        output_path=tmp_path / "synthetic.jsonl",
        client=_FakeClient(),
        count=2,
        seed=3,
    )

    assert result.generated == 2
    assert result.output_path.exists()
    assert len(result.output_path.read_text(encoding="utf-8").splitlines()) == 2
