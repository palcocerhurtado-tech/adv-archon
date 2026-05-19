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

from adv_archon.desktop.branding import ACCENT, BG, ERR, OK, TEXT_FAINT, TEXT_SUB, WARN

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

Qt: Any = None
QDialog: Any = None
QDialogButtonBox: Any = None
QDesktopServices: Any = None
QComboBox: Any = None
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
QProgressBar: Any = None
QUrl: Any = None
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
    QUrl = _c.QUrl
    QDesktopServices = _g.QDesktopServices
    QIcon = _g.QIcon
    QComboBox = _w.QComboBox
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
    QProgressBar = _w.QProgressBar
    QScrollArea = _w.QScrollArea
    QSizePolicy = _w.QSizePolicy
    QTextBrowser = _w.QTextBrowser
    QVBoxLayout = _w.QVBoxLayout
    QWidget = _w.QWidget


# ── Status colours / labels ───────────────────────────────────────────────────

_STATUS_COLOUR = {
    "borrador":          TEXT_FAINT,
    "geocodificando":    ACCENT,
    "geocodificado":     OK,
    "analizando":        ACCENT,
    "analizado":         ACCENT,
    "informe_generado":  OK,
    "informe_listo":     OK,
    "requiere_revision": WARN,
    "error":             ERR,
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
    f"<p style='color:{TEXT_FAINT};font-size:10px;margin-top:12px;'>"
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
        return "REVISAR", ERR
    if any(s in ("conditional", "pending_review") for s in statuses):
        return "CONDICIONADO", WARN
    if all(s in ("ready", "not_applicable") for s in statuses):
        return "VIABLE", OK
    return "CONDICIONADO", WARN


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
            self.setWindowTitle("Nuevo expediente guiado")
            self.setMinimumWidth(620)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(12)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QVBoxLayout(hero)
            hero_lay.setContentsMargins(16, 14, 16, 14)
            hero_lay.setSpacing(6)
            eyebrow = QLabel("FLUJO DE EXPEDIENTE")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Nuevo expediente")
            title.setObjectName("StudioTitle")
            subtitle = QLabel(
                "Define el tipo de actuación, identifica la parcela y deja el "
                "expediente listo para plano, análisis e informe."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            hero_lay.addWidget(eyebrow)
            hero_lay.addWidget(title)
            hero_lay.addWidget(subtitle)
            layout.addWidget(hero)

            steps = QHBoxLayout()
            steps.setSpacing(8)
            for number, label in (
                ("1", "Tipo"),
                ("2", "Parcela"),
                ("3", "Plano"),
                ("4", "Análisis"),
                ("5", "Informe"),
            ):
                step = QFrame()
                step.setObjectName("StudioMetric")
                step_lay = QVBoxLayout(step)
                step_lay.setContentsMargins(10, 8, 10, 8)
                step_lay.setSpacing(2)
                n = QLabel(number)
                n.setObjectName("StudioDecision")
                step_label = QLabel(label)
                step_label.setObjectName("Faint")
                step_lay.addWidget(n)
                step_lay.addWidget(step_label)
                steps.addWidget(step)
            layout.addLayout(steps)

            form_frame = QFrame()
            form_frame.setObjectName("Panel")
            form_lay = QVBoxLayout(form_frame)
            form_lay.setContentsMargins(14, 12, 14, 12)
            form_lay.setSpacing(8)
            form = QFormLayout()
            self._title = QLineEdit()
            self._title.setPlaceholderText("Ej: Reforma local calle Mayor 12")
            form.addRow("Nombre del expediente *", self._title)

            self._address = QLineEdit()
            self._address.setPlaceholderText(
                "Ej: Calle Gran Vía 1, Madrid, 40.4168, -3.7038 o ref. catastral"
            )
            form.addRow("Dirección, coordenadas o referencia *", self._address)

            self._case_type = QComboBox()
            from adv_archon.core.studio import case_template_options

            for code, label in case_template_options():
                self._case_type.addItem(label, code)
            form.addRow("Tipo de expediente Studio", self._case_type)

            self._notes = QLineEdit()
            self._notes.setPlaceholderText("Opcional")
            form.addRow("Notas", self._notes)

            form_lay.addLayout(form)
            layout.addWidget(form_frame)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Crear expediente")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
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

        def case_type(self) -> str:
            return cast(str, self._case_type.currentData() or "cambio_uso_vivienda")

    # ── Detail panel ──────────────────────────────────────────────────────────

    class ExpedienteDetailPanel(QWidget):  # type: ignore[misc]
        """Right panel: shows site context, plan attachment, actions."""

        def __init__(
            self,
            *,
            on_attach_plan: Any = None,
            on_analyze: Any = None,
            on_export: Any = None,
            on_talk: Any = None,
            on_review: Any = None,
        ) -> None:
            super().__init__()
            self._on_attach_plan = on_attach_plan
            self._on_analyze = on_analyze
            self._on_export = on_export
            self._on_talk = on_talk
            self._on_review = on_review
            self._expediente_id: str | None = None
            self._expediente: Any = None
            self._operation_busy = False

            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 8, 12, 8)
            layout.setSpacing(8)

            # Header
            self._title_label = QLabel("Selecciona o crea un expediente")
            self._title_label.setStyleSheet(
                "font-family:'Libre Baskerville','Georgia',serif;"
                "font-weight:bold;font-size:15px;"
            )
            self._title_label.setWordWrap(True)
            layout.addWidget(self._title_label)

            self._status_label = QLabel("")
            self._status_label.setStyleSheet(f"font-size:11px;color:{TEXT_SUB};")
            layout.addWidget(self._status_label)

            self._operation_label = QLabel("")
            self._operation_label.setStyleSheet(f"font-size:11px;color:{WARN};")
            self._operation_label.setVisible(False)
            layout.addWidget(self._operation_label)

            self._operation_progress = QProgressBar()
            self._operation_progress.setRange(0, 0)
            self._operation_progress.setTextVisible(False)
            self._operation_progress.setMaximumHeight(3)
            self._operation_progress.setVisible(False)
            layout.addWidget(self._operation_progress)

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
            self._plan_label.setStyleSheet(f"color:{TEXT_SUB};font-size:11px;")
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
                f"background:{ACCENT};color:{BG};"
                "padding:6px 16px;border-radius:4px;font-weight:700;"
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
                f"background:{OK};color:{BG};"
                "padding:6px 14px;border-radius:4px;font-weight:700;"
            )
            self._open_report_btn.clicked.connect(self._on_open_report_clicked)
            btn_row.addWidget(self._open_report_btn)

            self._talk_btn = QPushButton("Hablar con ARCHON")
            self._set_brand_icon(self._talk_btn)
            self._talk_btn.setEnabled(False)
            self._talk_btn.setToolTip(
                "Hablar con ARCHON usando este expediente como contexto"
            )
            self._talk_btn.clicked.connect(self._on_talk_clicked)
            btn_row.addWidget(self._talk_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

            review_row = QHBoxLayout()
            review_label = QLabel("Revisión arquitecto")
            review_label.setStyleSheet(f"color:{TEXT_FAINT};font-size:10px;font-weight:700;")
            review_row.addWidget(review_label)
            self._review_confirm_btn = QPushButton("Confirmar")
            self._review_correct_btn = QPushButton("Corregir")
            self._review_note_btn = QPushButton("Añadir nota")
            self._review_exclude_btn = QPushButton("Excluir informe")
            for button, action in (
                (self._review_confirm_btn, "confirmed"),
                (self._review_correct_btn, "needs_correction"),
                (self._review_exclude_btn, "excluded"),
            ):
                button.setObjectName("Ghost")
                button.clicked.connect(
                    lambda _checked=False, act=action: self._on_review_clicked(act)
                )
                review_row.addWidget(button)
            self._review_note_btn.setObjectName("Ghost")
            self._review_note_btn.clicked.connect(
                lambda _checked=False: self._on_review_clicked("note")
            )
            review_row.addWidget(self._review_note_btn)
            review_row.addStretch(1)
            layout.addLayout(review_row)

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
            colour = _STATUS_COLOUR.get(exp.status, TEXT_FAINT)
            label = _STATUS_LABEL.get(exp.status, exp.status)
            self._status_label.setText(
                f"<span style='color:{colour}'>● {label}</span>"
                f"  ·  {exp.municipality or '—'}"
                f"  ·  {exp.created_at[:10]}"
            )
            self._status_label.setTextFormat(Qt.TextFormat.RichText)

            if exp.plan_path:
                self._plan_label.setText(f"Plano: {Path(exp.plan_path).name}")
                self._plan_label.setStyleSheet(f"color:{TEXT_SUB};font-size:11px;")
            else:
                self._plan_label.setText("Sin plano adjunto — adjunta el plano antes de analizar")
                self._plan_label.setStyleSheet(f"color:{TEXT_FAINT};font-size:11px;")

            self._context_browser.setHtml(self._render_context(exp))
            can_analyze = bool(exp.plan_path) and bool(exp.municipality or exp.latitude)
            self._analyze_btn.setEnabled(can_analyze and not self._operation_busy)
            exportable = exp.status in (
                "analizado", "informe_listo", "informe_generado"
            )
            self._export_btn.setEnabled(exportable and not self._operation_busy)
            has_report = bool(exp.report_path) and Path(exp.report_path).exists()
            self._open_report_btn.setEnabled(has_report and not self._operation_busy)
            self._open_report_btn.setVisible(has_report)
            self._talk_btn.setEnabled(not self._operation_busy)
            for button in (
                self._review_confirm_btn,
                self._review_correct_btn,
                self._review_note_btn,
                self._review_exclude_btn,
            ):
                button.setEnabled(not self._operation_busy)

        def set_operation_busy(self, busy: bool, label: str = "") -> None:
            self._operation_busy = busy
            self._operation_label.setText(label)
            self._operation_label.setVisible(busy and bool(label))
            self._operation_progress.setVisible(busy)
            self._analyze_btn.setEnabled(False)
            self._export_btn.setEnabled(False)
            self._open_report_btn.setEnabled(False)
            self._talk_btn.setEnabled(False)
            for button in (
                self._review_confirm_btn,
                self._review_correct_btn,
                self._review_note_btn,
                self._review_exclude_btn,
            ):
                button.setEnabled(False)
            if not busy and self._expediente is not None:
                self.load_expediente(self._expediente)

        def _render_context(self, exp: Any) -> str:  # noqa: C901
            style = (
                "<style>"
                "td{padding:3px 8px;}"
                "th{text-align:left;color:#555;font-size:11px;}"
                "h4{margin:8px 0 4px 0;color:#333;font-size:12px;}"
                "</style>"
            )
            lines: list[str] = [style]
            case_type = getattr(exp, "case_type", "cambio_uso_vivienda")
            try:
                from adv_archon.core.studio import get_case_template

                template = get_case_template(case_type)
                lines.append(
                    "<h4>🏛 ADV ARCHON Studio</h4>"
                    f"<p><b>{escape(template.label)}</b></p>"
                    f"<p style='font-size:11px;color:#555;'>{escape(template.decision_focus)}</p>"
                )
            except Exception:
                pass

            try:
                from adv_archon.core.expediente_quality import evaluate_expediente_quality

                quality = evaluate_expediente_quality(exp)
                missing = ", ".join(item.label for item in quality.missing_items[:4])
                if not missing:
                    missing = "Sin faltas críticas detectadas."
                review = quality.architect_review
                pack = quality.normative_pack
                pack_label = (
                    f"{pack.municipality} · {pack.status} · {pack.last_updated}"
                    if pack
                    else "Municipio pendiente de paquete normativo"
                )
                risk_color = {
                    "alto": "#B24A3C",
                    "medio": "#C9A227",
                    "bajo": "#4B915B",
                }.get(quality.risk_level, "#5C5C58")
                lines.append(
                    "<h4>Calidad del expediente</h4>"
                    "<table>"
                    f"<tr><td>Estado</td><td><b>{escape(quality.completeness_label)}</b></td></tr>"
                    f"<tr><td>Riesgo jurídico</td><td style='color:{risk_color};'><b>"
                    f"{escape(quality.risk_label)}</b></td></tr>"
                    "<tr><td>Fuentes oficiales</td><td><b>"
                    f"{'consultadas' if quality.sources_consulted_ok else 'incompletas'}"
                    "</b></td></tr>"
                    f"<tr><td>Base municipal</td><td>{escape(pack_label)}</td></tr>"
                    f"<tr><td>Falta</td><td>{escape(missing)}</td></tr>"
                    f"<tr><td>Revisión</td><td><b>{escape(review.label)}</b></td></tr>"
                    "</table>"
                )
                if review.note:
                    lines.append(
                        "<p style='font-size:10px;color:#555;'>"
                        f"Nota revisión: {escape(review.note)}</p>"
                    )
            except Exception:
                pass

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
                    try:
                        ar = json.loads(exp.analysis_result) if exp.analysis_result else {}
                    except (json.JSONDecodeError, TypeError):
                        ar = {}
                    from adv_archon.core.studio import build_studio_payload

                    studio = build_studio_payload(
                        case_type=case_type,
                        municipality=exp.municipality,
                        site_context=ctx if isinstance(ctx, dict) else {},
                        analysis=ar if isinstance(ar, dict) else {},
                    )
                    value = studio["estimated_value"]
                    city = studio["city_pack"]
                    lines.append(
                        "<h4>💼 Valor estimado ahorrado</h4><table>"
                        f"<tr><td>Horas evitadas</td><td><b>{value['hours_saved']} h</b></td></tr>"
                        "<tr><td>Riesgos detectados</td>"
                        f"<td><b>{value['risks_detected']}</b></td></tr>"
                        "<tr><td>Fuentes consultadas</td>"
                        f"<td><b>{value['sources_consulted']}</b></td></tr>"
                        "<tr><td>Documentos generados</td>"
                        f"<td><b>{value['documents_generated']}</b></td></tr>"
                        "<tr><td>Paquete ciudad</td>"
                        f"<td><b>{escape(str(city['status']))}</b></td></tr>"
                        "</table>"
                    )
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
            self._operation_busy = False
            self._operation_label.setVisible(False)
            self._operation_progress.setVisible(False)
            self._title_label.setText("Selecciona o crea un expediente")
            self._status_label.setText("")
            self._context_browser.clear()
            self._analyze_btn.setEnabled(False)
            self._export_btn.setEnabled(False)
            self._open_report_btn.setEnabled(False)
            self._open_report_btn.setVisible(False)
            self._talk_btn.setEnabled(False)
            for button in (
                self._review_confirm_btn,
                self._review_correct_btn,
                self._review_note_btn,
                self._review_exclude_btn,
            ):
                button.setEnabled(False)

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

        def _on_talk_clicked(self) -> None:
            if self._on_talk and self._expediente_id:
                self._on_talk(self._expediente_id)

        def _on_review_clicked(self, action: str) -> None:
            if not self._on_review or not self._expediente_id:
                return
            self._on_review(self._expediente_id, action)

        def _on_open_report_clicked(self) -> None:
            if self._expediente and self._expediente.report_path:
                QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(self._expediente.report_path))
                )


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
