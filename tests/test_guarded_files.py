from __future__ import annotations

from pathlib import Path

import pytest

from adv_archon.tools.guarded_files import FileAccessPolicy, GuardedFileTools


def test_guarded_file_tools_blocks_sensitive_paths(tmp_path: Path) -> None:
    policy = FileAccessPolicy(
        allowed_roots=(tmp_path,),
        sensitive_roots=(tmp_path / "System",),
        allow_sensitive_reads=False,
    )
    tools = GuardedFileTools(policy=policy)
    sensitive = tmp_path / "System" / "secret.txt"
    sensitive.parent.mkdir(parents=True)
    sensitive.write_text("hola")

    with pytest.raises(PermissionError):
        tools.read_file(str(sensitive))


def test_guarded_file_tools_filters_find_local_matches(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    (allowed / "grimorio.txt").write_text("texto")
    (blocked / "grimorio.txt").write_text("texto")
    policy = FileAccessPolicy(
        allowed_roots=(tmp_path,),
        sensitive_roots=(blocked,),
        allow_sensitive_reads=False,
    )
    tools = GuardedFileTools(policy=policy)

    result = tools.find_local("grimorio", path=str(tmp_path), max_results=10)

    matches = result.payload["matches"]
    assert len(matches) == 1
    assert str(allowed / "grimorio.txt") == matches[0]["path"]
