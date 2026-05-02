from __future__ import annotations

import plistlib
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from adv_archon.desktop.branding import logo_path


@dataclass(frozen=True, slots=True)
class DesktopBundleResult:
    app_path: Path
    launcher_path: Path
    info_plist_path: Path
    icon_path: Path | None = None


def create_macos_app_bundle(
    *,
    destination_dir: Path,
    app_name: str = "ADV ARCHON",
    bundle_identifier: str = "com.advarchon.desktop",
    python_executable: Path | None = None,
) -> DesktopBundleResult:
    resolved_destination = destination_dir.expanduser().resolve()
    app_path = resolved_destination / f"{app_name}.app"
    contents_path = app_path / "Contents"
    macos_path = contents_path / "MacOS"
    resources_path = contents_path / "Resources"
    info_plist_path = contents_path / "Info.plist"
    launcher_path = macos_path / "adv-archon-desktop"
    bundled_icon_path: Path | None = None

    resources_path.mkdir(parents=True, exist_ok=True)
    macos_path.mkdir(parents=True, exist_ok=True)

    executable = (python_executable or Path(sys.executable)).expanduser().resolve()
    launcher = "\n".join(
        [
            "#!/bin/zsh",
            "export PATH=\"/opt/homebrew/bin:/usr/local/bin:$PATH\"",
            "cd \"$HOME\"",
            f"exec '{executable}' -m adv_archon.main desktop \"$@\"",
            "",
        ]
    )
    launcher_path.write_text(launcher, encoding="utf-8")
    current_mode = launcher_path.stat().st_mode
    launcher_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    source_logo = logo_path()
    if source_logo.exists():
        bundled_icon_path = resources_path / source_logo.name
        shutil.copy2(source_logo, bundled_icon_path)

    info_plist = {
        "CFBundleName": app_name,
        "CFBundleDisplayName": app_name,
        "CFBundleIdentifier": bundle_identifier,
        "CFBundleVersion": "1.0",
        "CFBundleShortVersionString": "1.0",
        "CFBundleExecutable": launcher_path.name,
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
    }
    if bundled_icon_path is not None:
        info_plist["CFBundleIconFile"] = bundled_icon_path.name
    with info_plist_path.open("wb") as handle:
        plistlib.dump(info_plist, handle)

    return DesktopBundleResult(
        app_path=app_path,
        launcher_path=launcher_path,
        info_plist_path=info_plist_path,
        icon_path=bundled_icon_path,
    )


__all__ = ["DesktopBundleResult", "create_macos_app_bundle"]
