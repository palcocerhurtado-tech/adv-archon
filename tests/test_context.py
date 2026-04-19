from pathlib import Path

from adv_archon.core.context import capture_runtime_context


def test_capture_runtime_context_detects_markers(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo-project'\n",
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()

    context = capture_runtime_context(tmp_path)

    assert context.working_set.project_name == "demo-project"
    assert "README.md" in context.working_set.markers
    assert "pyproject.toml" in context.working_set.markers
    assert "src/" in context.working_set.top_entries

