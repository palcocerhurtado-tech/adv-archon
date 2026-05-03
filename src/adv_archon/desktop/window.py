from __future__ import annotations

import os
from contextlib import suppress
from html import escape
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from adv_archon.core.expediente import ExpedienteStore
from adv_archon.desktop.expediente_panel import (
    ExpedienteDetailPanel,
    ExpedienteListPanel,
    NewExpedienteDialog,
)
from adv_archon.desktop.models import (
    DesktopAttachment,
    DesktopChatMessage,
    DesktopChatRequest,
    DesktopChatResponse,
    collect_attachments,
)
from adv_archon.desktop.runtime import (
    DesktopChatBackend,
    DesktopRuntimeAssumption,
    EchoDesktopBackend,
    build_default_runtime_assumptions,
)

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

Qt: Any = None
QObject: Any = None
QThread: Any = None
Signal: Any = None
QAbstractItemView: Any = None
QDialog: Any = None
QFileDialog: Any = None
QFrame: Any = None
QHBoxLayout: Any = None
QLabel: Any = None
QListWidget: Any = None
QListWidgetItem: Any = None
QMainWindow: Any = None
QMessageBox: Any = None
QPlainTextEdit: Any = None
QPushButton: Any = None
QSplitter: Any = None
QStatusBar: Any = None
QTabWidget: Any = None
QTextBrowser: Any = None
QVBoxLayout: Any = None
QWidget: Any = None

if PYSIDE6_AVAILABLE:
    _qt_core = import_module("PySide6.QtCore")
    _qt_widgets = import_module("PySide6.QtWidgets")
    Qt = _qt_core.Qt
    QObject = _qt_core.QObject
    QThread = _qt_core.QThread
    Signal = _qt_core.Signal
    QAbstractItemView = _qt_widgets.QAbstractItemView
    QDialog = _qt_widgets.QDialog
    QFileDialog = _qt_widgets.QFileDialog
    QFrame = _qt_widgets.QFrame
    QHBoxLayout = _qt_widgets.QHBoxLayout
    QLabel = _qt_widgets.QLabel
    QListWidget = _qt_widgets.QListWidget
    QListWidgetItem = _qt_widgets.QListWidgetItem
    QMainWindow = _qt_widgets.QMainWindow
    QMessageBox = _qt_widgets.QMessageBox
    QPlainTextEdit = _qt_widgets.QPlainTextEdit
    QPushButton = _qt_widgets.QPushButton
    QSplitter = _qt_widgets.QSplitter
    QStatusBar = _qt_widgets.QStatusBar
    QTabWidget = _qt_widgets.QTabWidget
    QTextBrowser = _qt_widgets.QTextBrowser
    QVBoxLayout = _qt_widgets.QVBoxLayout
    QWidget = _qt_widgets.QWidget


def _render_message(message: DesktopChatMessage) -> str:
    speaker = {"assistant": "ADV ARCHON", "system": "Sistema", "user": "Tú"}[message.role]
    lines = [f"<p><b>{escape(speaker)}</b><br>{escape(message.text).replace(chr(10), '<br>')}"]
    if message.attachments:
        lines.append("<ul>")
        for attachment in message.attachments:
            lines.append(f"<li>{escape(attachment.summary())}</li>")
        lines.append("</ul>")
    lines.append("</p>")
    return "".join(lines)


