from __future__ import annotations

import pytest

from adv_archon.desktop.window import PYSIDE6_AVAILABLE, create_desktop_window


def test_create_desktop_window_requires_pyside6_when_missing() -> None:
    if PYSIDE6_AVAILABLE:
        pytest.skip("PySide6 está instalada en este entorno.")

    with pytest.raises(RuntimeError, match="PySide6"):
        create_desktop_window()
