# mypy: ignore-errors
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from adv_archon.desktop.models import DesktopAttachment, collect_attachments

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

Qt: Any = None
QEvent: Any = None
Signal: Any = None
QComboBox: Any = None
QFrame: Any = None
QHBoxLayout: Any = None
QLabel: Any = None
QListWidget: Any = None
QListWidgetItem: Any = None
QPushButton: Any = None
QTextEdit: Any = None
QVBoxLayout: Any = None
QWidget: Any = None

if PYSIDE6_AVAILABLE:
    _qt_core = import_module("PySide6.QtCore")
    _qt_widgets = import_module("PySide6.QtWidgets")
    Qt = _qt_core.Qt
    QEvent = _qt_core.QEvent
    Signal = _qt_core.Signal
    QComboBox = _qt_widgets.QComboBox
    QFrame = _qt_widgets.QFrame
    QHBoxLayout = _qt_widgets.QHBoxLayout
    QLabel = _qt_widgets.QLabel
    QListWidget = _qt_widgets.QListWidget
    QListWidgetItem = _qt_widgets.QListWidgetItem
    QPushButton = _qt_widgets.QPushButton
    QTextEdit = _qt_widgets.QTextEdit
    QVBoxLayout = _qt_widgets.QVBoxLayout
    QWidget = _qt_widgets.QWidget


@dataclass(frozen=True, slots=True)
class DraftSection:
    section_id: str
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class AttachmentPreview:
    path: Path
    display_name: str
    kind: str
    summary: str


