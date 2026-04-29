import os
import plistlib
from pathlib import Path

from adv_archon.desktop.bundle import create_macos_app_bundle


def test_create_macos_app_bundle_writes_plist_and_launcher(tmp_path: Path) -> None:
    result = create_macos_app_bundle(
        destination_dir=tmp_path,
        python_executable=Path("/usr/bin/python3"),
    )

    assert result.app_path.name == "ADV ARCHON.app"
    assert result.info_plist_path.exists()
    assert result.launcher_path.exists()
    assert os.access(result.launcher_path, os.X_OK)

    launcher = result.launcher_path.read_text(encoding="utf-8")
    assert "/usr/bin/python3" in launcher
    assert "-m adv_archon.main desktop" in launcher

    with result.info_plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    assert plist["CFBundleName"] == "ADV ARCHON"
    assert plist["CFBundleExecutable"] == "adv-archon-desktop"

