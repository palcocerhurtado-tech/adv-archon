from pathlib import Path

import pytest

from adv_archon.tools.shell import AutoModeManager, ShellPolicy, ShellTool


def test_shell_policy_allows_readonly_whitelist() -> None:
    policy = ShellPolicy(whitelist_commands=("ls", "pwd", "cat"))

    decision = policy.evaluate("ls -la", auto_mode=False)

    assert decision.requires_confirmation is False
    assert decision.category == "whitelist"


def test_shell_policy_blacklists_destructive_commands() -> None:
    policy = ShellPolicy(whitelist_commands=("ls", "pwd"))

    decision = policy.evaluate("rm -rf demo", auto_mode=True)

    assert decision.requires_confirmation is True
    assert decision.category == "blacklist"


def test_auto_mode_manager_requires_confirmation() -> None:
    manager = AutoModeManager()

    enabled = manager.enable(lambda _prompt: True)

    assert enabled is True
    assert manager.enabled is True


def test_shell_tool_runs_whitelisted_command(tmp_path: Path) -> None:
    policy = ShellPolicy(whitelist_commands=("pwd",))
    manager = AutoModeManager()
    tool = ShellTool(
        policy=policy,
        auto_mode=manager,
        confirm=lambda _prompt: False,
        default_cwd=tmp_path,
    )

    result = tool.shell_exec("pwd")

    assert result.payload["exit_code"] == 0
    assert str(tmp_path) in result.payload["stdout"]


def test_shell_tool_blocks_unconfirmed_command(tmp_path: Path) -> None:
    policy = ShellPolicy(whitelist_commands=("pwd",))
    manager = AutoModeManager()
    tool = ShellTool(
        policy=policy,
        auto_mode=manager,
        confirm=lambda _prompt: False,
        default_cwd=tmp_path,
    )

    with pytest.raises(PermissionError):
        tool.shell_exec("touch demo.txt")
