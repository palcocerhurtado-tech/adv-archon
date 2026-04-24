from pathlib import Path

from adv_archon.core.benchmark import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkMetric,
    BenchmarkSummary,
)
from adv_archon.main import _load_benchmark_cases, _render_benchmark_summary


def test_load_benchmark_cases_expands_placeholders(tmp_path: Path) -> None:
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(
        """
        [
          {
            "case_id": "readme",
            "prompt": "resume {cwd}/README.md desde {home}",
            "expected_facts": ["adv archon"],
            "require_local_knowledge": true,
            "require_confidence_block": true,
            "tags": ["docs"]
          }
        ]
        """,
        encoding="utf-8",
    )

    cases = _load_benchmark_cases(
        cases_file,
        cwd=Path("/tmp/project"),
        home=Path("/Users/pabloalcocer"),
        max_cases=5,
    )

    assert len(cases) == 1
    assert cases[0].case_id == "readme"
    assert cases[0].prompt == "resume /tmp/project/README.md desde /Users/pabloalcocer"
    assert cases[0].expected_facts == ("adv archon",)
    assert cases[0].require_local_knowledge is True
    assert cases[0].require_confidence_block is True


def test_render_benchmark_summary_lists_failures() -> None:
    metric = BenchmarkMetric(name="grounding", score=0.4, passed=False, details=())
    summary = BenchmarkSummary(
        results=(
            BenchmarkCaseResult(
                case=BenchmarkCase(case_id="ok", prompt="hola"),
                response_text="hola",
                grounding=BenchmarkMetric(name="grounding", score=1.0, passed=True),
                local_knowledge=BenchmarkMetric(name="local_knowledge", score=1.0, passed=True),
                confidence_citations=BenchmarkMetric(
                    name="confidence_citations",
                    score=1.0,
                    passed=True,
                ),
                overall_score=1.0,
                passed=True,
                duration_seconds=0.1,
                confidence_block_present=True,
            ),
            BenchmarkCaseResult(
                case=BenchmarkCase(case_id="bad", prompt="adios"),
                response_text="adios",
                grounding=metric,
                local_knowledge=metric,
                confidence_citations=metric,
                overall_score=0.4,
                passed=False,
                duration_seconds=0.2,
                confidence_block_present=False,
                error="tool timeout",
            ),
        ),
        total_cases=2,
        passed_cases=1,
        failed_cases=1,
        pass_rate=0.5,
        average_score=0.7,
        average_grounding=0.7,
        average_local_knowledge=0.7,
        average_confidence_citations=0.7,
        total_duration_seconds=0.3,
        average_duration_seconds=0.15,
    )

    rendered = _render_benchmark_summary(
        summary,
        run_id=7,
        cases_path=Path("/tmp/cases.json"),
    )

    assert "run #7" in rendered
    assert "Casos a revisar:" in rendered
    assert "bad" in rendered
    assert "tool timeout" in rendered
