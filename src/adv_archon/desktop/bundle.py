from __future__ import annotations

import plistlib
import shutil
import stat
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
    project_root: Path | None = None,
) -> DesktopBundleResult:
    resolved_destination = destination_dir.expanduser().resolve()
    resolved_project_root = (project_root or Path.cwd()).expanduser().resolve()
    qt_plugins_path = _find_qt_plugins_path(resolved_project_root)
    app_path = resolved_destination / f"{app_name}.app"
    contents_path = app_path / "Contents"
    macos_path = contents_path / "MacOS"
    resources_path = contents_path / "Resources"
    info_plist_path = contents_path / "Info.plist"
    launcher_path = macos_path / "adv-archon-desktop"
    bundled_icon_path: Path | None = None

    resources_path.mkdir(parents=True, exist_ok=True)
    macos_path.mkdir(parents=True, exist_ok=True)

    venv_python = resolved_project_root / ".venv" / "bin" / "python"

    launcher_lines = [
        "#!/bin/sh",
        # Source user shell so PATH includes homebrew/cargo even from Finder
        '[ -f "$HOME/.zprofile" ] && . "$HOME/.zprofile"',
        '[ -f "$HOME/.zshrc"    ] && . "$HOME/.zshrc" 2>/dev/null',
        '[ -f "$HOME/.bash_profile" ] && . "$HOME/.bash_profile" 2>/dev/null',
        "# Find uv — common locations",
        'for UV in "$HOME/.cargo/bin/uv" "/opt/homebrew/bin/uv" "/usr/local/bin/uv" "$(command -v uv 2>/dev/null)"; do',
        '    [ -x "$UV" ] && break',
        "done",
        'if [ ! -x "$UV" ]; then',
        "    osascript -e 'display alert \"ADV ARCHON\" message \"No se encontró uv. Instálalo con: curl -LsSf https://astral.sh/uv/install.sh | sh\" as critical'",
        "    exit 1",
        "fi",
        f"cd '{resolved_project_root}'",
        f"export PYTHONPATH='{resolved_project_root / 'src'}':\"$PYTHONPATH\"",
        "export QT_LOGGING_RULES='qt.qpa.fonts.warning=false'",
        # Use venv Python directly for sysconfig (fast, no uv overhead)
        f'VENV_PY="{venv_python}"',
        '[ -x "$VENV_PY" ] || VENV_PY=$("$UV" run python -c "import sys; print(sys.executable)" 2>/dev/null)',
        'SITE=$("$VENV_PY" -c "import sysconfig; print(sysconfig.get_path(\'platlib\'))" 2>/dev/null)',
        'if [ -n "$SITE" ] && [ -d "$SITE/PySide6/Qt/plugins" ]; then',
        '    export QT_PLUGIN_PATH="$SITE/PySide6/Qt/plugins"',
        '    export QT_QPA_PLATFORM_PLUGIN_PATH="$SITE/PySide6/Qt/plugins/platforms"',
        "fi",
        'exec "$UV" run python -m adv_archon.main desktop "$@"',
        "",
    ]
    launcher = "\n".join(launcher_lines)
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
        "NSAppleEventsUsageDescription": "ADV ARCHON necesita Apple Events para funcionar correctamente.",
        "NSDocumentsFolderUsageDescription": "ADV ARCHON accede a tus documentos para analizar planos.",
        # Ensure PATH includes common uv/homebrew locations when launched from Finder
        "LSEnvironment": {
            "PATH": (
                f"{Path.home()}/.cargo/bin"
                ":/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            ),
        },
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


def _find_qt_plugins_path(project_root: Path) -> Path | None:
    candidates = sorted(
        (project_root / ".venv" / "lib").glob("python*/site-packages/PySide6/Qt/plugins")
    )
    for candidate in candidates:
        if (candidate / "platforms" / "libqcocoa.dylib").exists():
            return candidate
    return None


__all__ = ["DesktopBundleResult", "create_macos_app_bundle"]
