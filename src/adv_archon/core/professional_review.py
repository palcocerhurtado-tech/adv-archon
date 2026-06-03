from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from adv_archon.core.agent_plan import (
    AGENT_STEP_REVIEW_LABELS,
    AGENT_STEP_STATUS_LABELS,
    build_expediente_agent_plan,
)
from adv_archon.core.expediente_quality import evaluate_expediente_quality

REVIEW_FILTER_LABELS = {
    "all": "Todos",
    "pending": "Pendientes",
    "validated": "Validados",
    "warnings": "Advertencias",
    "included": "Incluidos",
    "excluded": "Excluidos",
    "repeat": "Repetir",
    "needs_review": "Necesitan revisión",
}


@dataclass(frozen=True, slots=True)
class ProfessionalReviewStep:
    expediente_id: str
    expediente_title: str
    municipality: str
    risk_level: str
    risk_label: str
    step_code: str
    step_title: str
    step_status: str
    step_status_label: str
    review_status: str
    review_label: str
    include_in_report: bool
    official_data: str
    archon_inference: str
    confidence: str
    recommended_action: str
    review_note: str = ""

    @property
    def needs_architect(self) -> bool:
        return self.review_status == "pending" and self.step_status in {
            "blocked",
            "needs_review",
            "pending",
        }

    @property
    def filter_keys(self) -> set[str]:
        keys = {"all", self.review_status}
        if self.review_status == "accepted_warning":
            keys.add("warnings")
        if self.review_status == "requested_repeat":
            keys.add("repeat")
        if self.step_status in {"blocked", "needs_review"}:
            keys.add("needs_review")
        if not self.include_in_report:
            keys.add("excluded")
        return keys

    def as_payload(self) -> dict[str, Any]:
        return {
            "expediente_id": self.expediente_id,
            "expediente_title": self.expediente_title,
            "municipality": self.municipality,
            "risk_level": self.risk_level,
            "risk_label": self.risk_label,
            "step_code": self.step_code,
            "step_title": self.step_title,
            "step_status": self.step_status,
            "step_status_label": self.step_status_label,
            "review_status": self.review_status,
            "review_label": self.review_label,
            "include_in_report": self.include_in_report,
            "official_data": self.official_data,
            "archon_inference": self.archon_inference,
            "confidence": self.confidence,
            "recommended_action": self.recommended_action,
            "review_note": self.review_note,
            "needs_architect": self.needs_architect,
        }


@dataclass(frozen=True, slots=True)
class ProfessionalReviewSummary:
    expediente_count: int
    total_steps: int
    pending: int
    validated: int
    accepted_warnings: int
    included: int
    excluded: int
    repeat_requested: int
    needs_review: int

    def count_for_filter(self, filter_key: str) -> int:
        return {
            "all": self.total_steps,
            "pending": self.pending,
            "validated": self.validated,
            "warnings": self.accepted_warnings,
            "included": self.included,
            "excluded": self.excluded,
            "repeat": self.repeat_requested,
            "needs_review": self.needs_review,
        }.get(filter_key, self.total_steps)

    def as_payload(self) -> dict[str, int]:
        return {
            "expediente_count": self.expediente_count,
            "total_steps": self.total_steps,
            "pending": self.pending,
            "validated": self.validated,
            "accepted_warnings": self.accepted_warnings,
            "included": self.included,
            "excluded": self.excluded,
            "repeat_requested": self.repeat_requested,
            "needs_review": self.needs_review,
        }


@dataclass(frozen=True, slots=True)
class ProfessionalReviewDashboard:
    summary: ProfessionalReviewSummary
    steps: tuple[ProfessionalReviewStep, ...]

    def filtered(self, filter_key: str) -> tuple[ProfessionalReviewStep, ...]:
        key = normalize_review_filter(filter_key)
        if key == "all":
            return self.steps
        return tuple(step for step in self.steps if key in step.filter_keys)

    def as_payload(self) -> dict[str, Any]:
        return {
            "summary": self.summary.as_payload(),
            "steps": [step.as_payload() for step in self.steps],
        }


def normalize_review_filter(filter_key: str | None) -> str:
    key = (filter_key or "all").strip().lower()
    return key if key in REVIEW_FILTER_LABELS else "all"


def build_professional_review_dashboard(
    expedientes: Sequence[Any] | Iterable[Any],
) -> ProfessionalReviewDashboard:
    steps: list[ProfessionalReviewStep] = []
    expediente_count = 0
    for exp in expedientes:
        expediente_count += 1
        quality = evaluate_expediente_quality(exp)
        plan = build_expediente_agent_plan(exp)
        expediente_title = str(getattr(exp, "title", "") or "Expediente sin título")
        municipality = str(getattr(exp, "municipality", "") or "").strip()
        for step in plan.steps:
            review_status = step.review_status or "pending"
            steps.append(
                ProfessionalReviewStep(
                    expediente_id=str(getattr(exp, "id", "")),
                    expediente_title=expediente_title,
                    municipality=municipality or "Municipio pendiente",
                    risk_level=quality.risk_level,
                    risk_label=quality.risk_label,
                    step_code=step.code,
                    step_title=step.title,
                    step_status=step.status,
                    step_status_label=AGENT_STEP_STATUS_LABELS.get(
                        step.status,
                        step.status,
                    ),
                    review_status=review_status,
                    review_label=step.review_label
                    or AGENT_STEP_REVIEW_LABELS.get(review_status, review_status),
                    include_in_report=step.include_in_report,
                    official_data=step.official_data,
                    archon_inference=step.archon_inference,
                    confidence=step.confidence,
                    recommended_action=step.recommended_action,
                    review_note=step.review_note,
                )
            )
    ordered_steps = tuple(sorted(steps, key=_review_sort_key))
    return ProfessionalReviewDashboard(
        summary=_build_summary(expediente_count, ordered_steps),
        steps=ordered_steps,
    )


def _build_summary(
    expediente_count: int,
    steps: tuple[ProfessionalReviewStep, ...],
) -> ProfessionalReviewSummary:
    return ProfessionalReviewSummary(
        expediente_count=expediente_count,
        total_steps=len(steps),
        pending=sum(1 for step in steps if step.review_status == "pending"),
        validated=sum(1 for step in steps if step.review_status == "validated"),
        accepted_warnings=sum(
            1 for step in steps if step.review_status == "accepted_warning"
        ),
        included=sum(1 for step in steps if step.review_status == "included"),
        excluded=sum(1 for step in steps if not step.include_in_report),
        repeat_requested=sum(
            1 for step in steps if step.review_status == "requested_repeat"
        ),
        needs_review=sum(1 for step in steps if step.needs_architect),
    )


def _review_sort_key(step: ProfessionalReviewStep) -> tuple[int, int, str, str]:
    review_rank = {
        "requested_repeat": 0,
        "pending": 1,
        "accepted_warning": 2,
        "validated": 3,
        "included": 4,
        "excluded": 5,
    }.get(step.review_status, 6)
    status_rank = {
        "blocked": 0,
        "needs_review": 1,
        "pending": 2,
        "in_progress": 3,
        "completed": 4,
    }.get(step.step_status, 5)
    return (review_rank, status_rank, step.expediente_title, step.step_code)
