from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adv_archon.tools.graphify_tools import GraphifyTools, build_graphify_tool_specs


@pytest.fixture()
def tool(tmp_path: Path) -> GraphifyTools:
    return GraphifyTools(
        default_project_path=tmp_path,
        output_dir="graphify-out",
        timeout_seconds=10,
    )


def _make_completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


# ---------------------------------------------------------------------------
# graphify_status — no subprocess needed
# ---------------------------------------------------------------------------


def test_status_not_installed(tool: GraphifyTools) -> None:
    with patch("shutil.which", return_value=None):
        result = tool.graphify_status()
    assert result.name == "graphify_status"
    assert result.payload["graphify_installed"] is False
    assert result.payload["graph_json_exists"] is False
    assert result.payload["install_hint"] is not None


def test_status_installed_no_graph(tool: GraphifyTools, tmp_path: Path) -> None:
    with patch("shutil.which", return_value="/usr/local/bin/graphify"):
        result = tool.graphify_status(str(tmp_path))
    assert result.payload["graphify_installed"] is True
    assert result.payload["graph_json_exists"] is False
    assert result.payload["install_hint"] is None


def test_status_installed_with_graph(tool: GraphifyTools, tmp_path: Path) -> None:
    graph_dir = tmp_path / "graphify-out"
    graph_dir.mkdir()
    graph_json = graph_dir / "graph.json"
    graph_json.write_text('{"nodes": []}')

    with patch("shutil.which", return_value="/usr/local/bin/graphify"):
        result = tool.graphify_status(str(tmp_path))
    assert result.payload["graph_json_exists"] is True
    assert result.payload["graph_json_size_bytes"] > 0


# ---------------------------------------------------------------------------
# graphify_query
# ---------------------------------------------------------------------------


def test_query_graphify_not_installed(tool: GraphifyTools) -> None:
    with patch("shutil.which", return_value=None):
        result = tool.graphify_query("what is the auth flow?")
    assert result.name == "graphify_query"
    assert result.payload["exit_code"] == 127
    assert "graphifyy" in result.payload["stderr"].lower() or "graphify" in result.payload["stderr"]


def test_query_success(tool: GraphifyTools, tmp_path: Path) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/graphify"),
        patch("subprocess.run", return_value=_make_completed(stdout="AuthFlow -> LoginHandler")) as mock_run,
    ):
        result = tool.graphify_query("auth flow", str(tmp_path / "graphify-out" / "graph.json"))
    assert result.payload["exit_code"] == 0
    assert "AuthFlow" in result.payload["stdout"]
    mock_run.assert_called_once()


def test_query_failure(tool: GraphifyTools) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/graphify"),
        patch("subprocess.run", return_value=_make_completed(returncode=1, stderr="graph not found")),
    ):
        result = tool.graphify_query("something")
    assert result.payload["exit_code"] == 1
    assert "graph not found" in result.payload["stderr"]


# ---------------------------------------------------------------------------
# graphify_path
# ---------------------------------------------------------------------------


def test_path_success(tool: GraphifyTools) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/graphify"),
        patch("subprocess.run", return_value=_make_completed(stdout="A -> B -> C")),
    ):
        result = tool.graphify_path("A", "C")
    assert result.name == "graphify_path"
    assert result.payload["source"] == "A"
    assert result.payload["target"] == "C"
    assert "A -> B -> C" in result.payload["stdout"]


# ---------------------------------------------------------------------------
# graphify_explain
# ---------------------------------------------------------------------------


def test_explain_success(tool: GraphifyTools) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/graphify"),
        patch("subprocess.run", return_value=_make_completed(stdout="AgentRuntime manages the lifecycle…")),
    ):
        result = tool.graphify_explain("AgentRuntime")
    assert result.name == "graphify_explain"
    assert "AgentRuntime" in result.payload["stdout"]


# ---------------------------------------------------------------------------
# graphify_run
# ---------------------------------------------------------------------------


def test_run_builds_graph(tool: GraphifyTools, tmp_path: Path) -> None:
    graph_dir = tmp_path / "graphify-out"
    graph_dir.mkdir()
    (graph_dir / "graph.json").write_text("{}")

    with (
        patch("shutil.which", return_value="/usr/bin/graphify"),
        patch("subprocess.run", return_value=_make_completed(stdout="Graph built.")),
    ):
        result = tool.graphify_run(str(tmp_path))
    assert result.name == "graphify_run"
    assert result.payload["exit_code"] == 0
    assert result.payload["graph_exists"] is True


def test_run_timeout(tool: GraphifyTools, tmp_path: Path) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/graphify"),
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="graphify", timeout=10)),
    ):
        result = tool.graphify_run(str(tmp_path))
    assert result.payload["timed_out"] is True
    assert result.payload["exit_code"] == 124


# ---------------------------------------------------------------------------
# graphify_update
# ---------------------------------------------------------------------------


def test_update_incremental(tool: GraphifyTools, tmp_path: Path) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/graphify"),
        patch("subprocess.run", return_value=_make_completed(stdout="Updated 3 nodes.")),
    ):
        result = tool.graphify_update(str(tmp_path))
    assert result.name == "graphify_update"
    assert result.payload["exit_code"] == 0


# ---------------------------------------------------------------------------
# graphify_add
# ---------------------------------------------------------------------------


def test_add_url(tool: GraphifyTools) -> None:
    url = "https://example.com/paper.pdf"
    with (
        patch("shutil.which", return_value="/usr/bin/graphify"),
        patch("subprocess.run", return_value=_make_completed(stdout="Added external source.")),
    ):
        result = tool.graphify_add(url)
    assert result.name == "graphify_add"
    assert result.payload["url"] == url


# ---------------------------------------------------------------------------
# build_graphify_tool_specs
# ---------------------------------------------------------------------------


def test_build_specs_returns_all_tools(tool: GraphifyTools) -> None:
    specs = build_graphify_tool_specs(tool)
    names = {s["name"] for s in specs}
    assert names == {
        "graphify_query",
        "graphify_path",
        "graphify_explain",
        "graphify_run",
        "graphify_update",
        "graphify_add",
        "graphify_status",
    }


def test_specs_have_required_fields(tool: GraphifyTools) -> None:
    specs = build_graphify_tool_specs(tool)
    for spec in specs:
        assert "name" in spec
        assert "description" in spec
        assert "schema" in spec
        assert callable(spec["fn"])
