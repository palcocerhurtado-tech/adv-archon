# mypy: ignore-errors
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adv_archon.core.knowledge import KnowledgeStore

try:
    from PySide6.QtCore import QObject, QThread, Signal
    from PySide6.QtWidgets import (
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
    )

    PYSIDE6_AVAILABLE = True
except ModuleNotFoundError:
    PYSIDE6_AVAILABLE = False
    QDialog = object  # type: ignore[misc,assignment]
    QObject = object  # type: ignore[misc,assignment]


if PYSIDE6_AVAILABLE:

    class _IngestWorker(QObject):  # type: ignore[misc]
        finished = Signal(int)
        status = Signal(str)
        failed = Signal(str)

        def __init__(
            self,
            pdf_path: Path,
            knowledge_store: KnowledgeStore,
            document_title: str,
        ) -> None:
            super().__init__()
            self._pdf_path = pdf_path
            self._ks = knowledge_store
            self._title = document_title

        def run(self) -> None:
            try:
                from adv_archon.core.pgou_ingest import ingest_pgou_pdf

                self.status.emit("Extrayendo texto del PDF…")
                count = ingest_pgou_pdf(
                    self._pdf_path,
                    self._ks,
                    document_title=self._title or None,
                )
                self.finished.emit(count)
            except Exception as exc:
                self.failed.emit(str(exc))

    class PgouImportDialog(QDialog):  # type: ignore[misc]
        """Dialog for ingesting a PGOU PDF into the KnowledgeStore."""

        def __init__(
            self,
            knowledge_store: KnowledgeStore,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self._ks = knowledge_store
            self._thread: QThread | None = None
            self._worker: _IngestWorker | None = None

            self.setWindowTitle("Importar normativa PGOU")
            self.setMinimumWidth(480)

            from adv_archon.desktop.branding import desktop_stylesheet
            self.setStyleSheet(desktop_stylesheet())

            layout = QVBoxLayout(self)
            layout.setSpacing(12)
            layout.setContentsMargins(20, 20, 20, 20)

            # PDF picker row
            pdf_row = QHBoxLayout()
            self._pdf_label = QLabel("Ningún archivo seleccionado")
            self._pdf_label.setWordWrap(True)
            pdf_row.addWidget(self._pdf_label, 1)
            browse_btn = QPushButton("Seleccionar PDF…")
            browse_btn.clicked.connect(self._browse)
            pdf_row.addWidget(browse_btn)
            layout.addLayout(pdf_row)

            # Document title
            title_row = QHBoxLayout()
            title_row.addWidget(QLabel("Título del documento:"))
            self._title_edit = QLineEdit()
            self._title_edit.setPlaceholderText("Ej: PGOU Málaga — Título I")
            title_row.addWidget(self._title_edit, 1)
            layout.addLayout(title_row)

            # Progress & status
            self._progress = QProgressBar()
            self._progress.setRange(0, 0)
            self._progress.setVisible(False)
            layout.addWidget(self._progress)

            self._status_label = QLabel("")
            layout.addWidget(self._status_label)

            # Buttons
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            self._import_btn = QPushButton("Importar")
            self._import_btn.setObjectName("Primary")
            self._import_btn.setEnabled(False)
            self._import_btn.clicked.connect(self._start_import)
            btn_row.addWidget(self._import_btn)
            self._close_btn = QPushButton("Cerrar")
            self._close_btn.clicked.connect(self.reject)
            btn_row.addWidget(self._close_btn)
            layout.addLayout(btn_row)

            self._pdf_path: Path | None = None

        def _browse(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Seleccionar PDF de normativa PGOU",
                str(Path.home()),
                "PDF (*.pdf);;Todos (*)",
            )
            if not path:
                return
            self._pdf_path = Path(path)
            self._pdf_label.setText(self._pdf_path.name)
            if not self._title_edit.text():
                self._title_edit.setText(
                    self._pdf_path.stem.replace("_", " ").replace("-", " ")
                )
            self._import_btn.setEnabled(True)

        def _start_import(self) -> None:
            if self._pdf_path is None:
                return
            self._import_btn.setEnabled(False)
            self._close_btn.setEnabled(False)
            self._progress.setVisible(True)
            self._status_label.setText("Preparando…")

            thread = QThread(self)
            worker = _IngestWorker(
                self._pdf_path,
                self._ks,
                self._title_edit.text().strip(),
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.status.connect(self._status_label.setText)
            worker.finished.connect(self._on_finished)
            worker.failed.connect(self._on_failed)
            worker.finished.connect(thread.quit)
            worker.failed.connect(thread.quit)
            thread.finished.connect(thread.deleteLater)

            self._thread = thread
            self._worker = worker
            thread.start()

        def _on_finished(self, count: int) -> None:
            self._progress.setVisible(False)
            self._status_label.setText(
                f"✓ {count} fragmentos importados correctamente."
            )
            self._close_btn.setEnabled(True)

        def _on_failed(self, error: str) -> None:
            self._progress.setVisible(False)
            self._status_label.setText(f"Error: {error}")
            self._import_btn.setEnabled(True)
            self._close_btn.setEnabled(True)


def open_pgou_import_dialog(
    knowledge_store: KnowledgeStore,
    parent: Any = None,
) -> None:
    """Open the PGOU import dialog. No-op if PySide6 is not available."""
    if not PYSIDE6_AVAILABLE:
        return
    dlg = PgouImportDialog(knowledge_store, parent=parent)
    dlg.exec()
