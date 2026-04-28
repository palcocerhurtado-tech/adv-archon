from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


_GRAPHIFY_NOT_FOUND = (
    "Graphify no está instalado. "
    "Ejecuta: pip install graphifyy && graphify install"
)


class GraphifyTools:
    def __init__(
        self,
        *,
        default_project_path: Path | None = None,
        output_dir: str = "graphify-out",
        timeout_seconds: int = 60,
    ) -> None:
        self._default_project_path = default_project_path or Path.cwd()
        self._output_dir = output_dir
        self._timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # Public tool methods
    # ------------------------------------------------------------------

    def graphify_query(self, query: str, graph_path: str | None = None) -> ToolResult:
        """Query the Graphify knowledge graph with a natural-language question."""
        resolved = self._resolve_graph_path(graph_path)
        result = self._run(
            ["graphify", "query", query, "--graph", str(resolved)],
            cwd=self._default_project_path,
        )
        return ToolResult(
            name="graphify_query",
            payload={
                "query": query,
                "graph_path": str(resolved),
                **result,
            },
        )

    def graphify_path(
        self,
        source: str,
        target: str,
        graph_path: str | None = None,
    ) -> ToolResult:
        """Find the dependency/relationship path between two concepts in the graph."""
        resolved = self._resolve_graph_path(graph_path)
        result = self._run(
            ["graphify", "path", source, target, "--graph", str(resolved)],
            cwd=self._default_project_path,
        )
        return ToolResult(
            name="graphify_path",
            payload={
                "source": source,
                "target": target,
                "graph_path": str(resolved),
                **result,
            },
        )

    def graphify_explain(self, concept: str, graph_path: str | None = None) -> ToolResult:
        """Ask Graphify to explain a concept using the knowledge graph."""
        resolved = self._resolve_graph_path(graph_path)
        result = self._run(
            ["graphify", "explain", concept, "--graph", str(resolved)],
            cwd=self._default_project_path,
        )
        return ToolResult(
            name="graphify_explain",
            payload={
                "concept": concept,
                "graph_path": str(resolved),
                **result,
            },
        )

    def graphify_run(self, path: str | None = None) -> ToolResult:
        """Re-extract and update the Graphify graph for a project (no LLM needed).
        Note: the initial graph must be built once via Claude Code's /graphify . skill.
        """
        target = Path(path).expanduser().resolve() if path else self._default_project_path
        graph_json = target / self._output_dir / "graph.json"
        if not graph_json.exists():
            return ToolResult(
                name="graphify_run",
                payload={
                    "project_path": str(target),
                    "graph_json": str(graph_json),
                    "graph_exists": False,
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": (
                        "No existe graph.json en este proyecto. "
                        "Construye el grafo inicial abriendo Claude Code en la carpeta "
                        f"'{target}' y ejecutando: /graphify ."
                    ),
                    "timed_out": False,
                },
            )
        result = self._run(
            ["graphify", "update", str(target)],
            cwd=target,
            timeout=120,
        )
        return ToolResult(
            name="graphify_run",
            payload={
                "project_path": str(target),
                "graph_json": str(graph_json),
                "graph_exists": graph_json.exists(),
                **result,
            },
        )

    def graphify_update(self, path: str | None = None) -> ToolResult:
        """Incrementally update the Graphify graph (faster than full rebuild)."""
        target = Path(path).expanduser().resolve() if path else self._default_project_path
        result = self._run(
            ["graphify", "update", str(target)],
            cwd=target,
            timeout=90,
        )
        graph_json = target / self._output_dir / "graph.json"
        return ToolResult(
            name="graphify_update",
            payload={
                "project_path": str(target),
                "graph_json": str(graph_json),
                "graph_exists": graph_json.exists(),
                **result,
            },
        )

    def graphify_add(self, url: str, graph_path: str | None = None) -> ToolResult:
        """Add an external URL (article, paper, blog) to the Graphify knowledge graph."""
        resolved = self._resolve_graph_path(graph_path)
        result = self._run(
            ["graphify", "add", url],
            cwd=self._default_project_path,
        )
        return ToolResult(
            name="graphify_add",
            payload={
                "url": url,
                "graph_path": str(resolved),
                **result,
            },
        )

    def graphify_status(self, path: str | None = None) -> ToolResult:
        """Check whether a Graphify graph exists for a project directory."""
        target = Path(path).expanduser().resolve() if path else self._default_project_path
        graph_dir = target / self._output_dir
        graph_json = graph_dir / "graph.json"
        report_md = graph_dir / "GRAPH_REPORT.md"
        installed = shutil.which("graphify") is not None
        return ToolResult(
            name="graphify_status",
            payload={
                "project_path": str(target),
                "graphify_installed": installed,
                "graph_dir": str(graph_dir),
                "graph_json_exists": graph_json.exists(),
                "report_exists": report_md.exists(),
                "graph_json_size_bytes": graph_json.stat().st_size if graph_json.exists() else 0,
                "install_hint": None if installed else _GRAPHIFY_NOT_FOUND,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_graph_path(self, graph_path: str | None) -> Path:
        if graph_path:
            return Path(graph_path).expanduser().resolve()
        return self._default_project_path / self._output_dir / "graph.json"

    def _run(
        self,
        args: list[str],
        *,
        cwd: Path,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        if shutil.which(args[0]) is None:
            return {
                "exit_code": 127,
                "stdout": "",
                "stderr": _GRAPHIFY_NOT_FOUND,
                "timed_out": False,
            }
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                cwd=cwd,
                text=True,
                timeout=timeout or self._timeout_seconds,
                check=False,
            )
            return {
                "exit_code": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "Tiempo de espera agotado.",
                "timed_out": True,
            }


def build_graphify_tool_specs(tool: GraphifyTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "graphify_query",
            "description": (
                "Query the Graphify knowledge graph with a natural-language question. "
                "Use this BEFORE reading individual files when exploring a codebase. "
                "Returns architectural relationships, dependencies, and relevant source paths."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language question about the codebase or knowledge graph.",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Absolute path to graph.json. Defaults to graphify-out/graph.json in the project.",
                    },
                },
                "required": ["query"],
            },
            "fn": tool.graphify_query,
        },
        {
            "name": "graphify_path",
            "description": (
                "Find the relationship or dependency path between two concepts, "
                "modules, or components in the Graphify graph."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Starting concept or module name."},
                    "target": {"type": "string", "description": "Target concept or module name."},
                    "graph_path": {"type": "string"},
                },
                "required": ["source", "target"],
            },
            "fn": tool.graphify_path,
        },
        {
            "name": "graphify_explain",
            "description": "Ask Graphify to explain a concept using graph context. Prefer this over raw file reads for conceptual questions.",
            "schema": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string", "description": "Concept, class, or module to explain."},
                    "graph_path": {"type": "string"},
                },
                "required": ["concept"],
            },
            "fn": tool.graphify_explain,
        },
        {
            "name": "graphify_run",
            "description": "Build or rebuild the Graphify knowledge graph for a directory. Use once per project before querying.",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project directory to scan. Defaults to the current working directory.",
                    },
                },
                "required": [],
            },
            "fn": tool.graphify_run,
        },
        {
            "name": "graphify_update",
            "description": "Incrementally update the Graphify graph after code changes (faster than a full rebuild).",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": [],
            },
            "fn": tool.graphify_update,
        },
        {
            "name": "graphify_add",
            "description": "Add an external URL (paper, blog, documentation) to the Graphify knowledge graph as context.",
            "schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL of the resource to add."},
                    "graph_path": {"type": "string"},
                },
                "required": ["url"],
            },
            "fn": tool.graphify_add,
        },
        {
            "name": "graphify_status",
            "description": "Check whether Graphify is installed and whether a graph exists for the project.",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": [],
            },
            "fn": tool.graphify_status,
        },
    ]


def format_graphify_result(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    stdout = str(payload.get("stdout", "")).strip()
    stderr = str(payload.get("stderr", "")).strip()
    exit_code = payload.get("exit_code", 0)
    if stdout:
        lines.append(stdout)
    if stderr and exit_code != 0:
        lines.append(f"[error] {stderr}")
    elif stderr:
        lines.append(stderr)
    if not lines:
        lines.append("(sin salida)")
    return "\n".join(lines)
