"""
Expediente panel — PySide6 widgets for the case management flow.

Provides:
  ExpedienteListPanel  — sidebar with list of expedientes + New button
  NewExpedienteDialog  — modal form to create a new expediente
  ExpedienteDetailPanel— main panel showing resolved site data for one expediente
"""
from __future__ import annotations

import json
from html import escape
from importlib.util import find_spec
from pathlib import Path
from typing import Any, cast

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

Qt: Any = None
QDialog: Any = None
QDialogButtonBox: Any = None
QFileDialog: Any = None
QFormLayout: Any = None
QFrame: Any = None
QHBoxLayout: Any = None
QIcon: Any = None
QLabel: Any = None
QLineEdit: Any = None
QListWidget: Any = None
QListWidgetItem: Any = None
QMessageBox: Any = None
QPushButton: Any = None
QScrollArea: Any = None
QSizePolicy: Any = None
QTextBrowser: Any = None
QVBoxLayout: Any = None
QWidget: Any = None

if PYSIDE6_AVAILABLE:
    from importlib import import_module
    _c = import_module("PySide6.QtCore")
    _g = import_module("PySide6.QtGui")
    _w = import_module("PySide6.QtWidgets")
    Qt = _c.Qt
    QIcon = _g.QIcon
    QDialog = _w.QDialog
    QDialogButtonBox = _w.QDialogButtonBox
    QFileDialog = _w.QFileDialog
    QFormLayout = _w.QFormLayout
    QFrame = _w.QFrame
    QHBoxLayout = _w.QHBoxLayout
    QLabel = _w.QLabel
    QLineEdit = _w.QLineEdit
    QListWidget = _w.QListWidget
    QListWidgetItem = _w.QListWidgetItem
    QMessageBox = _w.QMessageBox
    QPushButton = _w.QPushButton
    QScrollArea = _w.QScrollArea
    QSizePolicy = _w.QSizePolicy
    QTextBrowser = _w.QTextBrowser
    QVBoxLayout = _w.QVBoxLayout
    QWidget = _w.QWidget


# ── Status colours / labels ───────────────────────────────────────────────────

_STATUS_COLOUR = {
    "borrador":          "#888888",
    "geocodificando":    "#1565C0",
    "geocodificado":     "#00796B",
    "analizando":        "#1565C0",
    "analizado":         "#2979FF",
    "informe_generado":  "#2E7D32",
    "informe_listo":     "#2E7D32",
    "requiere_revision": "#E65100",
    "error":             "#C62828",
}

_STATUS_LABEL = {
    "borrador":          "Borrador",
    "geocodificando":    "Geocodificando…",
    "geocodificado":     "Ubicación resuelta",
    "analizando":        "Analizando…",
    "analizado":         "Analizado",
    "informe_generado":  "Informe generado",
    "informe_listo":     "Informe listo",
    "requiere_revision": "Requiere revisión",
    "error":             "Error",
}

_DISCLAIMER = (
    "<p style='color:#777;font-size:10px;margin-top:12px;'>"
    "⚠ Análisis preliminar de ADV ARCHON — no vinculante jurídicamente. "
    "Verifique siempre con el PGOU municipal vigente y con técnico competente."
    "</p>"
)

# ── Veredicto derivado del panel de checks ────────────────────────────────────

def _veredicto_from_checks(checks: list[dict[str, Any]]) -> tuple[str, str]:
    """Return (label, colour) VIABLE / CONDICIONADO / REVISAR."""
    if not checks:
        return "", ""
    statuses = [c.get("status", "") for c in checks]
    if any(s == "missing" for s in statuses):
        return "REVISAR", "#C62828"
    if any(s in ("conditional", "pending_review") for s in statuses):
        return "CONDICIONADO", "#E65100"
    if all(s in ("ready", "not_applicable") for s in statuses):
        return "VIABLE", "#2E7D32"
    return "CONDICIONADO", "#E65100"