def _get_value(source: Mapping[str, Any] | Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(source, Mapping) and name in source:
            return source[name]
        if not isinstance(source, Mapping) and hasattr(source, name):
            return getattr(source, name)
    return default


def extract_draft_sections(draft: Mapping[str, Any] | Any) -> list[DraftSection]:
    """Return normalized editable sections from a loose draft-like object."""
    raw_sections = _get_value(draft, "sections", default=()) or ()
    sections: list[DraftSection] = []
    for index, raw in enumerate(raw_sections, start=1):
        section_id = str(_get_value(raw, "id", "section_id", default=f"section-{index}"))
        title = str(_get_value(raw, "title", "heading", default=f"Seccion {index}"))
        content = str(_get_value(raw, "content", "body", "text", "markdown", default=""))
        sections.append(DraftSection(section_id=section_id, title=title, content=content))

    if not sections:
        summary = str(_get_value(draft, "executive_summary", "summary", default="")).strip()
        if summary:
            sections.append(
                DraftSection(
                    section_id="executive_summary",
                    title="Resumen ejecutivo",
                    content=summary,
                )
            )
    if not sections:
        sections.append(DraftSection(section_id="draft", title="Borrador", content=""))
    return sections


def build_attachment_previews(paths: list[str | Path]) -> list[AttachmentPreview]:
    attachments = collect_attachments(paths)
    return [
        AttachmentPreview(
            path=attachment.path,
            display_name=attachment.display_name,
            kind=attachment.kind,
            summary=attachment.summary(),
        )
        for attachment in attachments
    ]


def _attachment_paths_from_draft(draft: Mapping[str, Any] | Any) -> list[Path]:
    raw_attachments = _get_value(draft, "attachments", "adjuntos", default=()) or ()
    paths: list[Path] = []
    for item in raw_attachments:
        raw_path = _get_value(item, "path", default=item)
        if raw_path:
            paths.append(Path(str(raw_path)).expanduser())
    return paths


def _draft_title(draft: Mapping[str, Any] | Any) -> str:
    return str(_get_value(draft, "title", "titulo", "project_name", default="Borrador"))


def _draft_status(draft: Mapping[str, Any] | Any) -> str:
    return str(_get_value(draft, "status", "estado", "verdict", default="Sin validar"))


if PYSIDE6_AVAILABLE:

    class DraftEditorWidget(QWidget):  # type: ignore[misc]
        """Editable draft surface for PDF/DOCX/XLSX previews."""

        draft_changed = Signal(object)
        export_requested = Signal(str)

        def __init__(self, parent: Any | None = None) -> None:
            super().__init__(parent)
            self._draft: dict[str, Any] = {}
            self._sections: list[DraftSection] = []
            self._loading = False
            self._dirty = False

            self.setObjectName("DraftEditor")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)

            header = QVBoxLayout()
            self._title_label = QLabel("Borrador del informe")
            self._title_label.setObjectName("StudioCase")
            header.addWidget(self._title_label)

            self._status_label = QLabel("Sin borrador cargado")
            self._status_label.setObjectName("Faint")
            self._status_label.setWordWrap(True)
            header.addWidget(self._status_label)
            layout.addLayout(header)

            self._section_combo = QComboBox()
            self._section_combo.currentIndexChanged.connect(self._on_section_changed)
            layout.addWidget(self._section_combo)

            self._editor = QTextEdit()
            self._editor.setPlaceholderText("Edita aqui la seccion seleccionada del borrador.")
            self._editor.textChanged.connect(self._on_text_changed)
            layout.addWidget(self._editor, 1)

            attachment_header = QLabel("Adjuntos / evidencias")
            attachment_header.setObjectName("Faint")
            layout.addWidget(attachment_header)

            self._attachments_list = QListWidget()
            self._attachments_list.setMaximumHeight(92)
            layout.addWidget(self._attachments_list)

            actions = QHBoxLayout()
            self._save_button = QPushButton("Guardar borrador")
            self._save_button.clicked.connect(self.mark_saved)
            actions.addWidget(self._save_button)

            for kind, label in (("pdf", "PDF"), ("docx", "DOCX"), ("xlsx", "XLSX")):
                button = QPushButton(label)
                button.setObjectName("Primary" if kind == "pdf" else "Ghost")
                button.clicked.connect(
                    lambda _checked=False, value=kind: self.request_export(value)
                )
                actions.addWidget(button)

            layout.addLayout(actions)

        def load_draft(self, draft: Mapping[str, Any] | Any) -> None:
            self._loading = True
            self._dirty = False
            self._draft = dict(draft) if isinstance(draft, Mapping) else dict(vars(draft))
            self._sections = extract_draft_sections(draft)

            self._title_label.setText(_draft_title(draft))
            self.set_status(f"Estado: {_draft_status(draft)}")

            previous_block = self._section_combo.blockSignals(True)
            self._section_combo.clear()
            for section in self._sections:
                self._section_combo.addItem(section.title, section.section_id)
            self._section_combo.blockSignals(previous_block)

            self.set_attachments(_attachment_paths_from_draft(draft))
            self._section_combo.setCurrentIndex(0)
            self._render_current_section()
            self._loading = False

        def current_draft(self) -> dict[str, Any]:
            self._save_current_section()
            updated = dict(self._draft)
            updated["sections"] = [
                {
                    "id": section.section_id,
                    "title": section.title,
                    "content": section.content,
                }
                for section in self._sections
            ]
            updated["status"] = self._status_label.text().removeprefix("Estado: ").strip()
            return updated

        def current_section_id(self) -> str | None:
            index = self._section_combo.currentIndex()
            if index < 0 or index >= len(self._sections):
                return None
            return self._sections[index].section_id

        def set_status(self, text: str) -> None:
            self._status_label.setText(text)

        def set_attachments(self, paths: list[str | Path]) -> None:
            self._attachments_list.clear()
            previews = build_attachment_previews(paths)
            if not previews:
                self._attachments_list.addItem(QListWidgetItem("Sin adjuntos vinculados"))
                return
            for preview in previews:
                self._attachments_list.addItem(QListWidgetItem(preview.summary))

        def mark_dirty(self) -> None:
            if self._loading:
                return
            self._dirty = True
            self.set_status("Borrador sin guardar")
            self.draft_changed.emit(self.current_draft())

        def mark_saved(self) -> None:
            self._dirty = False
            self.set_status("Borrador guardado")
            self.draft_changed.emit(self.current_draft())

        def request_export(self, kind: str) -> None:
            self._save_current_section()
            self.export_requested.emit(kind)

        def _on_section_changed(self, _index: int) -> None:
            if self._loading:
                return
            self._render_current_section()

        def _on_text_changed(self) -> None:
            if self._loading:
                return
            self._save_current_section()
            self.mark_dirty()

        def _render_current_section(self) -> None:
            index = self._section_combo.currentIndex()
            if index < 0 or index >= len(self._sections):
                self._editor.clear()
                return
            self._loading = True
            self._editor.setPlainText(self._sections[index].content)
            self._loading = False

        def _save_current_section(self) -> None:
            index = self._section_combo.currentIndex()
            if index < 0 or index >= len(self._sections):
                return
            self._sections[index] = replace(
                self._sections[index],
                content=self._editor.toPlainText(),
            )


    class MultimodalComposerWidget(QFrame):  # type: ignore[misc]
        """Compact composer with text, attachment previews and voice/send actions."""

        send_requested = Signal(str, object)
        attach_requested = Signal()
        voice_requested = Signal()
        attachments_changed = Signal(object)

        def __init__(self, parent: Any | None = None) -> None:
            super().__init__(parent)
            self._attachments: list[DesktopAttachment] = []

            self.setObjectName("ComposerMultimodal")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(8)

            self._attachment_preview = QListWidget()
            self._attachment_preview.setMaximumHeight(76)
            layout.addWidget(self._attachment_preview)
            self._render_attachments()

            self._input = QTextEdit()
            self._input.setPlaceholderText("Escribe tu consulta... (Ctrl+Enter para enviar)")
            self._input.setMaximumHeight(88)
            self._input.installEventFilter(self)
            layout.addWidget(self._input)

            actions = QHBoxLayout()
            self._attach_button = QPushButton("Adjuntar")
            self._attach_button.clicked.connect(self.attach_requested.emit)
            actions.addWidget(self._attach_button)

            self._voice_button = QPushButton("Hablar")
            self._voice_button.clicked.connect(self.voice_requested.emit)
            actions.addWidget(self._voice_button)

            actions.addStretch(1)

            self._send_button = QPushButton("Enviar")
            self._send_button.setObjectName("Primary")
            self._send_button.clicked.connect(self.submit)
            actions.addWidget(self._send_button)
            layout.addLayout(actions)

        def eventFilter(self, watched: Any, event: Any) -> bool:
            if watched is self._input and event.type() == QEvent.Type.KeyPress:
                is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                if is_enter and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self.submit()
                    return True
            return super().eventFilter(watched, event)

        def set_text(self, text: str) -> None:
            self._input.setPlainText(text)

        def text(self) -> str:
            return self._input.toPlainText()

        def set_attachments(self, paths: list[str | Path]) -> None:
            self._attachments = collect_attachments(paths)
            self._render_attachments()
            self.attachments_changed.emit(tuple(self._attachments))

        def attachments(self) -> tuple[DesktopAttachment, ...]:
            return tuple(self._attachments)

        def clear(self) -> None:
            self._input.clear()
            self._attachments = []
            self._render_attachments()
            self.attachments_changed.emit(tuple())

        def submit(self) -> None:
            prompt = self.text().strip()
            if not prompt and not self._attachments:
                return
            self.send_requested.emit(prompt, tuple(self._attachments))
            self.clear()

        def _render_attachments(self) -> None:
            self._attachment_preview.clear()
            if not self._attachments:
                self._attachment_preview.addItem(QListWidgetItem("Sin adjuntos"))
                return
            for attachment in self._attachments:
                self._attachment_preview.addItem(QListWidgetItem(attachment.summary()))

else:

    class DraftEditorWidget:  # pragma: no cover - only used when Qt is missing
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PySide6 no esta instalada. No se puede crear DraftEditorWidget.")


    class MultimodalComposerWidget:  # pragma: no cover - only used when Qt is missing
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError(
                "PySide6 no esta instalada. No se puede crear MultimodalComposerWidget."
            )


__all__ = [
    "AttachmentPreview",
    "DraftEditorWidget",
    "DraftSection",
    "MultimodalComposerWidget",
    "PYSIDE6_AVAILABLE",
    "build_attachment_previews",
    "extract_draft_sections",
]
