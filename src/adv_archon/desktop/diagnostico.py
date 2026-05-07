# mypy: ignore-errors
"""Comprobador de entorno ADV ARCHON.

Uso:
  - Diálogo Qt:  show_diagnostico_dialog(parent, model="qwen2.5:7b")
  - CLI:         python -m adv_archon.desktop.diagnostico
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# ── Checks ────────────────────────────────────────────────────────────────────

@dataclass
class DiagnosticoItem:
    clave: str
    nombre: str
    descripcion: str
    ok: bool
    detalle: str = ""
    accion: str = ""


def _project_root() -> Path:
    try:
        from adv_archon.core.config import PACKAGE_ROOT
        candidate = PACKAGE_ROOT.parent.parent.parent
        if (candidate / "pyproject.toml").exists():
            return candidate
    except Exception:
        pass
    return Path(__file__).parent.parent.parent.parent


def _venv_python() -> Path | None:
    root = _project_root()
    for p in (root / ".venv" / "bin" / "python", root / ".venv" / "Scripts" / "python.exe"):
        if p.exists():
            return p
    return None


def _check_uv() -> DiagnosticoItem:
    found = shutil.which("uv")
    return DiagnosticoItem(
        clave="uv",
        nombre="uv (gestor de entornos)",
        descripcion="Gestiona el entorno Python y las dependencias de la app.",
        ok=bool(found),
        detalle=f"Encontrado en {found}" if found else "No se encontró uv en el PATH.",
        accion="" if found else "Instala uv: https://docs.astral.sh/uv/getting-started/installation/",
    )


def _check_venv() -> DiagnosticoItem:
    python = _venv_python()
    if python is None:
        return DiagnosticoItem(
            clave="venv",
            nombre="Entorno Python (.venv)",
            descripcion="Entorno virtual con todas las dependencias de la app.",
            ok=False,
            detalle="No se encontró .venv/bin/python.",
            accion="Ejecuta: uv sync --extra desktop",
        )
    try:
        r = subprocess.run(
            [str(python), "-c", "import dotenv.main; import pygments.formatters; print('ok')"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return DiagnosticoItem(
                clave="venv",
                nombre="Entorno Python (.venv)",
                descripcion="Entorno virtual con todas las dependencias de la app.",
                ok=True, detalle="Importaciones críticas: OK",
            )
        last_err = (r.stderr or "").strip().split("\n")[-1]
        return DiagnosticoItem(
            clave="venv",
            nombre="Entorno Python (.venv)",
            descripcion="Entorno virtual con todas las dependencias de la app.",
            ok=False,
            detalle=f"Importación fallida: {last_err[:120]}",
            accion="El comprobador puede repararlo automáticamente.",
        )
    except Exception as exc:
        return DiagnosticoItem(
            clave="venv", nombre="Entorno Python (.venv)",
            descripcion="Entorno virtual con todas las dependencias de la app.",
            ok=False, detalle=str(exc)[:120],
            accion="El comprobador puede repararlo automáticamente.",
        )


def _check_pyside6() -> DiagnosticoItem:
    python = _venv_python()
    if python is None:
        return DiagnosticoItem(
            clave="pyside6", nombre="PySide6 (interfaz gráfica)",
            descripcion="Biblioteca que dibuja la interfaz visual.",
            ok=False, detalle="Revisar entorno primero.",
        )
    try:
        r = subprocess.run(
            [str(python), "-c",
             "from PySide6.QtWidgets import QApplication;"
             "a=QApplication.instance() or QApplication([]);print('ok')"],
            capture_output=True, text=True, timeout=20,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        )
        if r.returncode == 0:
            return DiagnosticoItem(
                clave="pyside6", nombre="PySide6 (interfaz gráfica)",
                descripcion="Biblioteca que dibuja la interfaz visual.",
                ok=True, detalle="QApplication: OK",
            )
        last_err = (r.stderr or r.stdout or "").strip().split("\n")[-1]
        return DiagnosticoItem(
            clave="pyside6", nombre="PySide6 (interfaz gráfica)",
            descripcion="Biblioteca que dibuja la interfaz visual.",
            ok=False, detalle=last_err[:120],
            accion="El comprobador puede reinstalar PySide6 automáticamente.",
        )
    except Exception as exc:
        return DiagnosticoItem(
            clave="pyside6", nombre="PySide6 (interfaz gráfica)",
            descripcion="Biblioteca que dibuja la interfaz visual.",
            ok=False, detalle=str(exc)[:120],
            accion="El comprobador puede reinstalar PySide6 automáticamente.",
        )


def _check_ollama() -> DiagnosticoItem:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as resp:
            if resp.status == 200:
                return DiagnosticoItem(
                    clave="ollama", nombre="Ollama (motor de IA local)",
                    descripcion="Servidor local que ejecuta el modelo de inteligencia artificial.",
                    ok=True, detalle="Ollama responde en localhost:11434",
                )
    except Exception as exc:
        return DiagnosticoItem(
            clave="ollama", nombre="Ollama (motor de IA local)",
            descripcion="Servidor local que ejecuta el modelo de inteligencia artificial.",
            ok=False, detalle=f"No responde: {str(exc)[:80]}",
            accion="Abre Ollama.app o ejecuta: ollama serve",
        )
    return DiagnosticoItem(
        clave="ollama", nombre="Ollama (motor de IA local)",
        descripcion="Servidor local que ejecuta el modelo de inteligencia artificial.",
        ok=False, detalle="Respuesta inesperada.",
        accion="Reinicia Ollama y vuelve a intentarlo.",
    )


def _check_modelo(model: str) -> DiagnosticoItem:
    import json as _json
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as resp:
            data = _json.loads(resp.read())
        names = [m.get("name", "") for m in data.get("models", [])]
        base = model.split(":")[0]
        matched = next((n for n in names if n == model or n.startswith(base)), None)
        if matched:
            return DiagnosticoItem(
                clave="modelo", nombre=f"Modelo IA ({model})",
                descripcion="Modelo de lenguaje para análisis urbanístico.",
                ok=True, detalle=f"Encontrado: {matched}",
            )
        avail = ", ".join(names[:4]) or "ninguno"
        return DiagnosticoItem(
            clave="modelo", nombre=f"Modelo IA ({model})",
            descripcion="Modelo de lenguaje para análisis urbanístico.",
            ok=False, detalle=f"'{model}' no instalado. Disponibles: {avail}",
            accion=f"Ejecuta en terminal: ollama pull {model}",
        )
    except Exception:
        return DiagnosticoItem(
            clave="modelo", nombre=f"Modelo IA ({model})",
            descripcion="Modelo de lenguaje para análisis urbanístico.",
            ok=False, detalle="No se pudo consultar Ollama (ver check anterior).",
            accion="Asegúrate primero de que Ollama está activo.",
        )


def _check_db() -> DiagnosticoItem:
    data_dir = Path(os.getenv("ADV_ARCHON_HOME", str(Path.home() / ".adv-archon")))
    db_path = data_dir / "expedientes.db"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT 1")
        conn.close()
        return DiagnosticoItem(
            clave="db", nombre="Base de datos (expedientes)",
            descripcion="Almacén local de expedientes urbanísticos.",
            ok=True, detalle=f"Accesible: {db_path}",
        )
    except Exception as exc:
        return DiagnosticoItem(
            clave="db", nombre="Base de datos (expedientes)",
            descripcion="Almacén local de expedientes urbanísticos.",
            ok=False, detalle=str(exc)[:100],
            accion=f"Verifica permisos en: {data_dir}",
        )


def run_checks(model: str = "qwen2.5:7b") -> list[DiagnosticoItem]:
    """Run all checks. Pure Python — no Qt required."""
    return [
        _check_uv(),
        _check_venv(),
        _check_pyside6(),
        _check_ollama(),
        _check_modelo(model),
        _check_db(),
    ]


def repair_environment(project_root: Path | None = None) -> tuple[bool, str]:
    """Reinstall critical packages via uv. Returns (success, output)."""
    root = project_root or _project_root()
    uv = shutil.which("uv") or "uv"
    cmd = [
        uv, "sync", "--extra", "desktop",
        "--reinstall-package", "python-dotenv",
        "--reinstall-package", "PySide6",
        "--reinstall-package", "PySide6-Addons",
        "--reinstall-package", "PySide6-Essentials",
        "--reinstall-package", "shiboken6",
    ]
    try:
        r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=300)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as exc:
        return False, str(exc)


# ── Qt dialog ─────────────────────────────────────────────────────────────────

def show_diagnostico_dialog(
    parent: object = None,
    model: str = "qwen2.5:7b",
    project_root: Path | None = None,
) -> None:
    """Show the diagnostic dialog. Requires PySide6."""
    from PySide6.QtCore import QObject, QThread
    from PySide6.QtCore import Signal as _Signal
    from PySide6.QtWidgets import (
        QDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    from adv_archon.desktop.branding import (
        ACCENT,
        ERR,
        FONT_DISPLAY,
        FONT_SEAL,
        MARBLE_BG,
        MARBLE_BORDER,
        MARBLE_PANEL,
        OBSIDIAN,
        OK,
        TEXT,
        TEXT_SUB,
        WARN,
        desktop_stylesheet,
    )

    class _CheckWorker(QObject):
        finished = _Signal(list)

        def run(self) -> None:
            self.finished.emit(run_checks(model=model))

    class _RepairWorker(QObject):
        finished = _Signal(bool, str)

        def run(self) -> None:
            ok, out = repair_environment(project_root)
            self.finished.emit(ok, out)

    dlg = QDialog(parent)  # type: ignore[arg-type]
    dlg.setWindowTitle("Comprobador de entorno — ADV ARCHON")
    dlg.setMinimumWidth(580)
    dlg.setMinimumHeight(500)
    dlg.setStyleSheet(desktop_stylesheet())

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    # ── Header (obsidian) ────────────────────────────────────────────────────
    header = QFrame()
    header.setStyleSheet(
        f"QFrame {{ background: {OBSIDIAN}; border-bottom: 1px solid #1C1C1A; }}"
    )
    hl = QHBoxLayout(header)
    hl.setContentsMargins(22, 16, 22, 16)
    title_lbl = QLabel("Comprobador de entorno")
    title_lbl.setStyleSheet(
        f"font-family: {FONT_DISPLAY}; font-size: 17px; font-weight: 700;"
        f" color: {TEXT}; background: transparent;"
    )
    badge_lbl = QLabel("ADV ARCHON")
    badge_lbl.setStyleSheet(
        f"font-family: {FONT_SEAL}; font-size: 10px; color: {ACCENT};"
        f" letter-spacing: 0.14em; background: transparent;"
    )
    hl.addWidget(title_lbl)
    hl.addStretch()
    hl.addWidget(badge_lbl)
    outer.addWidget(header)

    # ── Body (marble) ────────────────────────────────────────────────────────
    body = QWidget()
    body.setStyleSheet(f"background: {MARBLE_BG};")
    bl = QVBoxLayout(body)
    bl.setContentsMargins(22, 18, 22, 18)
    bl.setSpacing(12)

    status_lbl = QLabel("Ejecutando comprobaciones…")
    status_lbl.setStyleSheet(f"color: {TEXT_SUB}; font-size: 12px; background: transparent;")
    bl.addWidget(status_lbl)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    results_container = QWidget()
    results_container.setStyleSheet("background: transparent;")
    results_layout = QVBoxLayout(results_container)
    results_layout.setContentsMargins(0, 0, 0, 0)
    results_layout.setSpacing(6)
    results_layout.addStretch()
    scroll.setWidget(results_container)
    bl.addWidget(scroll, 1)

    action_row = QHBoxLayout()
    repair_btn = QPushButton("Reparar entorno")
    repair_btn.setObjectName("Primary")
    repair_btn.setVisible(False)
    recheck_btn = QPushButton("Volver a comprobar")
    recheck_btn.setVisible(False)
    close_btn = QPushButton("Cerrar")
    close_btn.setObjectName("Ghost")
    close_btn.clicked.connect(dlg.accept)
    action_row.addWidget(repair_btn)
    action_row.addWidget(recheck_btn)
    action_row.addStretch()
    action_row.addWidget(close_btn)
    bl.addLayout(action_row)

    outer.addWidget(body, 1)

    _threads: list[tuple[QThread, QObject]] = []

    def _add_row(item: DiagnosticoItem) -> None:
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background: {MARBLE_PANEL}; border: 1px solid {MARBLE_BORDER};"
            " border-radius: 10px; }"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 11, 14, 11)
        rl.setSpacing(12)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {OK if item.ok else ERR}; font-size: 14px;"
            " background: transparent; border: none;"
        )
        dot.setFixedWidth(18)
        rl.addWidget(dot)

        col = QVBoxLayout()
        col.setSpacing(3)
        name = QLabel(item.nombre)
        name.setStyleSheet(
            "font-weight: 700; font-size: 13px; color: #050505;"
            " background: transparent; border: none;"
        )
        col.addWidget(name)
        if item.detalle:
            det = QLabel(item.detalle)
            det.setStyleSheet(
                f"font-size: 11px; color: {TEXT_SUB}; background: transparent; border: none;"
            )
            det.setWordWrap(True)
            col.addWidget(det)
        if item.accion and not item.ok:
            act = QLabel(item.accion)
            act.setStyleSheet(
                f"font-size: 11px; color: {ACCENT}; background: transparent; border: none;"
            )
            act.setWordWrap(True)
            col.addWidget(act)
        rl.addLayout(col, 1)

        idx = results_layout.count() - 1  # before trailing stretch
        results_layout.insertWidget(idx, row)

    def _clear_rows() -> None:
        while results_layout.count() > 1:
            item = results_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _on_checks_done(items: list) -> None:
        _clear_rows()
        for it in items:
            _add_row(it)
        all_ok = all(it.ok for it in items)
        if all_ok:
            status_lbl.setText("✓ Todo listo — ADV ARCHON está en perfectas condiciones.")
            status_lbl.setStyleSheet(
                f"color: {OK}; font-size: 13px; font-weight: 600; background: transparent;"
            )
        else:
            n = sum(1 for it in items if not it.ok)
            status_lbl.setText(f"{n} comprobación(es) requieren atención.")
            status_lbl.setStyleSheet(
                f"color: {ERR}; font-size: 13px; font-weight: 600; background: transparent;"
            )
        repair_btn.setVisible(not all_ok)
        recheck_btn.setVisible(True)
        _threads.clear()

    def _run_checks() -> None:
        status_lbl.setText("Ejecutando comprobaciones…")
        status_lbl.setStyleSheet(
            f"color: {TEXT_SUB}; font-size: 12px; background: transparent;"
        )
        repair_btn.setVisible(False)
        recheck_btn.setVisible(False)
        _clear_rows()
        thread = QThread(dlg)
        worker = _CheckWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(_on_checks_done)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        _threads.append((thread, worker))
        thread.start()

    def _on_repair_done(ok: bool, out: str) -> None:
        if ok:
            status_lbl.setText("Reparación completada. Volviendo a comprobar…")
            status_lbl.setStyleSheet(
                f"color: {ACCENT}; font-size: 12px; background: transparent;"
            )
        else:
            snippet = out[:80] if out else "error desconocido"
            status_lbl.setText(f"Reparación con errores: {snippet}")
            status_lbl.setStyleSheet(
                f"color: {ERR}; font-size: 12px; background: transparent;"
            )
        repair_btn.setEnabled(True)
        _threads.clear()
        _run_checks()

    def _repair() -> None:
        repair_btn.setEnabled(False)
        status_lbl.setText("Reparando entorno… (puede tardar hasta 2 minutos)")
        status_lbl.setStyleSheet(
            f"color: {WARN}; font-size: 12px; background: transparent;"
        )
        thread = QThread(dlg)
        worker = _RepairWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(_on_repair_done)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        _threads.append((thread, worker))
        thread.start()

    repair_btn.clicked.connect(_repair)
    recheck_btn.clicked.connect(_run_checks)
    _run_checks()
    dlg.exec()


# ── CLI fallback ──────────────────────────────────────────────────────────────

def _cli_main() -> None:
    import sys as _sys
    model = _sys.argv[1] if len(_sys.argv) > 1 else "qwen2.5:7b"
    print(f"\nADV ARCHON — Comprobador de entorno (modelo: {model})\n{'─'*52}")
    items = run_checks(model=model)
    for it in items:
        mark = "✓" if it.ok else "✗"
        print(f"  {mark}  {it.nombre}")
        if it.detalle:
            print(f"       {it.detalle}")
        if it.accion and not it.ok:
            print(f"       → {it.accion}")
    print("─" * 52)
    all_ok = all(it.ok for it in items)
    if all_ok:
        print("  Todo listo.\n")
    else:
        failed = sum(1 for it in items if not it.ok)
        print(f"  {failed} comprobación(es) requieren atención.\n")
    _sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    _cli_main()