if PYSIDE6_AVAILABLE:

    # ── List panel ────────────────────────────────────────────────────────────

    class ExpedienteListPanel(QWidget):  # type: ignore[misc]
        """Left sidebar: list of expedientes + New / Delete buttons."""

        def __init__(
            self,
            *,
            on_select: Any = None,
            on_new: Any = None,
            on_delete: Any = None,
        ) -> None:
            super().__init__()
            self._on_select = on_select
            self._on_new = on_new
            self._on_delete = on_delete

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)

            header = QLabel("Expedientes")
            header.setStyleSheet("font-weight: bold; font-size: 13px; padding: 6px 8px;")
            layout.addWidget(header)

            self._list = QListWidget()
            self._list.setAlternatingRowColors(True)
            self._list.currentItemChanged.connect(self._on_item_changed)
            layout.addWidget(self._list)

            btn_row = QHBoxLayout()
            new_btn = QPushButton("+ Nuevo")
            new_btn.setToolTip("Crear nuevo expediente")
            new_btn.clicked.connect(self._on_new_clicked)
            btn_row.addWidget(new_btn)

            del_btn = QPushButton("Eliminar")
            del_btn.setToolTip("Eliminar expediente seleccionado")
            del_btn.clicked.connect(self._on_delete_clicked)
            btn_row.addWidget(del_btn)
            layout.addLayout(btn_row)

            self.setMinimumWidth(200)
            self.setMaximumWidth(280)

        def populate(self, expedientes: list[Any]) -> None:
            self._list.clear()
            for exp in expedientes:
                label = _STATUS_LABEL.get(exp.status, exp.status)
                item = QListWidgetItem(f"{exp.title}\n{exp.municipality or exp.address[:30]}")
                item.setData(Qt.ItemDataRole.UserRole, exp.id)
                item.setToolTip(f"Estado: {label}  |  {exp.created_at[:10]}")
                self._list.addItem(item)

        def selected_id(self) -> str | None:
            item = self._list.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item else None

        def _on_item_changed(self, current: Any, _previous: Any) -> None:
            if current and self._on_select:
                self._on_select(current.data(Qt.ItemDataRole.UserRole))

        def _on_new_clicked(self) -> None:
            if self._on_new:
                self._on_new()

        def _on_delete_clicked(self) -> None:
            eid = self.selected_id()
            if eid and self._on_delete:
                self._on_delete(eid)

    # ── New expediente dialog ─────────────────────────────────────────────────

    class NewExpedienteDialog(QDialog):  # type: ignore[misc]
        """Modal form to enter basic expediente data before geo-resolution."""

        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("Nuevo Expediente")
            self.setMinimumWidth(460)

            layout = QVBoxLayout(self)

            form = QFormLayout()
            self._title = QLineEdit()
            self._title.setPlaceholderText("Ej: Reforma local calle Mayor 12")
            form.addRow("Nombre del expediente *", self._title)

            self._address = QLineEdit()
            self._address.setPlaceholderText(
                "Ej: Calle Gran Vía 1, Madrid, 40.4168, -3.7038 o ref. catastral"
            )
            form.addRow("Dirección, coordenadas o referencia *", self._address)

            self._notes = QLineEdit()
            self._notes.setPlaceholderText("Opcional")
            form.addRow("Notas", self._notes)

            layout.addLayout(form)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(self._on_accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def _on_accept(self) -> None:
            if not self._title.text().strip():
                QMessageBox.warning(
                    self, "Campo requerido", "El nombre del expediente es obligatorio."
                )
                return
            if not self._address.text().strip():
                QMessageBox.warning(
                    self,
                    "Campo requerido",
                    "La dirección, coordenadas o referencia son obligatorias.",
                )
                return
            self.accept()

        def title_text(self) -> str:
            return cast(str, self._title.text()).strip()

        def address_text(self) -> str:
            return cast(str, self._address.text()).strip()

        def notes_text(self) -> str:
            return cast(str, self._notes.text()).strip()

    # ── Detail panel ──────────────────────────────────────────────────────────

    class ExpedienteDetailPanel(QWidget):  # type: ignore[misc]
        """Right panel: shows site context, plan attachment, actions."""

        def __init__(
            self,
            *,
            on_attach_plan: Any = None,
            on_analyze: Any = None,
            on_export: Any = None,
        ) -> None:
            super().__init__()
            self._on_attach_plan = on_attach_plan
            self._on_analyze = on_analyze
            self._on_export = on_export
            self._expediente_id: str | None = None
            self._expediente: Any = None

            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 8, 12, 8)
            layout.setSpacing(8)

            # Header
            self._title_label = QLabel("Selecciona o crea un expediente")
            self._title_label.setStyleSheet("font-weight: bold; font-size: 15px;")
            self._title_label.setWordWrap(True)
            layout.addWidget(self._title_label)

            self._status_label = QLabel("")
            self._status_label.setStyleSheet("font-size: 11px; color: #888;")
            layout.addWidget(self._status_label)

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            layout.addWidget(sep)

            # Site context display
            self._context_browser = QTextBrowser()
            self._context_browser.setOpenExternalLinks(False)
            self._context_browser.setMinimumHeight(240)
            layout.addWidget(self._context_browser)

            # Plano row
            plan_row = QHBoxLayout()
            self._plan_label = QLabel("Sin plano adjunto")
            self._plan_label.setStyleSheet("color: #888; font-size: 11px;")
            plan_row.addWidget(self._plan_label)
            plan_row.addStretch()
            attach_btn = QPushButton("Adjuntar plano…")
            attach_btn.setToolTip("Adjuntar el plano arquitectónico (PDF, DWG, PNG…)")
            attach_btn.clicked.connect(self._on_attach_clicked)
            plan_row.addWidget(attach_btn)
            layout.addLayout(plan_row)

            # Action buttons
            btn_row = QHBoxLayout()
            self._analyze_btn = QPushButton("Analizar con PGOU")
            self._set_brand_icon(self._analyze_btn)
            self._analyze_btn.setEnabled(False)
            self._analyze_btn.setToolTip(
                "Enviar el plano al agente ARCHON para análisis de cumplimiento"
            )
            self._analyze_btn.setStyleSheet(
                "background:#1565C0; color:white;"
                " padding:6px 16px; border-radius:4px;"
            )
            self._analyze_btn.clicked.connect(self._on_analyze_clicked)
            btn_row.addWidget(self._analyze_btn)

            self._export_btn = QPushButton("Exportar informe PDF")
            self._set_brand_icon(self._export_btn)
            self._export_btn.setEnabled(False)
            self._export_btn.setToolTip(
                "Generar informe PDF profesional con todos los datos del expediente"
            )
            self._export_btn.clicked.connect(self._on_export_clicked)
            btn_row.addWidget(self._export_btn)

            self._open_report_btn = QPushButton("Abrir informe")
            self._open_report_btn.setEnabled(False)
            self._open_report_btn.setVisible(False)
            self._open_report_btn.setToolTip("Abrir el informe PDF generado")
            self._open_report_btn.setStyleSheet(
                "background:#2E7D32; color:white;"
                " padding:6px 14px; border-radius:4px;"
            )
            self._open_report_btn.clicked.connect(self._on_open_report_clicked)
            btn_row.addWidget(self._open_report_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

        def _set_brand_icon(self, button: Any) -> None:
            try:
                from adv_archon.desktop.branding import logo_path
                icon_path = logo_path()
                if icon_path.exists():
                    button.setIcon(QIcon(str(icon_path)))
            except Exception:
                return

        def load_expediente(self, exp: Any) -> None:
            """Populate the panel with data from an Expediente."""
            self._expediente_id = exp.id
            self._expediente = exp
            self._title_label.setText(exp.title)
            colour = _STATUS_COLOUR.get(exp.status, "#888")
            label = _STATUS_LABEL.get(exp.status, exp.status)
            self._status_label.setText(
                f"<span style='color:{colour}'>● {label}</span>"
                f"  ·  {exp.municipality or '—'}"
                f"  ·  {exp.created_at[:10]}"
            )
            self._status_label.setTextFormat(Qt.TextFormat.RichText)

            if exp.plan_path:
                self._plan_label.setText(f"Plano: {Path(exp.plan_path).name}")
                self._plan_label.setStyleSheet("color: #333; font-size: 11px;")
            else:
                self._plan_label.setText("Sin plano adjunto — adjunta el plano antes de analizar")
                self._plan_label.setStyleSheet("color: #888; font-size: 11px;")

            self._context_browser.setHtml(self._render_context(exp))
            can_analyze = bool(exp.plan_path) and bool(exp.municipality or exp.latitude)
            self._analyze_btn.setEnabled(can_analyze)
            exportable = exp.status in (
                "analizado", "informe_listo", "informe_generado"
            )
            self._export_btn.setEnabled(exportable)
            has_report = bool(exp.report_path) and Path(exp.report_path).exists()
            self._open_report_btn.setEnabled(has_report)
            self._open_report_btn.setVisible(has_report)

        def _render_context(self, exp: Any) -> str:  # noqa: C901
            style = (
                "<style>"
                "td{padding:3px 8px;}"
                "th{text-align:left;color:#555;font-size:11px;}"
                "h4{margin:8px 0 4px 0;color:#333;font-size:12px;}"
                "</style>"
            )
            lines: list[str] = [style]

            # ── Paso 1: Ubicación ─────────────────────────────────────────
            if not exp.municipality and not exp.site_context:
                lines.append(
                    "<h4>📍 Ubicación</h4>"
                    "<p style='color:#888;'>Aún sin resolver. "
                    "Crea el expediente con una dirección o coordenadas GPS y "
                    "ARCHON resolverá la parcela automáticamente.</p>"
                )
                lines.append(_DISCLAIMER)
                return "".join(lines)

            lines.append(
                f"<h4>📍 Ubicación</h4><p><b>{escape(str(exp.address))}</b></p>"
            )
            if exp.municipality:
                lines.append(
                    f"<p>{escape(str(exp.municipality))},"
                    f" {escape(str(exp.province))}</p>"
                )

            # ── Paso 2: Parcela catastral ─────────────────────────────────
            parcel_shown = False
            if exp.cadastral_ref:
                lines.append(
                    f"<h4>🏠 Parcela catastral</h4>"
                    f"<p style='font-size:11px;'>Ref: {exp.cadastral_ref}</p>"
                )
                parcel_shown = True

            if exp.site_context:
                try:
                    ctx = json.loads(exp.site_context)
                    pd = ctx.get("parcel_detail") or {}
                    if isinstance(pd, dict) and not pd.get("error"):
                        if not parcel_shown:
                            lines.append("<h4>🏠 Parcela catastral</h4>")
                        items = []
                        if pd.get("surface_m2"):
                            items.append(f"Superficie: {pd['surface_m2']} m²")
                        if pd.get("construction_year"):
                            items.append(f"Año: {pd['construction_year']}")
                        if pd.get("floors_above") is not None:
                            items.append(f"Plantas: {pd['floors_above']}")
                        if pd.get("use_detail"):
                            items.append(f"Uso: {pd['use_detail']}")
                        if items:
                            lines.append(
                                "<p style='font-size:11px;color:#444;'>"
                                + " · ".join(items) + "</p>"
                            )
                except (json.JSONDecodeError, TypeError):
                    pass

            # ── Paso 3: Afecciones sectoriales ────────────────────────────
            if exp.site_context:
                try:
                    ctx = json.loads(exp.site_context)
                    checks = ctx.get("legal_checks") or []
                    if checks:
                        verdict, v_colour = _veredicto_from_checks(checks)
                        if verdict:
                            lines.append(
                                f"<h4>⚖ Veredicto preliminar</h4>"
                                f"<p style='font-size:16px;font-weight:bold;"
                                f"color:{v_colour};'>{verdict}</p>"
                            )
                        lines.append("<h4>🗺 Afecciones sectoriales</h4><table>")
                        _icons = {
                            "ready": "✅", "conditional": "⚠️",
                            "pending_review": "🔍",
                            "not_applicable": "—", "missing": "❌",
                        }
                        for c in checks:
                            icon = _icons.get(c.get("status", ""), "·")
                            chk_name = escape(
                                str(c.get("name") or c.get("title") or "")
                            )
                            detail = escape(str(c.get("detail") or "")[:80])
                            lines.append(
                                f"<tr><td>{icon}</td>"
                                f"<td><b>{chk_name}</b></td>"
                                f"<td style='font-size:10px;color:#555;'>"
                                f"{detail}</td></tr>"
                            )
                        lines.append("</table>")
                        sources = ", ".join({
                            "Catastro OVC", "SNCZI/CNIG", "Natura 2000",
                            "SIGCOSTAS", "MITMA/IGN",
                        })
                        lines.append(
                            f"<p style='font-size:10px;color:#777;'>"
                            f"Fuentes: {sources}</p>"
                        )
                except (json.JSONDecodeError, TypeError):
                    pass

            # ── Paso 4: Análisis LLM ──────────────────────────────────────
            if exp.analysis_result:
                try:
                    ar = json.loads(exp.analysis_result)
                    summary = ar.get("summary", "")
                    if summary:
                        lines.append(
                            f"<h4>📋 Veredicto del análisis</h4>"
                            f"<p style='font-size:11px;'>"
                            f"{escape(str(summary)[:400])}</p>"
                        )
                except (json.JSONDecodeError, TypeError):
                    if isinstance(exp.analysis_result, str) and exp.analysis_result:
                        lines.append(
                            f"<h4>📋 Análisis</h4>"
                            f"<p style='font-size:11px;'>{exp.analysis_result[:400]}</p>"
                        )

            if exp.notes:
                lines.append(
                    "<hr><p style='color:#555;font-size:11px;'>"
                    f"Notas: {escape(str(exp.notes))}</p>"
                )

            lines.append(_DISCLAIMER)
            return "".join(lines)

        def clear(self) -> None:
            self._expediente_id = None
            self._expediente = None
            self._title_label.setText("Selecciona o crea un expediente")
            self._status_label.setText("")
            self._context_browser.clear()
            self._analyze_btn.setEnabled(False)
            self._export_btn.setEnabled(False)
            self._open_report_btn.setEnabled(False)
            self._open_report_btn.setVisible(False)

        def _on_attach_clicked(self) -> None:
            if not self._expediente_id:
                QMessageBox.information(
                    self, "Sin expediente",
                    "Selecciona o crea un expediente primero."
                )
                return
            if self._on_attach_plan:
                self._on_attach_plan(self._expediente_id)

        def _on_analyze_clicked(self) -> None:
            if self._on_analyze and self._expediente_id:
                self._on_analyze(self._expediente_id)

        def _on_export_clicked(self) -> None:
            if self._on_export and self._expediente_id:
                self._on_export(self._expediente_id)

        def _on_open_report_clicked(self) -> None:
            import subprocess
            if self._expediente and self._expediente.report_path:
                subprocess.Popen(["open", str(self._expediente.report_path)])


else:
    # Stubs for environments without PySide6 (tests, CI)
    class ExpedienteListPanel:  # type: ignore[no-redef]
        def __init__(self, **_kw: Any) -> None:
            raise RuntimeError("PySide6 no está instalada.")

    class NewExpedienteDialog:  # type: ignore[no-redef]
        def __init__(self, *_a: Any, **_kw: Any) -> None:
            raise RuntimeError("PySide6 no está instalada.")

    class ExpedienteDetailPanel:  # type: ignore[no-redef]
        def __init__(self, **_kw: Any) -> None:
            raise RuntimeError("PySide6 no está instalada.")