if PYSIDE6_AVAILABLE:

    class _ChatWorker(QObject):  # type: ignore[misc]
        completed = Signal(object)
        failed = Signal(str)

        def __init__(self, backend: DesktopChatBackend, request: DesktopChatRequest) -> None:
            super().__init__()
            self._backend = backend
            self._request = request

        def run(self) -> None:
            try:
                response = self._backend.complete(self._request)
            except Exception as exc:  # pragma: no cover - defensive UI path
                self.failed.emit(str(exc))
                return
            self.completed.emit(response)


    class AttachmentListWidget(QListWidget):  # type: ignore[misc]
        files_dropped = Signal(list)

        def __init__(self) -> None:
            super().__init__()
            self.setAcceptDrops(True)
            self.setAlternatingRowColors(True)
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        def dragEnterEvent(self, event: Any) -> None:  # pragma: no cover - Qt callback
            if self._extract_paths(event.mimeData()):
                event.acceptProposedAction()
                return
            super().dragEnterEvent(event)

        def dragMoveEvent(self, event: Any) -> None:  # pragma: no cover - Qt callback
            if self._extract_paths(event.mimeData()):
                event.acceptProposedAction()
                return
            super().dragMoveEvent(event)

        def dropEvent(self, event: Any) -> None:  # pragma: no cover - Qt callback
            paths = self._extract_paths(event.mimeData())
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
                return
            super().dropEvent(event)

        @staticmethod
        def _extract_paths(mime_data: Any) -> list[Path]:
            if mime_data is None or not mime_data.hasUrls():
                return []
            paths: list[Path] = []
            for url in mime_data.urls():
                if url.isLocalFile():
                    paths.append(Path(url.toLocalFile()))
            return paths


    class DesktopWindow(QMainWindow):  # type: ignore[misc]
        def __init__(
            self,
            *,
            backend: DesktopChatBackend | None = None,
            assumptions: tuple[DesktopRuntimeAssumption, ...] | None = None,
        ) -> None:
            super().__init__()
            self._backend = backend or EchoDesktopBackend()
            self._assumptions = assumptions or build_default_runtime_assumptions()
            self._attachments: list[DesktopAttachment] = []
            self._active_threads: list[tuple[Any, Any]] = []

            self.setWindowTitle("ADV ARCHON Desktop")
            self.resize(1200, 800)

            # Expediente store — persisted in the same data dir as the rest of the app
            _data_dir = Path(os.getenv("ADV_ARCHON_HOME", Path.home() / ".adv-archon"))
            _data_dir.mkdir(parents=True, exist_ok=True)
            self._exp_store = ExpedienteStore(_data_dir / "expedientes.db")

            root = QWidget()
            root_layout = QVBoxLayout(root)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            tabs = QTabWidget()
            tabs.setTabPosition(QTabWidget.TabPosition.North)
            root_layout.addWidget(tabs)

            # ── Tab 1: Chat ────────────────────────────────────────────────
            chat_tab = QWidget()
            layout = QVBoxLayout(chat_tab)
            layout.setContentsMargins(16, 12, 16, 16)
            layout.setSpacing(12)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            layout.addWidget(splitter, 1)

            chat_panel = QWidget()
            chat_layout = QVBoxLayout(chat_panel)
            chat_layout.setContentsMargins(0, 0, 0, 0)
            chat_layout.setSpacing(10)

            self._transcript = QTextBrowser()
            self._transcript.setOpenExternalLinks(False)
            chat_layout.addWidget(self._transcript, 1)

            composer = QWidget()
            composer_layout = QVBoxLayout(composer)
            composer_layout.setContentsMargins(0, 0, 0, 0)
            composer_layout.setSpacing(8)

            self._prompt_input = QPlainTextEdit()
            self._prompt_input.setPlaceholderText(
                "Escribe aquí. Puedes adjuntar archivos o soltarlos en la lista lateral."
            )
            self._prompt_input.setFixedHeight(140)
            composer_layout.addWidget(self._prompt_input)

            composer_actions = QHBoxLayout()
            self._attach_button = QPushButton("Adjuntar archivos")
            self._attach_button.clicked.connect(self.select_files)
            composer_actions.addWidget(self._attach_button)

            self._send_button = QPushButton("Enviar")
            self._send_button.clicked.connect(self.send_current_message)
            composer_actions.addWidget(self._send_button)
            composer_layout.addLayout(composer_actions)
            chat_layout.addWidget(composer)

            attachments_panel = QWidget()
            attachments_layout = QVBoxLayout(attachments_panel)
            attachments_layout.setContentsMargins(0, 0, 0, 0)
            attachments_layout.setSpacing(10)

            attachments_layout.addWidget(QLabel("Adjuntos"))
            self._attachment_list = AttachmentListWidget()
            self._attachment_list.files_dropped.connect(self.attach_paths)
            attachments_layout.addWidget(self._attachment_list, 1)

            attachment_actions = QHBoxLayout()
            self._remove_button = QPushButton("Quitar seleccionados")
            self._remove_button.clicked.connect(self.remove_selected_attachments)
            attachment_actions.addWidget(self._remove_button)

            self._clear_button = QPushButton("Limpiar")
            self._clear_button.clicked.connect(self.clear_attachments)
            attachment_actions.addWidget(self._clear_button)
            attachments_layout.addLayout(attachment_actions)

            assumptions_label = QLabel(
                "Suposiciones actuales:\n"
                + "\n".join(f"• {item.title}: {item.description}" for item in self._assumptions)
            )
            assumptions_label.setWordWrap(True)
            attachments_layout.addWidget(assumptions_label)

            splitter.addWidget(chat_panel)
            splitter.addWidget(attachments_panel)
            splitter.setSizes([760, 320])

            tabs.addTab(chat_tab, "Chat")

            # ── Tab 2: Expedientes ─────────────────────────────────────────
            exp_tab = QWidget()
            exp_layout = QHBoxLayout(exp_tab)
            exp_layout.setContentsMargins(0, 0, 0, 0)
            exp_layout.setSpacing(0)

            self._exp_list_panel = ExpedienteListPanel(
                on_select=self._on_exp_select,
                on_new=self._on_exp_new,
                on_delete=self._on_exp_delete,
            )
            exp_layout.addWidget(self._exp_list_panel)

            exp_sep = QFrame()
            exp_sep.setFrameShape(QFrame.Shape.VLine)
            exp_layout.addWidget(exp_sep)

            self._exp_detail_panel = ExpedienteDetailPanel(
                on_attach_plan=self._on_exp_attach_plan,
                on_analyze=self._on_exp_analyze,
                on_export=self._on_exp_export,
            )
            exp_layout.addWidget(self._exp_detail_panel, 1)

            tabs.addTab(exp_tab, "Expedientes")

            self._exp_list_panel.populate(self._exp_store.list_all())

            self.setCentralWidget(root)
            self.setStatusBar(QStatusBar())
            self.statusBar().showMessage("ADV ARCHON listo.")

            self._append_message(
                DesktopChatMessage(
                    role="system",
                    text=(
                        "Bienvenido a ADV ARCHON. Puedes chatear aquí o gestionar "
                        "expedientes en la pestaña Expedientes."
                    ),
                )
            )

        def attach_paths(self, paths: list[Path]) -> None:
            existing_paths = [attachment.path for attachment in self._attachments]
            merged = collect_attachments([*existing_paths, *paths])
            self._attachments = merged
            self._refresh_attachment_list()
            self.statusBar().showMessage(f"{len(self._attachments)} adjuntos cargados.")

        def select_files(self) -> None:
            file_paths, _selected_filter = QFileDialog.getOpenFileNames(
                self,
                "Seleccionar archivos",
                str(Path.home()),
                "Todos los archivos (*)",
            )
            if not file_paths:
                return
            self.attach_paths([Path(raw_path) for raw_path in file_paths])

        def remove_selected_attachments(self) -> None:
            selected_rows = {index.row() for index in self._attachment_list.selectedIndexes()}
            if not selected_rows:
                return
            self._attachments = [
                attachment
                for index, attachment in enumerate(self._attachments)
                if index not in selected_rows
            ]
            self._refresh_attachment_list()
            self.statusBar().showMessage("Adjuntos actualizados.")

        def clear_attachments(self) -> None:
            self._attachments = []
            self._refresh_attachment_list()
            self.statusBar().showMessage("Adjuntos limpiados.")

        def send_current_message(self) -> None:
            request = DesktopChatRequest(
                prompt=self._prompt_input.toPlainText(),
                attachments=tuple(self._attachments),
                metadata={"surface": "desktop-ui"},
            )
            if request.is_empty:
                self.statusBar().showMessage("Escribe algo o adjunta al menos un archivo.")
                return

            self._append_message(
                DesktopChatMessage(
                    role="user",
                    text=request.prompt or "Adjuntos enviados sin texto adicional.",
                    attachments=request.attachments,
                )
            )
            self._prompt_input.clear()
            self._attachments = []
            self._refresh_attachment_list()
            self._set_busy(True, "Consultando backend desktop…")
            self._run_request(request)

        def _run_request(self, request: DesktopChatRequest) -> None:
            thread = QThread(self)
            worker = _ChatWorker(self._backend, request)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.completed.connect(
                lambda response, thread=thread, worker=worker: self._handle_response(
                    response, thread, worker
                )
            )
            worker.failed.connect(
                lambda error, thread=thread, worker=worker: self._handle_failure(
                    error, thread, worker
                )
            )
            thread.finished.connect(thread.deleteLater)
            self._active_threads.append((thread, worker))
            thread.start()

        def _handle_response(self, response: DesktopChatResponse, thread: Any, worker: Any) -> None:
            self._append_message(
                DesktopChatMessage(
                    role="assistant",
                    text=response.text,
                    attachments=response.used_attachments,
                )
            )
            self._finish_worker(thread, worker, "Respuesta recibida.")

        def _handle_failure(self, error: str, thread: Any, worker: Any) -> None:
            QMessageBox.warning(self, "ADV ARCHON Desktop", error)
            self._finish_worker(thread, worker, "El backend desktop devolvió un error.")

        def _finish_worker(self, thread: Any, worker: Any, status_message: str) -> None:
            self._set_busy(False, status_message)
            with suppress(ValueError):
                self._active_threads.remove((thread, worker))
            thread.quit()
            thread.wait(1000)
            worker.deleteLater()

        def _refresh_attachment_list(self) -> None:
            self._attachment_list.clear()
            for attachment in self._attachments:
                self._attachment_list.addItem(QListWidgetItem(attachment.summary()))

        def _append_message(self, message: DesktopChatMessage) -> None:
            self._transcript.append(_render_message(message))
            self._transcript.verticalScrollBar().setValue(
                self._transcript.verticalScrollBar().maximum()
            )

        def _set_busy(self, is_busy: bool, status_message: str) -> None:
            self._prompt_input.setDisabled(is_busy)
            self._send_button.setDisabled(is_busy)
            self._attach_button.setDisabled(is_busy)
            self._remove_button.setDisabled(is_busy)
            self._clear_button.setDisabled(is_busy)
            self.statusBar().showMessage(status_message)

        # ── Expediente callbacks ───────────────────────────────────────────

        def _on_exp_new(self) -> None:
            dlg = NewExpedienteDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            exp = self._exp_store.create(
                title=dlg.title_text(),
                address=dlg.address_text(),
                notes=dlg.notes_text(),
            )
            self._exp_list_panel.populate(self._exp_store.list_all())
            self._exp_detail_panel.load_expediente(exp)
            self.statusBar().showMessage(f"Expediente «{exp.title}» creado.")

        def _on_exp_select(self, expediente_id: str) -> None:
            exp = self._exp_store.get(expediente_id)
            if exp:
                self._exp_detail_panel.load_expediente(exp)

        def _on_exp_delete(self, expediente_id: str) -> None:
            exp = self._exp_store.get(expediente_id)
            if not exp:
                return
            reply = QMessageBox.question(
                self,
                "Eliminar expediente",
                f"¿Eliminar «{exp.title}»? Esta acción no se puede deshacer.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._exp_store.delete(expediente_id)
                self._exp_list_panel.populate(self._exp_store.list_all())
                self._exp_detail_panel.clear()
                self.statusBar().showMessage("Expediente eliminado.")

        def _on_exp_attach_plan(self, expediente_id: str) -> None:
            paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Adjuntar plano arquitectónico",
                str(Path.home()),
                "Planos (*.pdf *.dwg *.dxf *.png *.jpg *.jpeg);;Todos (*)",
            )
            if not paths:
                return
            exp = self._exp_store.get(expediente_id)
            if not exp:
                return
            import dataclasses
            exp = dataclasses.replace(exp, plan_path=paths[0])
            self._exp_store.update(exp)
            self._exp_detail_panel.load_expediente(exp)
            self.statusBar().showMessage(f"Plano adjuntado: {Path(paths[0]).name}")

        def _on_exp_analyze(self, expediente_id: str) -> None:
            exp = self._exp_store.get(expediente_id)
            if not exp:
                return
            # Pre-fill chat with expediente context so the user can trigger analysis
            self.statusBar().showMessage("Abre la pestaña Chat para ejecutar el análisis.")
            prompt = (
                f"Analiza el plano del expediente «{exp.title}».\n"
                f"Dirección: {exp.address}\n"
                f"Municipio: {exp.municipality or '(pendiente de resolver)'}\n"
                f"Ref. catastral: {exp.cadastral_ref or '(pendiente)'}\n"
                f"Plano: {exp.plan_path}\n\n"
                "Ejecuta plan_compliance_check con ese plano y el municipio indicado."
            )
            self._prompt_input.setPlainText(prompt)
            # Switch to chat tab
            self.centralWidget().layout().itemAt(0).widget().setCurrentIndex(0)

        def _on_exp_export(self, expediente_id: str) -> None:
            exp = self._exp_store.get(expediente_id)
            if not exp:
                return
            QMessageBox.information(
                self,
                "Exportar informe",
                f"Usa el comando /export o solicítalo en el chat para generar el PDF "
                f"del expediente «{exp.title}».",
            )


else:

    class DesktopWindow:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PySide6 no está instalada. No se puede crear la UI desktop.")


def create_desktop_window(
    *,
    backend: DesktopChatBackend | None = None,
    assumptions: tuple[DesktopRuntimeAssumption, ...] | None = None,
) -> Any:
    if not PYSIDE6_AVAILABLE:
        raise RuntimeError("PySide6 no está instalada. No se puede crear la UI desktop.")
    return DesktopWindow(backend=backend, assumptions=assumptions)
