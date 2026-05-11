import os
import plistlib
from pathlib import Path

from adv_archon.desktop import bundle as bundle_module


def test_create_macos_app_bundle_writes_plist_and_launcher(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bundle_module, "_write_native_launcher", lambda _path: False)
    project_root = tmp_path / "project"
    qt_platforms = (
        project_root
        / ".venv"
        / "lib"
        / "python3.12"
        / "site-packages"
        / "PySide6"
        / "Qt"
        / "plugins"
        / "platforms"
    )
    qt_platforms.mkdir(parents=True)
    (qt_platforms / "libqcocoa.dylib").write_text("", encoding="utf-8")
    python_executable = tmp_path / ".venv" / "bin" / "python"
    result = bundle_module.create_macos_app_bundle(
        destination_dir=tmp_path,
        python_executable=python_executable,
        project_root=project_root,
    )

    assert result.app_path.name == "ADV ARCHON.app"
    assert result.info_plist_path.exists()
    assert result.launcher_path.exists()
    assert os.access(result.launcher_path, os.X_OK)
    assert result.icon_path is not None
    assert result.icon_path.exists()

    launcher_script = (
        result.app_path / "Contents" / "Resources" / "launch-adv-archon.sh"
    )
    assert launcher_script.exists()
    assert os.access(launcher_script, os.X_OK)

    launcher = launcher_script.read_text(encoding="utf-8")
    assert "#!/bin/sh" in launcher
    assert "uv" in launcher                         # uses uv run, not hardcoded Python
    assert f"PROJECT_ROOT='{project_root}'" in launcher
    assert 'cd "$PROJECT_ROOT"' in launcher
    assert 'chflags -R nohidden "$PROJECT_ROOT/.venv"' in launcher
    assert 'export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"' in launcher
    # Reset stale Finder env vars, then set the path from PySide6's own metadata.
    assert "unset QT_PLUGIN_PATH" in launcher
    assert "unset QT_QPA_PLATFORM_PLUGIN_PATH" in launcher
    assert 'export QT_PLUGIN_PATH="$QT_PLUGIN_DIR"' in launcher
    assert 'export QT_QPA_PLATFORM_PLUGIN_PATH="$QT_PLUGIN_DIR/platforms"' in launcher
    assert "import dotenv.main" in launcher
    assert "--reinstall-package python-dotenv" in launcher
    assert "--reinstall-package PySide6" in launcher
    assert "sysconfig" not in launcher
    assert "-m adv_archon.main desktop" in launcher

    with result.info_plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    assert plist["CFBundleName"] == "ADV ARCHON"
    assert "Beta" in plist["CFBundleShortVersionString"]
    assert plist["CFBundleExecutable"] == "adv-archon-desktop"
    assert plist["CFBundleIconFile"] == result.icon_path.name


def test_create_macos_app_bundle_can_embed_project_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(bundle_module, "_write_native_launcher", lambda _path: False)
    project_root = tmp_path / "project"
    (project_root / "src" / "adv_archon").mkdir(parents=True)
    (project_root / "src" / "adv_archon" / "__init__.py").write_text("", encoding="utf-8")
    (project_root / ".venv").mkdir()
    (project_root / ".git").mkdir()
    (project_root / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (project_root / ".env.local").write_text("TOKEN=secret\n", encoding="utf-8")
    (project_root / ".env.example").write_text("TOKEN=\n", encoding="utf-8")
    (project_root / ".DS_Store").write_text("", encoding="utf-8")
    (project_root / "tests").mkdir()
    (project_root / "tests" / "test_secret.py").write_text("", encoding="utf-8")
    (project_root / "docs" / "archive").mkdir(parents=True)
    (project_root / "docs" / "archive" / "old.md").write_text("", encoding="utf-8")
    (project_root / "normativa_arquitectura_es" / "src").mkdir(parents=True)
    (project_root / "normativa_arquitectura_es" / "src" / "rag.py").write_text(
        "",
        encoding="utf-8",
    )
    (project_root / "src" / "adv_archon.egg-info").mkdir()
    (project_root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    result = bundle_module.create_macos_app_bundle(
        destination_dir=tmp_path / "dist",
        project_root=project_root,
        embed_project=True,
    )

    assert result.embedded_project_path is not None
    assert (result.embedded_project_path / "src" / "adv_archon").exists()
    assert not (result.embedded_project_path / ".venv").exists()
    assert not (result.embedded_project_path / ".git").exists()
    assert not (result.embedded_project_path / ".env").exists()
    assert not (result.embedded_project_path / ".env.local").exists()
    assert (result.embedded_project_path / ".env.example").exists()
    assert not (result.embedded_project_path / ".DS_Store").exists()
    assert not (result.embedded_project_path / "tests").exists()
    assert not (result.embedded_project_path / "docs" / "archive").exists()
    assert not (result.embedded_project_path / "normativa_arquitectura_es").exists()
    assert not (result.embedded_project_path / "src" / "adv_archon.egg-info").exists()
    launcher = (
        result.app_path / "Contents" / "Resources" / "launch-adv-archon.sh"
    ).read_text(encoding="utf-8")
    assert "EMBEDDED_PROJECT" in launcher
    assert 'cd "$PROJECT_ROOT"' in launcher
