"""
Standalone entry point for the PyInstaller macOS bundle.

This file is the Analysis target in archon.spec. It must not import
anything at module level that isn't available in a frozen environment.
"""
from __future__ import annotations

import sys


def main() -> None:
    # Fix sys.path so adv_archon is importable in frozen builds
    if getattr(sys, "frozen", False):
        bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
        if bundle_dir not in sys.path:
            sys.path.insert(0, bundle_dir)

    from adv_archon.main import desktop_main
    sys.exit(desktop_main())


if __name__ == "__main__":
    main()
