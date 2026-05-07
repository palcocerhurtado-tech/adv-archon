"""Tests for the diagnostic checker module."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_diagnostico_item_fields() -> None:
    from adv_archon.desktop.diagnostico import DiagnosticoItem

    item = DiagnosticoItem(
        clave="test", nombre="Test", descripcion="Desc.", ok=True, detalle="OK"
    )
    assert item.clave == "test"
    assert item.ok is True
    assert item.accion == ""


def test_check_uv_found(monkeypatch) -> None:
    from adv_archon.desktop import diagnostico as m

    monkeypatch.setattr(m.shutil, "which", lambda _: "/usr/local/bin/uv")
    item = m._check_uv()
    assert item.ok is True
    assert "/usr/local/bin/uv" in item.detalle


def test_check_uv_missing(monkeypatch) -> None:
    from adv_archon.desktop import diagnostico as m

    monkeypatch.setattr(m.shutil, "which", lambda _: None)
    item = m._check_uv()
    assert item.ok is False
    assert item.accion != ""


def test_check_venv_no_python(monkeypatch) -> None:
    from adv_archon.desktop import diagnostico as m

    monkeypatch.setattr(m, "_venv_python", lambda: None)
    item = m._check_venv()
    assert item.ok is False
    assert "uv sync" in item.accion


def test_check_venv_ok(monkeypatch, tmp_path) -> None:
    from adv_archon.desktop import diagnostico as m

    fake_python = tmp_path / "python"
    fake_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(m, "_venv_python", lambda: fake_python)

    fake_result = MagicMock()
    fake_result.returncode = 0
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **kw: fake_result)

    item = m._check_venv()
    assert item.ok is True


def test_check_venv_bad_imports(monkeypatch, tmp_path) -> None:
    from adv_archon.desktop import diagnostico as m

    fake_python = tmp_path / "python"
    fake_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(m, "_venv_python", lambda: fake_python)

    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stderr = "ModuleNotFoundError: No module named 'dotenv.main'"
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **kw: fake_result)

    item = m._check_venv()
    assert item.ok is False
    assert item.accion != ""


def test_check_ollama_ok(monkeypatch) -> None:
    from adv_archon.desktop import diagnostico as m

    fake_resp = MagicMock()
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = MagicMock(return_value=False)
    fake_resp.status = 200
    monkeypatch.setattr(m.urllib.request, "urlopen", lambda *a, **kw: fake_resp)

    item = m._check_ollama()
    assert item.ok is True


def test_check_ollama_unreachable(monkeypatch) -> None:
    from adv_archon.desktop import diagnostico as m

    monkeypatch.setattr(
        m.urllib.request, "urlopen",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("Connection refused")),
    )
    item = m._check_ollama()
    assert item.ok is False
    assert item.accion != ""


def test_check_db_ok(monkeypatch, tmp_path) -> None:
    from adv_archon.desktop import diagnostico as m

    monkeypatch.setenv("ADV_ARCHON_HOME", str(tmp_path))
    item = m._check_db()
    assert item.ok is True
    assert "expedientes.db" in item.detalle


def test_run_checks_returns_six_items() -> None:
    from adv_archon.desktop.diagnostico import DiagnosticoItem, run_checks
    from unittest.mock import patch

    fake = DiagnosticoItem(clave="x", nombre="X", descripcion="", ok=True)
    with (
        patch("adv_archon.desktop.diagnostico._check_uv", return_value=fake),
        patch("adv_archon.desktop.diagnostico._check_venv", return_value=fake),
        patch("adv_archon.desktop.diagnostico._check_pyside6", return_value=fake),
        patch("adv_archon.desktop.diagnostico._check_ollama", return_value=fake),
        patch("adv_archon.desktop.diagnostico._check_modelo", return_value=fake),
        patch("adv_archon.desktop.diagnostico._check_db", return_value=fake),
    ):
        items = run_checks()
    assert len(items) == 6
    assert all(isinstance(i, DiagnosticoItem) for i in items)


def test_repair_environment_calls_uv(monkeypatch, tmp_path) -> None:
    from adv_archon.desktop import diagnostico as m

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # type: ignore[misc]
        calls.append(cmd)
        r = MagicMock()
        r.returncode = 0
        r.stdout = ""
        r.stderr = ""
        return r

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    monkeypatch.setattr(m.shutil, "which", lambda _: "/usr/local/bin/uv")

    ok, _ = m.repair_environment(project_root=tmp_path)
    assert ok is True
    assert calls
    flat = " ".join(calls[0])
    assert "uv" in flat
    assert "sync" in flat
    assert "--reinstall-package" in flat
    assert "python-dotenv" in flat
    assert "PySide6" in flat


def test_desktop_stylesheet_marble_tokens() -> None:
    """Marble temple: new tokens present, brand palette intact."""
    from adv_archon.desktop.branding import desktop_stylesheet

    sheet = desktop_stylesheet()
    # Obsidian structure
    assert "#050505" in sheet   # BG / OBSIDIAN
    # Marble field
    assert "#F7F7F4" in sheet   # MARBLE_BG / TEXT
    # Brand
    assert "#B8B6AE" in sheet   # TEXT_SUB
    assert "#2E2E2C" in sheet   # SURFACE_HIGH / BORDER
    assert "#C9A227" in sheet   # ACCENT gold
    assert "Libre Baskerville" in sheet
    assert "Inter" in sheet
    # Marble panel
    assert "#FFFFFF" in sheet   # MARBLE_PANEL
