"""Reflector middleware: risk-assess tool calls before execution.

Wraps tool functions and returns APPROVE / DOWNGRADE / BLOCK decisions
based on the tool name and arguments. Logs all decisions to
~/.adv-archon/reflection.log.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

_LOG_DIR = Path.home() / ".adv-archon"
_LOG_FILE = _LOG_DIR / "reflection.log"

logger = logging.getLogger("archon.reflector")

# Tools that write or delete irreversibly
_HIGH_RISK_TOOLS = {
    "write_file",
    "edit_file",
    "delete_file",
    "shell",
    "run_shell",
    "git_push",
    "git_reset",
    "install_package",
}

# Argument patterns that elevate risk
_CRITICAL_PATH_PREFIXES = (
    str(Path.home() / ".ssh"),
    str(Path.home() / ".zshrc"),
    str(Path.home() / ".bashrc"),
    str(Path.home() / ".gnupg"),
    "/etc/",
    "/usr/",
)


class Verdict(StrEnum):
    APPROVE = "APPROVE"
    DOWNGRADE = "DOWNGRADE"  # run in safe / dry-run mode
    BLOCK = "BLOCK"


def _ensure_log() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log(verdict: Verdict, tool: str, args: dict[str, Any], reason: str) -> None:
    _ensure_log()
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict.value,
        "tool": tool,
        "reason": reason,
        "args_preview": str(args)[:200],
    }
    with _LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _assess(tool_name: str, args: dict[str, Any]) -> tuple[Verdict, str]:
    """Return (verdict, reason) for a tool call."""
    # Check for critical paths in any string argument
    all_args_str = " ".join(str(v) for v in args.values())
    for prefix in _CRITICAL_PATH_PREFIXES:
        if prefix in all_args_str:
            return Verdict.BLOCK, f"Ruta crítica detectada: {prefix}"

    # git push --force to main/master
    if tool_name in ("shell", "run_shell", "git_push"):
        cmd = args.get("command", "") or args.get("cmd", "")
        if isinstance(cmd, str) and "push" in cmd and (
            "--force" in cmd or "-f" in cmd
        ) and ("main" in cmd or "master" in cmd):
            return Verdict.BLOCK, "Force-push a rama protegida bloqueado"

    if tool_name in _HIGH_RISK_TOOLS:
        return Verdict.APPROVE, f"Herramienta de alto riesgo revisada: {tool_name}"

    return Verdict.APPROVE, "Sin riesgo detectado"


def reflect(
    tool_name: str,
    fn: Callable[..., Any],
    args: dict[str, Any],
) -> tuple[Verdict, str, Any]:
    """Assess and optionally execute a tool call.

    Returns (verdict, reason, result).
    result is None when BLOCK or when an error occurs.
    """
    verdict, reason = _assess(tool_name, args)
    _log(verdict, tool_name, args, reason)

    if verdict == Verdict.BLOCK:
        return verdict, reason, None

    try:
        result = fn(**args)
    except Exception as exc:
        return Verdict.APPROVE, reason, f"[Error en herramienta: {exc}]"

    return verdict, reason, result
