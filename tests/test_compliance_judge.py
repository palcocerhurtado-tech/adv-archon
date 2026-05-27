from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from adv_archon.core.compliance_judge import ComplianceJudge


@dataclass
class _FakeLLM:
    text: str

    def complete(self, *_args, **_kwargs) -> SimpleNamespace:
        return SimpleNamespace(text=self.text)


def test_complete_returns_parsed_quality_result() -> None:
    judge = ComplianceJudge(
        _FakeLLM(
            """
            {"score": 82, "breakdown": {"precision": 20, "completeness": 21,
            "structure": 20, "actionability": 21}, "flags": ["ok"],
            "verdict": "APTO"}
            """
        )
    )

    result = judge.evaluate("Madrid", "Plano resumido", "Análisis generado")

    assert result["score"] == 82
    assert result["breakdown"]["precision"] == 20
    assert result["flags"] == ["ok"]
    assert result["verdict"] == "APTO"


def test_json_inside_text_is_accepted() -> None:
    judge = ComplianceJudge(
        _FakeLLM('Respuesta: {"score": 55, "breakdown": {}, "flags": [], "verdict": "REVISAR"}')
    )

    result = judge.evaluate("Zaragoza", "Plano", "Análisis")

    assert result["score"] == 55
    assert result["verdict"] == "REVISAR"


def test_broken_json_returns_pending_review_result() -> None:
    judge = ComplianceJudge(_FakeLLM("no es json"))

    result = judge.evaluate("Madrid", "Plano", "Análisis")

    assert result["score"] is None
    assert result["verdict"] == "REVISAR"
    assert result["flags"]


def test_is_reliable_uses_threshold() -> None:
    judge = ComplianceJudge(_FakeLLM("{}"))

    assert judge.is_reliable({"score": 70}, threshold=60) is True
    assert judge.is_reliable({"score": 55}, threshold=60) is False
    assert judge.is_reliable({"score": None}, threshold=60) is False
