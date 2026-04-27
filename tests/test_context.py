import subprocess
from pathlib import Path

from adv_archon.core.context import _capture_git_context, _run_git, capture_runtime_context


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


def test_run_git_preserves_significant_trailing_spaces(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["git"],
            returncode=0,
            stdout="/tmp/ADV ARCHON \n",
            stderr="",
        )

    monkeypatch.setattr("adv_archon.core.context.subprocess.run", fake_run)

    result = _run_git(tmp_path, "rev-parse", "--show-toplevel")

    assert result == "/tmp/ADV ARCHON "


def test_capture_git_context_preserves_repo_root_with_trailing_space(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo "
    repo.mkdir()
    answers = {
        ("rev-parse", "--show-toplevel"): f"{repo}\n",
        ("branch", "--show-current"): "main\n",
        ("status", "--porcelain"): " M fichero con espacio \n",
    }

    def fake_run(args, capture_output, check, text):  # type: ignore[no-untyped-def]
        key = tuple(args[3:])
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=answers.get(key, ""),
            stderr="",
        )

    monkeypatch.setattr("adv_archon.core.context.subprocess.run", fake_run)

    context = _capture_git_context(repo)

    assert context.repo_root == repo.resolve()
    assert context.branch == "main"
    assert context.changed_paths == ["fichero con espacio "]
