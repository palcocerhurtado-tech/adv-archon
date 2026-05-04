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
    assert f"cd '{project_root}'" in launcher
    assert f"export PYTHONPATH='{project_root / 'src'}':\"$PYTHONPATH\"" in launcher
    # Qt plugin path is now detected dynamically at runtime, not baked in
    assert "QT_PLUGIN_PATH" in launcher
    assert "sysconfig" in launcher
    assert "-m adv_archon.main desktop" in launcher

    with result.info_plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    assert plist["CFBundleName"] == "ADV ARCHON"
    assert plist["CFBundleExecutable"] == "adv-archon-desktop"
    assert plist["CFBundleIconFile"] == result.icon_path.name
