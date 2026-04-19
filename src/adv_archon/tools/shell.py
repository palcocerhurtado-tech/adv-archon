from __future__ import annotations

import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adv_archon.core.logging import AppLogger

ConfirmCallback = Callable[[str], bool]
SYSTEM_REDIRECT_RE = re.compile(r"[<>]{1,2}\s*(/dev/|/etc/|/usr/|/System/|/Library/)")
CURL_PIPE_RE = re.compile(r"\b(?:curl|wget)\b[^|]*\|\s*(?:sh|bash)\b")
SHELL_OPERATORS = {"|", "||", "&&", ";", ">", ">>", "<", "<<", "&"}
ABSOLUTE_BLACKLIST_COMMANDS = {"rm", "rmdir", "mv", "dd", "mkfs", "sudo"}
READONLY_GIT_SUBCOMMANDS = {"status", "log", "diff", "branch", "show"}
VERSION_FLAGS = {"--version", "-V", "version"}


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


@dataclass(slots=True)
class ShellDecision:
    requires_confirmation: bool
    reason: str
    category: str


@dataclass(slots=True)
class ShellPolicy:
    whitelist_commands: tuple[str, ...]
    timeout_seconds: int = 20

    def evaluate(self, command: str, *, auto_mode: bool) -> ShellDecision:
        stripped = command.strip()
        if not stripped:
            raise ValueError("El comando shell no puede estar vacío.")

        if self._is_absolutely_blacklisted(stripped):
            return ShellDecision(
                requires_confirmation=True,
                reason="Comando en la lista negra absoluta.",
                category="blacklist",
            )
        if self._is_whitelisted(stripped):
            return ShellDecision(
                requires_confirmation=False,
                reason="Comando permitido por la whitelist de solo lectura.",
                category="whitelist",
            )
        if auto_mode:
            return ShellDecision(
                requires_confirmation=False,
                reason="Modo AUTO activo para comandos no destructivos.",
                category="auto",
            )
        return ShellDecision(
            requires_confirmation=True,
            reason="Comando fuera de la whitelist de solo lectura.",
            category="manual",
        )

    def _is_whitelisted(self, command: str) -> bool:
        tokens = self._tokens(command)
        if not tokens:
            return False
        if any(token in SHELL_OPERATORS for token in tokens):
            return False

        executable = tokens[0]
        if executable in self.whitelist_commands:
            return True
        if len(tokens) == 2 and tokens[1] in VERSION_FLAGS:
            return True
        if executable == "git":
            return self._is_whitelisted_git(tokens)
        return False

    def _is_whitelisted_git(self, tokens: list[str]) -> bool:
        if len(tokens) < 2:
            return False
        subcommand = tokens[1]
        if subcommand in READONLY_GIT_SUBCOMMANDS:
            return True
        return subcommand == "remote" and "-v" in tokens[2:]

    def _is_absolutely_blacklisted(self, command: str) -> bool:
        lowered = command.lower()
        tokens = [token.lower() for token in self._tokens(command)]
        if tokens and tokens[0] in ABSOLUTE_BLACKLIST_COMMANDS:
            return True
        if tokens[:2] in (["chmod", "-r"], ["chown", "-r"]):
            return True
        if lowered.startswith("git clean") or " git clean" in lowered:
            return True
        if "git reset --hard" in lowered:
            return True
        if "git push --force" in lowered or "git push -f" in lowered:
            return True
        if CURL_PIPE_RE.search(lowered):
            return True
        return bool(SYSTEM_REDIRECT_RE.search(command))

    @staticmethod
    def _tokens(command: str) -> list[str]:
        try:
            return shlex.split(command)
        except ValueError:
            return [command]


class AutoModeManager:
    def __init__(self) -> None:
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self, confirm: ConfirmCallback) -> bool:
        if self._enabled:
            return True
        prompt = (
            "Vas a entrar en modo AUTO. Esto significa:\n"
            "  - Cualquier comando shell no destructivo se ejecutará sin confirmación\n"
            "  - Los comandos destructivos seguirán pidiendo confirmación\n"
            "Duración: esta sesión\n"
            "¿Confirmas?"
        )
        self._enabled = confirm(prompt)
        return self._enabled

    def disable(self) -> None:
        self._enabled = False

    def status(self) -> str:
        return "on" if self._enabled else "off"


class ShellTool:
    def __init__(
        self,
        *,
        policy: ShellPolicy,
        auto_mode: AutoModeManager,
        confirm: ConfirmCallback,
        logger: AppLogger | None = None,
        default_cwd: Path | None = None,
    ) -> None:
        self._policy = policy
        self._auto_mode = auto_mode
        self._confirm = confirm
        self._logger = logger
        self._default_cwd = default_cwd or Path.cwd()

    def shell_exec(
        self,
        cmd: str,
        cwd: str | None = None,
        timeout_seconds: int | None = None,
    ) -> ToolResult:
        decision = self._policy.evaluate(cmd, auto_mode=self._auto_mode.enabled)
        if decision.requires_confirmation:
            prompt = (
                f"Se va a ejecutar un comando shell.\n"
                f"Motivo: {decision.reason}\n"
                f"Comando exacto:\n{cmd}\n"
                "¿Confirmas?"
            )
            if not self._confirm(prompt):
                raise PermissionError("Ejecución cancelada por el usuario.")

        target_cwd = (Path(cwd).expanduser().resolve() if cwd else self._default_cwd)
        timeout = timeout_seconds or self._policy.timeout_seconds
        try:
            completed = subprocess.run(
                ["/bin/zsh", "-lc", cmd],
                capture_output=True,
                cwd=target_cwd,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            payload = {
                "command": cmd,
                "cwd": str(target_cwd),
                "exit_code": 124,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": True,
                "decision": decision.category,
            }
            if self._logger is not None:
                self._logger.log("shell_exec", **payload)
            return ToolResult(name="shell_exec", payload=payload)

        payload = {
            "command": cmd,
            "cwd": str(target_cwd),
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
            "decision": decision.category,
        }
        if self._logger is not None:
            self._logger.log("shell_exec", **payload)
        return ToolResult(name="shell_exec", payload=payload)


def format_shell_result(payload: dict[str, Any]) -> str:
    lines = [
        f"$ {payload['command']}",
        f"[exit {payload['exit_code']}]",
    ]
    stdout = str(payload.get("stdout", "")).strip()
    stderr = str(payload.get("stderr", "")).strip()
    if stdout:
        lines.append(stdout)
    if stderr:
        lines.append("stderr:")
        lines.append(stderr)
    return "\n".join(lines)


def build_shell_tool_specs(tool: ShellTool) -> list[dict[str, Any]]:
    return [
        {
            "name": "shell_exec",
            "description": (
                "Run a shell command under the user's safety policy. "
                "Use it for terminal inspection and trusted commands."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string"},
                    "cwd": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["cmd"],
            },
            "fn": tool.shell_exec,
        }
    ]
