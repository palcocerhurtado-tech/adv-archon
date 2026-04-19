from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adv_archon.core.logging import AppLogger
from adv_archon.tools.shell import AutoModeManager, ShellPolicy

ConfirmCallback = Callable[[str], bool]


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


class MacTools:
    def __init__(
        self,
        *,
        confirm: ConfirmCallback,
        auto_mode: AutoModeManager,
        shell_policy: ShellPolicy,
        logger: AppLogger | None = None,
        default_cwd: Path | None = None,
    ) -> None:
        self._confirm = confirm
        self._auto_mode = auto_mode
        self._shell_policy = shell_policy
        self._logger = logger
        self._default_cwd = default_cwd or Path.cwd()

    def clipboard_read(self) -> ToolResult:
        completed = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            check=False,
        )
        payload = {
            "text": completed.stdout,
            "exit_code": completed.returncode,
        }
        if self._logger is not None:
            self._logger.log("clipboard_read", exit_code=completed.returncode)
        return ToolResult(name="clipboard_read", payload=payload)

    def clipboard_write(self, text: str) -> ToolResult:
        completed = subprocess.run(
            ["pbcopy"],
            input=text,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = {
            "chars": len(text),
            "exit_code": completed.returncode,
            "stderr": completed.stderr,
        }
        if self._logger is not None:
            self._logger.log("clipboard_write", chars=len(text), exit_code=completed.returncode)
        return ToolResult(name="clipboard_write", payload=payload)

    def open_app(self, path_or_url: str) -> ToolResult:
        synthetic = f"open {path_or_url}"
        decision = self._shell_policy.evaluate(synthetic, auto_mode=self._auto_mode.enabled)
        if decision.requires_confirmation:
            prompt = (
                "Se va a abrir un recurso con macOS `open`.\n"
                f"Motivo: {decision.reason}\n"
                f"Destino:\n{path_or_url}\n"
                "¿Confirmas?"
            )
            if not self._confirm(prompt):
                raise PermissionError("Apertura cancelada por el usuario.")

        completed = subprocess.run(
            ["open", path_or_url],
            capture_output=True,
            cwd=self._default_cwd,
            text=True,
            check=False,
        )
        payload = {
            "target": path_or_url,
            "exit_code": completed.returncode,
            "stderr": completed.stderr,
            "decision": decision.category,
        }
        if self._logger is not None:
            self._logger.log("open_app", **payload)
        return ToolResult(name="open_app", payload=payload)


def build_mac_tool_specs(tool: MacTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "clipboard_read",
            "description": "Read the current text content from the macOS clipboard.",
            "schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
            "fn": tool.clipboard_read,
        },
        {
            "name": "clipboard_write",
            "description": "Write text into the macOS clipboard.",
            "schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
            "fn": tool.clipboard_write,
        },
        {
            "name": "open_app",
            "description": "Open a local file, app target, or URL with macOS open.",
            "schema": {
                "type": "object",
                "properties": {
                    "path_or_url": {"type": "string"},
                },
                "required": ["path_or_url"],
            },
            "fn": tool.open_app,
        },
    ]
