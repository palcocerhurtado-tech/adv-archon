from datetime import date
from pathlib import Path

import numpy as np

from adv_archon.core.daily import build_daily_report
from adv_archon.core.logging import AppLogger
from adv_archon.core.memory import MemoryStore


class FakeEncoder:
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            lowered = text.lower()
            vector = np.array(
                [
                    1.0 if "todo" in lowered else 0.0,
                    1.0 if "note" in lowered or "nota" in lowered else 0.0,
                    float(len(lowered) % 5 + 1),
                ],
                dtype=np.float32,
            )
            norm = np.linalg.norm(vector)
            rows.append(vector if norm == 0 else vector / norm)
        return np.vstack(rows)


def test_build_daily_report_summarizes_logs_and_pending_notes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(
        "[project]\nname = 'daily-demo'\n",
        encoding="utf-8",
    )

    logs_dir = tmp_path / "logs"
    logger = AppLogger(logs_dir, session_id="session-1", persist=True)
    logger.log("session_started", cwd=str(project_root))
    logger.log(
        "llm_call",
        provider="gemini",
        phase="assistant",
        total_tokens=42,
        estimated_cost_usd=0.0001,
    )
    logger.log("shell_exec", command="git status")

    memory_store = MemoryStore(
        tmp_path / "memory.db",
        encoder=FakeEncoder(),
    )
    memory_store.remember("TODO: revisar propuesta ACME", ["todo", "note"])

    report = build_daily_report(
        project_root=project_root,
        logs_dir=logs_dir,
        memory_store=memory_store,
        target_day=date.today(),
    )

    rendered = report.render()

    assert "daily-demo" in rendered
    assert "llamadas LLM: 1" in rendered
    assert "comandos shell: 1" in rendered
    assert "TODO: revisar propuesta ACME" in rendered
