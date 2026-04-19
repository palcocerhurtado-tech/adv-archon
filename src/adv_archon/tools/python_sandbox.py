from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adv_archon.core.logging import AppLogger

ConfirmCallback = Callable[[str], bool]


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class PythonSandboxTool:
    def __init__(
        self,
        *,
        confirm: ConfirmCallback,
        logger: AppLogger | None = None,
        default_cwd: Path | None = None,
        timeout_seconds: int = 15,
    ) -> None:
        self._confirm = confirm
        self._logger = logger
        self._default_cwd = default_cwd or Path.cwd()
        self._timeout_seconds = timeout_seconds

    def python_exec(self, code: str, timeout_seconds: int | None = None) -> ToolResult:
        if not code.strip():
            raise ValueError("El snippet Python no puede estar vacío.")
        prompt = (
            "Se va a ejecutar un snippet Python en un subproceso efímero.\n"
            f"Código:\n{code}\n"
            "¿Confirmas?"
        )
        if not self._confirm(prompt):
            raise PermissionError("Ejecución cancelada por el usuario.")

        timeout = timeout_seconds or self._timeout_seconds
        try:
            completed = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                cwd=self._default_cwd,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            payload = {
                "code": code,
                "exit_code": 124,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "timed_out": True,
            }
            if self._logger is not None:
                self._logger.log("python_exec", **payload)
            return ToolResult(name="python_exec", payload=payload)

        payload = {
            "code": code,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
        if self._logger is not None:
            self._logger.log("python_exec", **payload)
        return ToolResult(name="python_exec", payload=payload)


def build_python_tool_specs(tool: PythonSandboxTool) -> list[dict[str, Any]]:
    return [
        {
            "name": "python_exec",
            "description": "Run a short Python snippet in a temporary subprocess.",
            "schema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["code"],
            },
            "fn": tool.python_exec,
        }
    ]
