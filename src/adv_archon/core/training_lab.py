from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adv_archon.core.feedback_store import ExportResult, FeedbackStats, FeedbackStore
from adv_archon.core.training_data import (
    LocalChatClient,
    generate_training_examples,
    load_case_templates,
    write_jsonl,
)


@dataclass(frozen=True, slots=True)
class TrainingLabStatus:
    feedback: FeedbackStats
    templates_count: int
    synthetic_dataset_path: Path
    synthetic_examples: int

    @property
    def fine_tune_ready(self) -> bool:
        return self.feedback.approved > 0 or self.synthetic_examples > 0

    @property
    def readiness_label(self) -> str:
        if self.feedback.approved >= 50:
            return "Listo para primer experimento LoRA"
        if self.feedback.approved > 0 or self.synthetic_examples > 0:
            return "Dataset inicial disponible"
        return "Pendiente de ejemplos"


@dataclass(frozen=True, slots=True)
class SyntheticGenerationResult:
    output_path: Path
    requested: int
    generated: int


def build_training_lab_status(
    *,
    feedback_db: Path,
    templates_path: Path,
    synthetic_dataset_path: Path,
) -> TrainingLabStatus:
    stats = FeedbackStore(feedback_db).stats()
    templates_count = len(load_case_templates(templates_path)) if templates_path.exists() else 0
    synthetic_examples = _count_jsonl(synthetic_dataset_path)
    return TrainingLabStatus(
        feedback=stats,
        templates_count=templates_count,
        synthetic_dataset_path=synthetic_dataset_path,
        synthetic_examples=synthetic_examples,
    )


def export_feedback_dataset(*, feedback_db: Path, output_path: Path) -> ExportResult:
    return FeedbackStore(feedback_db).export_alpaca(output_path)


def generate_synthetic_dataset(
    *,
    templates_path: Path,
    output_path: Path,
    client: LocalChatClient,
    count: int,
    seed: int = 42,
) -> SyntheticGenerationResult:
    templates = load_case_templates(templates_path)
    examples = generate_training_examples(
        templates=templates,
        client=client,
        count=count,
        seed=seed,
    )
    write_jsonl(examples, output_path)
    return SyntheticGenerationResult(
        output_path=output_path,
        requested=count,
        generated=len(examples),
    )


def render_training_lab_status(status: TrainingLabStatus) -> str:
    average = (
        f"{status.feedback.average_score:.1f}/100"
        if status.feedback.average_score is not None
        else "sin datos"
    )
    return "\n".join(
        [
            "Training Lab ADV ARCHON",
            f"- ejemplos reales guardados: {status.feedback.total}",
            f"- ejemplos aprobados por juez local: {status.feedback.approved}",
            f"- ejemplos a revisar: {status.feedback.review}",
            f"- score medio del juez: {average}",
            f"- plantillas sintéticas: {status.templates_count}",
            f"- sintéticos generados: {status.synthetic_examples}",
            f"- dataset sintético: {status.synthetic_dataset_path}",
            f"- estado: {status.readiness_label}",
        ]
    )


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def default_templates_path(project_root: Path) -> Path:
    return project_root / "data" / "case_templates.json"


def default_synthetic_dataset_path(root: Path) -> Path:
    return root / "compliance_synthetic_dataset.jsonl"


def default_export_path() -> Path:
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return Path.home() / "Desktop" / f"adv_archon_training_feedback_{stamp}.jsonl"


def build_ollama_client(config: Any) -> LocalChatClient:
    from adv_archon.integrations.ollama import OllamaClient

    return OllamaClient(
        base_url=config.llm.ollama_base_url,
        model=config.llm.ollama_model,
        temperature=0.2,
        timeout=float(config.llm.ollama_timeout_seconds),
        num_ctx=config.llm.ollama_num_ctx,
        keep_alive=config.llm.ollama_keep_alive,
    )


__all__ = [
    "SyntheticGenerationResult",
    "TrainingLabStatus",
    "build_ollama_client",
    "build_training_lab_status",
    "default_export_path",
    "default_synthetic_dataset_path",
    "default_templates_path",
    "export_feedback_dataset",
    "generate_synthetic_dataset",
    "render_training_lab_status",
]
