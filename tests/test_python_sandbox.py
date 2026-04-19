import pytest

from adv_archon.tools.python_sandbox import PythonSandboxTool


def test_python_sandbox_executes_confirmed_code() -> None:
    tool = PythonSandboxTool(confirm=lambda _prompt: True)

    result = tool.python_exec("print('hola')")

    assert result.payload["exit_code"] == 0
    assert "hola" in result.payload["stdout"]


def test_python_sandbox_respects_confirmation() -> None:
    tool = PythonSandboxTool(confirm=lambda _prompt: False)

    with pytest.raises(PermissionError):
        tool.python_exec("print('no')")
