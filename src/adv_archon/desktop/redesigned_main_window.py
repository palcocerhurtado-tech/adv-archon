# mypy: ignore-errors
"""
ADV ARCHON — Redesigned Main Window (v2)
=========================================
Minimalist, conversational UI.  Single canvas · Cmd+K command palette
· Collapsible side panels · No floating windows.

Outbound signals (connect these to your runtime):
    window.prompt_submitted   Signal(str, list)   – (text, [Path, …])
    window.command_triggered  Signal(str)          – command id string

Inbound API (push events into the window):
    window.receive_chunk(chunk: str)      – stream one LLM token
    window.receive_tool_call(name: str)   – update Tools tab + auto-open right panel
    window.receive_source(source: str)    – add entry to Sources tab
    window.receive_final()                – close the streaming bubble
    window.set_expediente(exp: dict)      – update active expediente context
    window.set_model(model: str)          – update status-bar model label
    window.set_mode("local"|"cloud")      – update mode indicator

Integration with existing ArchonRuntime
-----------------------------------------
The simplest wiring (drop-in for DesktopWindow):

    worker = BackendWorker(runtime)          # existing workers.py
    window = RedesignedMainWindow()
    window.prompt_submitted.connect(
        lambda text, atts: worker.run_prompt(text, atts))
    worker.chunk_received.connect(window.receive_chunk)
    worker.tool_called.connect(
        lambda name, _args: window.receive_tool_call(name))
    worker.prompt_done.connect(window.receive_final)
    window.command_triggered.connect(your_command_dispatcher)
    window.show()
"""
from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QPoint,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QKeySequence,
    QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ── colour tokens ──────────────────────────────────────────────────────────
ACCENT           = "#C9A84C"
BG_LIGHT         = "#F7F4EF"
BG_DARK          = "#1C1C1E"
CARD_LIGHT       = "#FFFFFF"
CARD_DARK        = "#2C2C2E"
TEXT_PRI_LIGHT   = "#111111"
TEXT_PRI_DARK    = "#EEEEEE"
TEXT_SEC_LIGHT   = "#6B6B6B"
TEXT_SEC_DARK    = "#8E8E93"
BORDER_LIGHT     = "#E8E4DD"
BORDER_DARK      = "#3A3A3C"
USER_BG_LIGHT    = "#E8E4DD"
USER_BG_DARK     = "#3A3A3C"
AGENT_BG_LIGHT   = "#FFFFFF"
AGENT_BG_DARK    = "#2C2C2E"
PANEL_BG_LIGHT   = "#F0EDE8"
PANEL_BG_DARK    = "#111111"

LEFT_OPEN_W  = 240
RIGHT_OPEN_W = 340
TOP_H        = 38


def _is_dark() -> bool:
    app = QApplication.instance()
    if app is None:
        return False
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


# ── Command Registry ───────────────────────────────────────────────────────
@dataclass
class CommandDef:
    id: str
    label: str
    category: str
    shortcut: str = ""
    icon: str = ""


COMMANDS: list[CommandDef] = [
    # Expedientes
    CommandDef("exp_new",            "Nuevo expediente",                "Expedientes",   "⌘N",  "📋"),  # noqa: E501
    CommandDef("exp_open",           "Abrir expediente…",               "Expedientes",   "⌘O",  "📂"),  # noqa: E501
    CommandDef("exp_list",           "Ver todos los expedientes",        "Expedientes",   "",    "🗂"),  # noqa: E501
    CommandDef("exp_import",         "Importar expediente (.archon)",    "Expedientes",   "",    "📥"),  # noqa: E501
    CommandDef("exp_export",         "Exportar expediente (.archon)",    "Expedientes",   "",    "📦"),  # noqa: E501
    # Análisis
    CommandDef("pgou_analyze",       "Analizar con PGOU",               "Análisis",      "",    "⚖"),  # noqa: E501
    CommandDef("pgou_params",        "Extraer parámetros urbanísticos",  "Análisis",      "",    "🔍"),  # noqa: E501
    CommandDef("review_pro",         "Revisión Pro",                    "Análisis",      "",    "✅"),  # noqa: E501
    CommandDef("geo_query",          "Consulta geográfica",             "Análisis",      "",    "🗺"),  # noqa: E501
    CommandDef("boe_search",         "Buscar en BOE",                   "Análisis",      "",    "📰"),  # noqa: E501
    CommandDef("edificabilidad",     "Calcular edificabilidad",         "Análisis",      "",    "📐"),  # noqa: E501
    CommandDef("comparar_parcelas",  "Comparar parcelas",               "Análisis",      "",    "⚡"),  # noqa: E501
    # Documentos
    CommandDef("doc_pdf",            "Exportar a PDF",                  "Documentos",    "⌘E",  "📄"),  # noqa: E501
    CommandDef("doc_docx",           "Exportar a DOCX",                 "Documentos",    "",    "📝"),  # noqa: E501
    CommandDef("doc_xlsx",           "Exportar a XLSX",                 "Documentos",    "",    "📊"),  # noqa: E501
    CommandDef("doc_informe",        "Generar informe integrado",       "Documentos",    "",    "📑"),  # noqa: E501
    CommandDef("doc_memoria",        "Redactar Memoria Descriptiva",    "Documentos",    "",    "📖"),  # noqa: E501
    CommandDef("doc_pem_pdf",        "Exportar PEM a PDF",              "Documentos",    "",    "💶"),  # noqa: E501
    # Herramientas
    CommandDef("research",           "Research Workbench",              "Herramientas",  "",    "🔬"),  # noqa: E501
    CommandDef("training",           "Training Lab",                    "Herramientas",  "",    "🧪"),  # noqa: E501
    CommandDef("pgou_status",        "Estado PGOU (municipios)",        "Herramientas",  "",    "🏛"),  # noqa: E501
    CommandDef("studio_demo",        "Studio Demo",                     "Herramientas",  "",    "🎬"),  # noqa: E501
    CommandDef("briefing",           "Daily Briefing",                  "Herramientas",  "",    "📰"),  # noqa: E501
    # Configuración
    CommandDef("mode_local",         "Cambiar a modo local",            "Configuración", "",    "💻"),  # noqa: E501
    CommandDef("mode_cloud",         "Cambiar a modo cloud",            "Configuración", "",    "🌐"),  # noqa: E501
    CommandDef("settings",           "Ajustes",                         "Configuración", "",    "⚙"),  # noqa: E501
    CommandDef("qa_system",          "QA sistema y permisos",           "Configuración", "",    "🔧"),  # noqa: E501
    CommandDef("model_select",       "Cambiar modelo Ollama",           "Configuración", "",    "🤖"),  # noqa: E501
    CommandDef("theme_toggle",       "Cambiar tema (claro/oscuro)",     "Configuración", "",    "🌓"),  # noqa: E501
    # Ayuda
    CommandDef("beta_guide",         "Guía beta",                       "Ayuda",         "",    "📚"),  # noqa: E501
    CommandDef("shortcuts",          "Atajos de teclado",               "Ayuda",         "",    "⌨"),  # noqa: E501
]


# ── Attachment Chiclet ──────────────────────────────────────────────────────
class AttachmentChiclet(QFrame):
    """Pill that shows an attached file name + remove button."""

    removed = Signal(Path)

    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = path
        self.setObjectName("chiclet")
        self.setFixedHeight(26)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 4, 0)
        lay.setSpacing(4)

        ext = path.suffix.lower()
        icon = "📄" if ext == ".pdf" else "🖼" if ext in (".png", ".jpg", ".jpeg") else "📎"
        name = path.name
        short = name[:26] + "…" if len(name) > 26 else name
        lbl = QLabel(f"{icon} {short}")
        lbl.setObjectName("chicletLabel")

        btn = QPushButton("×")
        btn.setObjectName("chicletRemove")
        btn.setFixedSize(16, 16)
        btn.clicked.connect(lambda: self.removed.emit(self._path))

        lay.addWidget(lbl)
        lay.addWidget(btn)


# ── Composer Edit (QTextEdit subclass) ─────────────────────────────────────
class _ComposerEdit(QTextEdit):
    """QTextEdit that submits on Enter (Shift+Enter = newline) and accepts drops."""

    submit_requested = Signal()
    files_dropped    = Signal(list)   # list[Path]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("composerEdit")
        self.setPlaceholderText("Escribe tu consulta o arrastra un archivo… (⏎ enviar · ⇧⏎ nueva línea)")  # noqa: E501
        self.setAcceptDrops(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setFixedHeight(46)
        self.document().contentsChanged.connect(self._auto_resize)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        mods = event.modifiers()
        key  = event.key()
        enter_keys = (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        shift = Qt.KeyboardModifier.ShiftModifier

        if key in enter_keys and not (mods & shift):
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            paths = [
                Path(u.toLocalFile())
                for u in event.mimeData().urls()
                if u.isLocalFile()
            ]
            if paths:
                self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def _auto_resize(self) -> None:
        h = max(46, min(int(self.document().size().height()) + 18, 160))
        self.setFixedHeight(h)


# ── Full Composer Area ─────────────────────────────────────────────────────
class Composer(QFrame):
    """
    Complete input zone: chiclets row (hidden when empty) +
    text edit + status-bar row with model info and ⌘K button.
    """

    submitted        = Signal(str, list)   # (text, list[Path])
    palette_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("composer")
        self._attachments: list[Path] = []
        self._chips: dict[Path, AttachmentChiclet] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 8, 14, 8)
        outer.setSpacing(6)

        # Chiclets row
        self._chiclet_row = QFrame()
        self._chiclet_row.setObjectName("chicletRow")
        self._cl = QHBoxLayout(self._chiclet_row)
        self._cl.setContentsMargins(0, 0, 0, 0)
        self._cl.setSpacing(6)
        self._cl.addStretch()
        self._chiclet_row.setVisible(False)
        outer.addWidget(self._chiclet_row)

        # Text edit
        self._edit = _ComposerEdit()
        self._edit.submit_requested.connect(self._on_submit)
        self._edit.files_dropped.connect(self._add_files)
        outer.addWidget(self._edit)

        # Status row
        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 4, 0)
        self._status = QLabel("llama3.2:3b · local · Sin expediente")
        self._status.setObjectName("statusLabel")
        cmdk = QPushButton("⌘K  Comandos")
        cmdk.setObjectName("cmdKBtn")
        cmdk.setFixedHeight(22)
        cmdk.clicked.connect(self.palette_requested)
        row.addWidget(self._status)
        row.addStretch()
        row.addWidget(cmdk)
        outer.addLayout(row)

    # ── public API ──────────────────────────────────────────────────────
    def add_attachment(self, path: Path) -> None:
        if path in self._attachments:
            return
        self._attachments.append(path)
        chip = AttachmentChiclet(path)
        chip.removed.connect(self._remove_chip)
        self._chips[path] = chip
        self._cl.insertWidget(0, chip)
        self._chiclet_row.setVisible(True)

    def clear(self) -> None:
        self._edit.clear()
        for p in list(self._attachments):
            self._remove_chip(p)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_enabled_input(self, enabled: bool) -> None:
        self._edit.setReadOnly(not enabled)

    # ── private ─────────────────────────────────────────────────────────
    def _on_submit(self) -> None:
        text = self._edit.toPlainText().strip()
        if not text and not self._attachments:
            return
        atts = list(self._attachments)
        self.clear()
        self.submitted.emit(text, atts)

    def _add_files(self, paths: list[Path]) -> None:
        for p in paths:
            self.add_attachment(p)

    def _remove_chip(self, path: Path) -> None:
        if path in self._attachments:
            self._attachments.remove(path)
        chip = self._chips.pop(path, None)
        if chip:
            chip.setParent(None)  # type: ignore[call-overload]
        self._chiclet_row.setVisible(bool(self._attachments))


# ── Message Bubble ─────────────────────────────────────────────────────────
class MessageBubble(QFrame):
    """Single chat message. Role: "user" | "agent"."""

    def __init__(
        self,
        role: str,
        text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._role          = role
        self._buffer        = text
        self._is_placeholder = not bool(text)   # True until first real content arrives
        self.setObjectName(f"bubble_{role}")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)

        self._view = QTextBrowser()
        self._view.setObjectName(f"bubbleView_{role}")
        self._view.setOpenExternalLinks(True)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._view.setReadOnly(True)

        if role == "user":
            outer.addStretch()
            outer.addWidget(self._view)
        else:
            outer.addWidget(self._view)
            outer.addStretch()

        if text:
            self._render()

    def set_text(self, text: str) -> None:
        self._buffer = text
        self._is_placeholder = False
        self._render()

    def append_text(self, chunk: str) -> None:
        self._buffer += chunk
        self._is_placeholder = False
        self._render()

    def show_status(self, status: str) -> None:
        """Show italic status text without affecting the content buffer."""
        self._view.setMarkdown(f"*{status}*")
        self._fit()

    def _render(self) -> None:
        self._view.setMarkdown(self._buffer)
        self._fit()

    def _fit(self) -> None:
        doc = self._view.document()
        w = self._view.viewport().width() or 480
        doc.setTextWidth(w)
        h = max(int(doc.size().height()) + 10, 32)
        self._view.setFixedHeight(h)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._fit()


# ── Chat Area ──────────────────────────────────────────────────────────────
class ChatArea(QScrollArea):
    """Scrollable message list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatArea")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._content.setObjectName("chatContent")
        self._vbox = QVBoxLayout(self._content)
        self._vbox.setContentsMargins(0, 20, 0, 20)
        self._vbox.setSpacing(4)
        self._vbox.addStretch()
        self.setWidget(self._content)

        self._streaming_bubble: MessageBubble | None = None

    # ── public API ──────────────────────────────────────────────────────
    def add_message(self, role: str, text: str) -> MessageBubble:
        bubble = MessageBubble(role, text)
        self._insert(bubble)
        self._streaming_bubble = None
        QTimer.singleShot(40, self._scroll_end)
        return bubble

    def start_stream(self) -> MessageBubble:
        bubble = MessageBubble("agent", "")
        self._insert(bubble)
        self._streaming_bubble = bubble
        return bubble

    def append_stream(self, chunk: str) -> None:
        if self._streaming_bubble is None:
            return
        if self._streaming_bubble._is_placeholder:
            self._streaming_bubble._buffer = chunk
            self._streaming_bubble._is_placeholder = False
        else:
            self._streaming_bubble._buffer += chunk
        self._streaming_bubble._render()
        QTimer.singleShot(0, self._scroll_end)

    def update_stream_status(self, status: str) -> None:
        """Show italic status in the active streaming bubble (placeholder phase only)."""
        if self._streaming_bubble is not None and self._streaming_bubble._is_placeholder:
            self._streaming_bubble.show_status(status)

    def finish_stream(self) -> None:
        self._streaming_bubble = None

    def clear_messages(self) -> None:
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    # ── private ─────────────────────────────────────────────────────────
    def _insert(self, bubble: MessageBubble) -> None:
        # Insert before the trailing stretch
        self._vbox.insertWidget(self._vbox.count() - 1, bubble)

    def _scroll_end(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


# ── Top Bar ────────────────────────────────────────────────────────────────
class TopBar(QFrame):
    """38px semi-transparent header bar."""

    left_panel_toggled  = Signal()
    right_panel_toggled = Signal()
    palette_requested   = Signal()
    expediente_clicked  = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(TOP_H)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)

        # Hamburger — left panel
        self._menu_btn = QPushButton("☰")
        self._menu_btn.setObjectName("topBtn")
        self._menu_btn.setFixedSize(32, 28)
        self._menu_btn.setToolTip("Panel izquierdo  ⌘⇧L")
        self._menu_btn.clicked.connect(self.left_panel_toggled)
        lay.addWidget(self._menu_btn)

        # App title
        title = QLabel("ADV ARCHON")
        title.setObjectName("appTitle")
        lay.addWidget(title)

        lay.addStretch()

        # Active expediente pill
        self._exp_pill = QPushButton("Sin expediente")
        self._exp_pill.setObjectName("expPill")
        self._exp_pill.setToolTip("Expediente activo — clic para cambiar")
        self._exp_pill.clicked.connect(self.expediente_clicked)
        lay.addWidget(self._exp_pill)

        lay.addStretch()

        # Mode icon
        self._mode_ico = QLabel("💻")
        self._mode_ico.setObjectName("topIcon")
        self._mode_ico.setToolTip("Modo: local")
        lay.addWidget(self._mode_ico)

        # Theme / palette shortcut
        self._theme_btn = QPushButton("⌘K")
        self._theme_btn.setObjectName("topBtn")
        self._theme_btn.setFixedSize(38, 26)
        self._theme_btn.setToolTip("Paleta de comandos  ⌘K")
        self._theme_btn.clicked.connect(self.palette_requested)
        lay.addWidget(self._theme_btn)

        # Right panel toggle
        self._ctx_btn = QPushButton("▥")
        self._ctx_btn.setObjectName("topBtn")
        self._ctx_btn.setFixedSize(32, 28)
        self._ctx_btn.setToolTip("Panel de contexto  ⌘⇧R")
        self._ctx_btn.clicked.connect(self.right_panel_toggled)
        lay.addWidget(self._ctx_btn)

    def set_expediente(self, name: str) -> None:
        text = (name[:32] + "…") if len(name) > 32 else name
        self._exp_pill.setText(f"📋  {text}" if name else "Sin expediente")

    def set_mode(self, mode: str) -> None:
        self._mode_ico.setText("🌐" if mode == "cloud" else "💻")
        self._mode_ico.setToolTip(f"Modo: {mode}")


# ── Left Panel ─────────────────────────────────────────────────────────────
class LeftPanel(QFrame):
    """Collapsible left navigation: profile/mode, expediente list, actions."""

    expediente_selected     = Signal(str)   # expediente id
    new_expediente_requested = Signal()
    command_triggered       = Signal(str)
    profile_changed         = Signal(str)   # new profile name

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("leftPanel")
        self.setMinimumWidth(0)
        self._profiles: list[str] = ["general"]

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Profile + mode row
        row = QHBoxLayout()
        self._profile_btn = QPushButton("general")
        self._profile_btn.setObjectName("miniSelector")
        self._profile_btn.setFixedHeight(26)
        self._profile_btn.clicked.connect(self._show_profile_menu)
        self._mode_btn = QPushButton("local")
        self._mode_btn.setObjectName("miniSelector")
        self._mode_btn.setFixedHeight(26)
        self._mode_btn.clicked.connect(self._toggle_mode)
        row.addWidget(self._profile_btn)
        row.addWidget(self._mode_btn)
        lay.addLayout(row)

        # Search
        self._search = QLineEdit()
        self._search.setObjectName("sideSearch")
        self._search.setPlaceholderText("Buscar expediente…")
        self._search.textChanged.connect(self._filter)
        lay.addWidget(self._search)

        # Section label
        sec = QLabel("RECIENTES")
        sec.setObjectName("sectionLabel")
        lay.addWidget(sec)

        # Expediente list
        self._list = QListWidget()
        self._list.setObjectName("sideList")
        self._list.setMaximumHeight(180)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.itemClicked.connect(
            lambda item: self.expediente_selected.emit(
                item.data(Qt.ItemDataRole.UserRole) or ""
            )
        )
        lay.addWidget(self._list)

        self._all_items: list[tuple[str, str, str]] = []   # (id, title, municipality)

        # New expediente
        new_btn = QPushButton("＋  Nuevo expediente")
        new_btn.setObjectName("newExpBtn")
        new_btn.setFixedHeight(34)
        new_btn.clicked.connect(self.new_expediente_requested)
        lay.addWidget(new_btn)

        lay.addStretch()

        # "Más…" dropdown
        more_btn = QPushButton("Más…")
        more_btn.setObjectName("moreBtn")
        more_btn.setFixedHeight(26)
        menu = QMenu(more_btn)
        for label, cid in [
            ("Research Workbench", "research"),
            ("Training Lab",       "training"),
            ("Studio Demo",        "studio_demo"),
            ("Estado PGOU",        "pgou_status"),
            ("─────────────", None),
            ("Ajustes",            "settings"),
            ("QA permisos",        "qa_system"),
            ("Estado sistema",     "system_status"),
            ("Guía beta",          "beta_guide"),
            ("Atajos de teclado",  "shortcuts"),
        ]:
            if cid is None:
                menu.addSeparator()
                continue
            act = menu.addAction(label)
            act.triggered.connect(
                lambda _=False, c=cid: self.command_triggered.emit(c)
            )
        more_btn.setMenu(menu)
        lay.addWidget(more_btn)

        # Footer status
        self._footer = QLabel("⬡  ADV ARCHON  ·  Beta 0.1")
        self._footer.setObjectName("sideFooter")
        lay.addWidget(self._footer)

        self._current_mode = "local"

    # ── public API ──────────────────────────────────────────────────────
    def set_expedientes(self, exps: list[dict]) -> None:
        self._all_items = [
            (e.get("id", ""), e.get("title", "—"), e.get("municipality", ""))
            for e in exps
        ]
        self._render(self._all_items)

    def set_ollama_status(self, active: bool) -> None:
        dot = '<span style="color:#22C55E">●</span>' if active else '<span style="color:#888">○</span>'  # noqa: E501
        self._footer.setText(f"{dot}  Ollama  ·  Beta 0.1")

    def set_mode_display(self, mode: str) -> None:
        self._current_mode = mode
        self._mode_btn.setText(mode)

    def set_profiles(self, profiles: list[str], active: str = "general") -> None:
        self._profiles = profiles or ["general"]
        self._profile_btn.setText(active)

    def set_active_profile(self, profile: str) -> None:
        self._profile_btn.setText(profile)

    # ── private ─────────────────────────────────────────────────────────
    def _toggle_mode(self) -> None:
        new = "cloud" if self._current_mode == "local" else "local"
        self.set_mode_display(new)
        self.command_triggered.emit(f"mode_{new}")

    def _show_profile_menu(self) -> None:
        menu = QMenu(self._profile_btn)
        current = self._profile_btn.text()
        for p in self._profiles:
            act = menu.addAction(("✓  " if p == current else "    ") + p)
            act.triggered.connect(
                lambda _=False, name=p: self._select_profile(name)
            )
        menu.exec(self._profile_btn.mapToGlobal(
            self._profile_btn.rect().bottomLeft()
        ))

    def _select_profile(self, name: str) -> None:
        self._profile_btn.setText(name)
        self.profile_changed.emit(name)

    def _filter(self, query: str) -> None:
        q = query.lower()
        filtered = [
            (eid, t, m) for eid, t, m in self._all_items
            if not q or q in t.lower() or q in m.lower()
        ]
        self._render(filtered)

    def _render(self, items: list[tuple[str, str, str]]) -> None:
        self._list.clear()
        for eid, title, muni in items[:5]:
            text = f"{title}" + (f"\n{muni}" if muni else "")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, eid)
            self._list.addItem(item)


# ── Right Panel ────────────────────────────────────────────────────────────
class RightPanel(QFrame):
    """Collapsible right context panel with tabs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setMinimumWidth(0)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("contextTabs")
        lay.addWidget(self._tabs)

        # Tab 0 — Contexto
        self._ctx_view = QTextBrowser()
        self._ctx_view.setObjectName("ctxView")
        self._ctx_view.setOpenExternalLinks(False)
        self._tabs.addTab(self._ctx_view, "Contexto")

        # Tab 1 — Herramientas
        tools_w = QWidget()
        tools_w.setObjectName("toolsWidget")
        self._tools_lay = QVBoxLayout(tools_w)
        self._tools_lay.setContentsMargins(8, 8, 8, 8)
        self._tools_lay.setSpacing(4)
        self._tools_lay.addStretch()
        scroll_t = QScrollArea()
        scroll_t.setWidgetResizable(True)
        scroll_t.setWidget(tools_w)
        scroll_t.setFrameShape(QFrame.Shape.NoFrame)
        self._tabs.addTab(scroll_t, "Herr.")

        # Tab 2 — Fuentes
        self._sources = QListWidget()
        self._sources.setObjectName("sourcesList")
        self._tabs.addTab(self._sources, "Fuentes")

        # Tab 3 — Historial
        self._history = QListWidget()
        self._history.setObjectName("historyList")
        self._tabs.addTab(self._history, "Historial")

        # Tab 4 — Adjuntos
        attach_w = QWidget()
        attach_w.setObjectName("attachWidget")
        self._attach_lay = QVBoxLayout(attach_w)
        self._attach_lay.setContentsMargins(8, 8, 8, 8)
        self._attach_lay.addStretch()
        scroll_a = QScrollArea()
        scroll_a.setWidgetResizable(True)
        scroll_a.setWidget(attach_w)
        scroll_a.setFrameShape(QFrame.Shape.NoFrame)
        self._tabs.addTab(scroll_a, "Adjuntos")

    # ── public API ──────────────────────────────────────────────────────
    def set_context(self, markdown: str) -> None:
        self._ctx_view.setMarkdown(markdown)
        self._tabs.setCurrentIndex(0)

    def add_tool(self, name: str) -> None:
        badge = QLabel(f"  ✦  {name}")
        badge.setObjectName("toolBadge")
        badge.setFixedHeight(24)
        self._tools_lay.insertWidget(self._tools_lay.count() - 1, badge)
        self._tabs.setCurrentIndex(1)

    def clear_tools(self) -> None:
        while self._tools_lay.count() > 1:
            item = self._tools_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def add_source(self, source: str) -> None:
        self._sources.insertItem(0, source)
        self._tabs.setCurrentIndex(2)

    def add_history(self, timestamp: str, text: str) -> None:
        self._history.insertItem(0, f"{timestamp}  {text}")

    def add_attachment(self, path: Path) -> None:
        ext  = path.suffix.lower()
        icon = "📄" if ext == ".pdf" else "🖼" if ext in (".png", ".jpg", ".jpeg") else "📎"
        name = path.name[:22] + "…" if len(path.name) > 22 else path.name
        lbl  = QLabel(f"{icon}  {name}")
        lbl.setObjectName("attachLabel")
        self._attach_lay.insertWidget(self._attach_lay.count() - 1, lbl)


# ── Command Palette ────────────────────────────────────────────────────────
class CommandPalette(QDialog):
    """
    Cmd+K command palette.  Filtered list of all commands.
    Emits command_selected(id) when user activates a row.
    """

    command_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("cmdPalette")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(580)
        self.setMaximumHeight(500)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._inner = QFrame()
        self._inner.setObjectName("paletteInner")
        inner_lay = QVBoxLayout(self._inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(0)
        lay.addWidget(self._inner)

        # Search
        self._filter = QLineEdit()
        self._filter.setObjectName("paletteSearch")
        self._filter.setPlaceholderText("  Buscar comando…")
        self._filter.setFixedHeight(48)
        self._filter.textChanged.connect(self._populate)
        inner_lay.addWidget(self._filter)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("palSep")
        inner_lay.addWidget(sep)

        # Results
        self._results = QListWidget()
        self._results.setObjectName("paletteList")
        self._results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._results.itemActivated.connect(self._activate)
        inner_lay.addWidget(self._results)

        self._populate("")

    def open_at(self, parent_window: QWidget) -> None:
        w = parent_window.width()
        h = parent_window.height()
        x = parent_window.x() + w // 2 - self.width() // 2
        y = parent_window.y() + h // 4
        self.move(x, max(y, 30))
        self._filter.clear()
        self._populate("")
        self.show()
        self._filter.setFocus()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.hide()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self._results.currentItem()
            if item:
                self._activate(item)
            return
        if key == Qt.Key.Key_Up:
            self._move_selection(-1)
            return
        if key == Qt.Key.Key_Down:
            self._move_selection(1)
            return
        super().keyPressEvent(event)

    # ── private ─────────────────────────────────────────────────────────
    def _populate(self, query: str = "") -> None:
        self._results.clear()
        q = query.lower().strip()
        filtered = [
            c for c in COMMANDS
            if not q or q in c.label.lower() or q in c.category.lower() or q in c.icon
        ]

        current_cat = ""
        for cmd in filtered:
            if cmd.category != current_cat:
                current_cat = cmd.category
                header = QListWidgetItem(f"   {current_cat.upper()}")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                f = header.font()
                f.setPointSize(9)
                header.setFont(f)
                self._results.addItem(header)

            row_text = f"   {cmd.icon}   {cmd.label}"
            if cmd.shortcut:
                row_text += f"   {cmd.shortcut}"
            item = QListWidgetItem(row_text)
            item.setData(Qt.ItemDataRole.UserRole, cmd.id)
            self._results.addItem(item)

        # Select first enabled item
        for i in range(self._results.count()):
            it = self._results.item(i)
            if it and (it.flags() & Qt.ItemFlag.ItemIsEnabled):
                self._results.setCurrentRow(i)
                break

    def _activate(self, item: QListWidgetItem) -> None:
        cmd_id = item.data(Qt.ItemDataRole.UserRole)
        if cmd_id:
            self.command_selected.emit(cmd_id)
            self.hide()

    def _move_selection(self, delta: int) -> None:
        row = self._results.currentRow()
        count = self._results.count()
        row = (row + delta) % count
        # skip non-selectable headers
        attempts = 0
        while attempts < count:
            it = self._results.item(row)
            if it and (it.flags() & Qt.ItemFlag.ItemIsEnabled):
                self._results.setCurrentRow(row)
                return
            row = (row + delta) % count
            attempts += 1


# ── Floating Contextual Toolbar ────────────────────────────────────────────
class FloatingToolbar(QFrame):
    """
    Small toolbar that appears near selected text or a clicked expediente.
    Auto-hides after 4 seconds of inactivity.
    """

    action_triggered = Signal(str)

    _ACTIONS = [
        ("pgou_analyze",  "⚖ PGOU"),
        ("doc_pdf",       "📄 PDF"),
        ("memory_add",    "🧠 Memoria"),
        ("voice_talk",    "🎤 Hablar"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint,  # type: ignore[arg-type]
        )
        self.setObjectName("floatingToolbar")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(4)

        for aid, label in self._ACTIONS:
            btn = QPushButton(label)
            btn.setObjectName("floatBtn")
            btn.setFixedHeight(26)
            btn.clicked.connect(
                lambda _=False, a=aid: self.action_triggered.emit(a)
            )
            lay.addWidget(btn)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_near(self, global_pos: QPoint) -> None:
        self.adjustSize()
        self.move(global_pos.x() - self.width() // 2, global_pos.y() - self.height() - 8)
        self.show()
        self._timer.start(4000)


# ── Main Window ────────────────────────────────────────────────────────────
class RedesignedMainWindow(QMainWindow):
    """
    ADV ARCHON v2 — minimalist single-canvas conversational window.
    See module docstring for integration guide.
    """

    prompt_submitted  = Signal(str, list)   # (text, list[Path])
    command_triggered = Signal(str)         # command id

    def __init__(
        self,
        runtime: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runtime    = runtime
        self._dark       = _is_dark()
        self._left_open  = False
        self._right_open = False
        self._model_name = "llama3.2:3b"
        self._mode       = "local"
        self._active_exp: dict | None = None

        self._build_window()
        self._build_ui()
        self._setup_shortcuts()
        self._load_styles()
        self._watch_system_palette()

        if runtime is not None:
            self._wire_runtime(runtime)

    # ═══════════════════════════════════════════════════════════════════
    # Inbound API — push events from the runtime into the window
    # ═══════════════════════════════════════════════════════════════════

    def receive_chunk(self, chunk: str) -> None:
        """Append one streaming token to the active agent bubble."""
        self._chat.append_stream(chunk)

    def receive_tool_call(self, name: str) -> None:
        """Show a tool badge in the right panel and auto-open it."""
        self._right.add_tool(name)
        if not self._right_open:
            self._toggle_right()

    def receive_source(self, source: str) -> None:
        """Add an entry to the Sources tab."""
        self._right.add_source(source)

    def receive_final(self) -> None:
        """Mark the streaming bubble as complete."""
        self._chat.finish_stream()
        self._composer.set_enabled_input(True)

    def set_expediente(self, exp: dict) -> None:
        """Update the active expediente across the whole UI."""
        self._active_exp = exp
        title = exp.get("title", "")
        self._topbar.set_expediente(title)
        self._right.set_context(self._build_context_md(exp))
        self._refresh_status()
        # Auto-open right panel on first expediente selection
        if not self._right_open:
            self._toggle_right()

    def set_model(self, model: str) -> None:
        self._model_name = model
        self._refresh_status()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._topbar.set_mode(mode)
        self._left.set_mode_display(mode)
        self._refresh_status()

    def set_expediente_list(self, exps: list[dict]) -> None:
        self._left.set_expedientes(exps)

    def set_runtime(self, runtime: Any) -> None:
        self._runtime = runtime
        self._wire_runtime(runtime)

    # ═══════════════════════════════════════════════════════════════════
    # Setup
    # ═══════════════════════════════════════════════════════════════════

    def _build_window(self) -> None:
        self.setWindowTitle("ADV ARCHON")
        self.setMinimumSize(QSize(900, 600))
        self.resize(QSize(1280, 800))

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────
        self._topbar = TopBar()
        self._topbar.left_panel_toggled.connect(self._toggle_left)
        self._topbar.right_panel_toggled.connect(self._toggle_right)
        self._topbar.palette_requested.connect(self._show_palette)
        self._topbar.expediente_clicked.connect(
            lambda: self.command_triggered.emit("exp_open")
        )
        root.addWidget(self._topbar)

        # ── Splitter: left | center | right ──────────────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("mainSplitter")
        self._splitter.setHandleWidth(1)
        self._splitter.setChildrenCollapsible(True)
        root.addWidget(self._splitter, stretch=1)

        # Left panel
        self._left = LeftPanel()
        self._left.expediente_selected.connect(
            lambda eid: self.command_triggered.emit(f"exp_open:{eid}")
        )
        self._left.new_expediente_requested.connect(
            lambda: self.command_triggered.emit("exp_new")
        )
        self._left.command_triggered.connect(self.command_triggered)
        self._splitter.addWidget(self._left)

        # Center: chat + composer
        center = QWidget()
        center.setObjectName("centerWidget")
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        self._chat = ChatArea()
        cl.addWidget(self._chat, stretch=1)

        self._composer = Composer()
        self._composer.submitted.connect(self._on_submit)
        self._composer.palette_requested.connect(self._show_palette)
        cl.addWidget(self._composer)

        self._splitter.addWidget(center)

        # Right panel
        self._right = RightPanel()
        self._splitter.addWidget(self._right)

        # Initial sizes: left collapsed, center full, right collapsed
        self._splitter.setSizes([0, 1280, 0])

        # Command palette (singleton)
        self._palette = CommandPalette(self)
        self._palette.command_selected.connect(self._on_command)

        # Floating toolbar
        self._floatbar = FloatingToolbar(self)
        self._floatbar.action_triggered.connect(self.command_triggered)

        # Welcome message
        self._chat.add_message(
            "agent",
            "**Hola.** Soy ADV ARCHON, tu asistente de arquitectura y urbanismo.\n\n"
            "Puedo analizar planos contra el PGOU, consultar fuentes oficiales, detectar "
            "riesgos jurídicos y generar informes PDF listos para entregar.\n\n"
            "Escribe tu consulta, arrastra un **plano PDF** al campo de texto, "
            "o pulsa **⌘K** para ver todos los comandos disponibles.",
        )

    def _setup_shortcuts(self) -> None:
        bindings: dict[str, Any] = {
            "Ctrl+K":       self._show_palette,
            "Ctrl+Shift+L": self._toggle_left,
            "Ctrl+Shift+R": self._toggle_right,
            "Ctrl+N":       lambda: self.command_triggered.emit("exp_new"),
            "Ctrl+O":       lambda: self.command_triggered.emit("exp_open"),
            "Ctrl+E":       lambda: self.command_triggered.emit("doc_pdf"),
        }
        for key, slot in bindings.items():
            QShortcut(QKeySequence(key), self).activated.connect(slot)

    # ═══════════════════════════════════════════════════════════════════
    # Panel toggles
    # ═══════════════════════════════════════════════════════════════════

    def _toggle_left(self) -> None:
        sizes = self._splitter.sizes()
        if self._left_open:
            new = [0, sizes[0] + sizes[1], sizes[2]]
            self._left_open = False
        else:
            take = LEFT_OPEN_W
            new = [take, max(sizes[0] + sizes[1] - take, 500), sizes[2]]
            self._left_open = True
        self._splitter.setSizes(new)

    def _toggle_right(self) -> None:
        sizes = self._splitter.sizes()
        if self._right_open:
            new = [sizes[0], sizes[1] + sizes[2], 0]
            self._right_open = False
        else:
            take = RIGHT_OPEN_W
            new = [sizes[0], max(sizes[1] - take, 500), take]
            self._right_open = True
        self._splitter.setSizes(new)

    # ═══════════════════════════════════════════════════════════════════
    # Command palette
    # ═══════════════════════════════════════════════════════════════════

    def _show_palette(self) -> None:
        self._palette.open_at(self)

    def _on_command(self, cmd_id: str) -> None:
        # Handle built-in UI commands directly; delegate the rest
        if cmd_id == "theme_toggle":
            self._toggle_theme()
            return
        if cmd_id == "mode_local":
            self.set_mode("local")
        elif cmd_id == "mode_cloud":
            self.set_mode("cloud")
        self.command_triggered.emit(cmd_id)

    # ═══════════════════════════════════════════════════════════════════
    # Submit
    # ═══════════════════════════════════════════════════════════════════

    def _on_submit(self, text: str, attachments: list[Path]) -> None:
        if not text and not attachments:
            return
        display = text or f"[{len(attachments)} archivo(s)]"
        self._chat.add_message("user", display)
        self._chat.start_stream()
        self._composer.set_enabled_input(False)
        # Add attachments to right panel
        for att in attachments:
            self._right.add_attachment(att)
        self.prompt_submitted.emit(text, attachments)

    # ═══════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════

    def _refresh_status(self) -> None:
        exp_name = (self._active_exp or {}).get("title", "Sin expediente")
        muni     = (self._active_exp or {}).get("municipality", "")
        parts    = [self._model_name, self._mode]
        if exp_name != "Sin expediente":
            parts.append(exp_name)
            if muni:
                parts.append(muni)
        self._composer.set_status("  ·  ".join(parts))

    @staticmethod
    def _build_context_md(exp: dict) -> str:
        lines: list[str] = [f"## {exp.get('title', 'Expediente')}\n"]
        for key, label in [
            ("municipality", "Municipio"),
            ("address",      "Dirección"),
            ("case_type",    "Tipo"),
            ("status",       "Estado"),
        ]:
            if exp.get(key):
                lines.append(f"**{label}:** {exp[key]}")
        if exp.get("extracted_params"):
            try:
                params = json.loads(exp["extracted_params"])
                lines.append("\n### Parámetros urbanísticos\n")
                for k, v in params.items():
                    if v:
                        lines.append(f"- **{k}:** {v}")
            except Exception:
                pass
        if exp.get("site_context"):
            try:
                ctx = json.loads(exp["site_context"])
                checks = ctx.get("legal_checks", [])
                if checks:
                    lines.append("\n### Afecciones\n")
                    for c in checks[:8]:
                        lines.append(f"- {c}")
            except Exception:
                pass
        return "\n".join(lines)

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._load_styles()

    def _watch_system_palette(self) -> None:
        app = QApplication.instance()
        if app is None or not hasattr(app, "paletteChanged"):
            return
        with contextlib.suppress(Exception):
            app.paletteChanged.connect(self._on_system_palette_changed)

    def _on_system_palette_changed(self, _palette: QPalette) -> None:
        dark = _is_dark()
        if dark == self._dark:
            return
        self._dark = dark
        self._load_styles()

    def _wire_runtime(self, runtime: Any) -> None:
        """Connect an ArchonRuntime (duck-typed) to this window."""
        with contextlib.suppress(Exception):
            self.set_mode(runtime.llm.mode)
        with contextlib.suppress(Exception):
            self.set_model(runtime.config.llm.ollama_model or "ollama")

    # ═══════════════════════════════════════════════════════════════════
    # Styles
    # ═══════════════════════════════════════════════════════════════════

    def _load_styles(self) -> None:
        qss_path = Path(__file__).parent / "style_v2.qss"
        base = (
            qss_path.read_text(encoding="utf-8")
            if qss_path.exists()
            else self._fallback_qss()
        )
        # Inject dark-mode overrides when needed
        if self._dark:
            base += "\n" + self._dark_overrides()
        QApplication.instance().setStyleSheet(base)  # type: ignore[union-attr]

    def _fallback_qss(self) -> str:
        b, c, t, s, br = BG_LIGHT, CARD_LIGHT, TEXT_PRI_LIGHT, TEXT_SEC_LIGHT, BORDER_LIGHT
        return f"""
            QMainWindow {{ background: {b}; }}
            QWidget#centralWidget, QWidget#centerWidget {{ background: {b}; }}
            QFrame#topBar {{
                background: rgba(247,244,239,0.95);
                border-bottom: 1px solid {br};
            }}
            QLabel#appTitle {{
                color: {t}; font-weight: 700; font-size: 13px; letter-spacing: 0.5px;
            }}
            QPushButton#topBtn {{
                background: transparent; border: none; color: {t}; font-size: 15px;
            }}
            QPushButton#topBtn:hover {{ background: rgba(0,0,0,0.06); border-radius: 6px; }}
            QPushButton#expPill {{
                background: {br}; color: {s}; border: none; border-radius: 10px;
                font-size: 11px; padding: 2px 12px;
            }}
            QFrame#composer {{
                background: {c}; border: 1px solid {br}; border-radius: 16px;
                margin: 10px 20px 12px 20px;
            }}
            QTextEdit#composerEdit {{
                background: transparent; border: none; color: {t}; font-size: 14px; padding: 2px;
            }}
            QLabel#statusLabel {{ color: {s}; font-size: 11px; }}
            QPushButton#cmdKBtn {{
                background: {br}; color: {s}; border: none;
                border-radius: 5px; font-size: 11px; padding: 0 8px;
            }}
            QPushButton#cmdKBtn:hover {{ background: {ACCENT}; color: #111; }}
            QFrame#chiclet {{
                background: {br}; border-radius: 11px;
            }}
            QLabel#chicletLabel {{ color: {t}; font-size: 12px; }}
            QPushButton#chicletRemove {{
                background: transparent; color: {s}; border: none;
                font-size: 12px; font-weight: bold;
            }}
            QScrollArea#chatArea {{ background: {b}; border: none; }}
            QWidget#chatContent {{ background: {b}; }}
            QFrame#bubble_user {{
                background: {USER_BG_LIGHT}; border-radius: 14px; max-width: 560px;
            }}
            QFrame#bubble_agent {{
                background: {AGENT_BG_LIGHT}; border-radius: 0px;
            }}
            QTextBrowser#bubbleView_user {{
                background: transparent; border: none; color: {t};
                font-size: 14px; max-width: 520px;
            }}
            QTextBrowser#bubbleView_agent {{
                background: transparent; border: none; color: {t}; font-size: 14px;
            }}
            QFrame#leftPanel {{ background: {PANEL_BG_LIGHT}; border-right: 1px solid {br}; }}
            QFrame#rightPanel {{ background: {PANEL_BG_LIGHT}; border-left: 1px solid {br}; }}
            QTabWidget#contextTabs::pane {{ border: none; background: {PANEL_BG_LIGHT}; }}
            QTabBar::tab {{
                background: transparent; color: {s}; padding: 4px 10px; font-size: 11px;
                border: none; border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {t}; border-bottom: 2px solid {ACCENT}; font-weight: bold;
            }}
            QLabel#sectionLabel {{
                color: {s}; font-size: 10px; font-weight: bold; letter-spacing: 1.2px;
            }}
            QLabel#sideFooter {{ color: {ACCENT}; font-size: 10px; }}
            QPushButton#newExpBtn {{
                background: {ACCENT}; color: #111; font-weight: 700; border: none;
                border-radius: 7px; font-size: 13px;
            }}
            QPushButton#newExpBtn:hover {{ background: #D4AF60; }}
            QPushButton#miniSelector {{
                background: {br}; color: {t}; border: none; border-radius: 5px; font-size: 11px;
            }}
            QPushButton#moreBtn {{
                background: transparent; color: {s};
                border: 1px solid {br}; border-radius: 5px; font-size: 12px;
            }}
            QLineEdit#sideSearch {{
                background: {c}; border: 1px solid {br}; border-radius: 7px;
                padding: 4px 10px; font-size: 12px; color: {t};
            }}
            QListWidget#sideList {{
                background: transparent; border: none; color: {t}; font-size: 12px;
            }}
            QListWidget#sideList::item:selected {{ background: {br}; border-radius: 5px; }}
            QListWidget#sideList::item:hover {{ background: rgba(0,0,0,0.04); border-radius: 5px; }}
            QFrame#paletteInner {{
                background: {c}; border: 1px solid {br}; border-radius: 14px;
            }}
            QLineEdit#paletteSearch {{
                background: transparent; border: none; font-size: 16px;
                padding: 0 18px; color: {t};
            }}
            QFrame#palSep {{ color: {br}; background: {br}; max-height: 1px; }}
            QListWidget#paletteList {{
                background: transparent; border: none; color: {t}; font-size: 13px;
            }}
            QListWidget#paletteList::item:selected {{ background: {br}; border-radius: 6px; }}
            QLabel#toolBadge {{
                background: rgba(201,168,76,0.15); color: {ACCENT}; border-radius: 4px;
                font-size: 11px; padding: 0 6px;
            }}
            QLabel#attachLabel {{ color: {t}; font-size: 12px; }}
            QFrame#floatingToolbar {{
                background: {c}; border: 1px solid {br}; border-radius: 10px;
            }}
            QPushButton#floatBtn {{
                background: transparent; border: none; color: {t};
                font-size: 12px; padding: 2px 8px;
            }}
            QPushButton#floatBtn:hover {{ background: {br}; border-radius: 5px; }}
            QSplitter#mainSplitter::handle {{ background: {br}; width: 1px; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {br}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """

    def _dark_overrides(self) -> str:
        b, c, t, s, br = BG_DARK, CARD_DARK, TEXT_PRI_DARK, TEXT_SEC_DARK, BORDER_DARK
        return f"""
            /* ── Base ── */
            QMainWindow {{ background: {b}; }}
            QWidget {{ background: {b}; color: {t}; }}
            QWidget#centralWidget, QWidget#centerWidget, QWidget#chatContent {{ background: {b}; }}

            /* ── Top bar ── */
            QFrame#topBar {{
                background: rgba(28,28,30,0.96);
                border-bottom: 1px solid {br};
            }}
            QLabel#appTitle {{ color: {t}; }}
            QPushButton#topBtn {{
                color: {t}; background: transparent; border: none;
            }}
            QPushButton#topBtn:hover {{ background: rgba(255,255,255,0.09); }}
            QPushButton#topBtn:pressed {{ background: rgba(255,255,255,0.14); }}
            QPushButton#expPill {{
                background: {br}; color: {s}; border: none;
            }}
            QPushButton#expPill:hover {{ background: {ACCENT}; color: #111; }}

            /* ── Chat ── */
            QScrollArea#chatArea {{ background: {b}; border: none; }}
            QFrame#bubble_user {{ background: {USER_BG_DARK}; border-radius: 14px; }}
            QFrame#bubble_agent {{ background: transparent; }}
            QTextBrowser#bubbleView_user {{
                background: transparent; border: none; color: {t}; font-size: 14px;
            }}
            QTextBrowser#bubbleView_agent {{
                background: transparent; border: none; color: {t}; font-size: 14px;
            }}

            /* ── Composer ── */
            QFrame#composer {{
                background: {c}; border: 1px solid {br}; border-radius: 16px;
            }}
            QTextEdit#composerEdit {{
                background: transparent; color: {t}; border: none; font-size: 14px;
            }}
            QLabel#statusLabel {{ color: {s}; font-size: 11px; }}
            QPushButton#cmdKBtn {{
                background: {br}; color: {s}; border: none; border-radius: 5px;
            }}
            QPushButton#cmdKBtn:hover {{ background: {ACCENT}; color: #111; }}

            /* ── Chiclets ── */
            QFrame#chiclet {{ background: {br}; border-radius: 11px; }}
            QLabel#chicletLabel {{ color: {t}; }}
            QPushButton#chicletRemove {{ color: {s}; background: transparent; border: none; }}

            /* ── Left panel ── */
            QFrame#leftPanel {{
                background: {PANEL_BG_DARK}; border-right: 1px solid {br};
            }}
            QLabel#sectionLabel {{ color: {s}; font-size: 10px; font-weight: bold; }}
            QLabel#sideFooter {{ color: {ACCENT}; font-size: 10px; }}
            QLineEdit#sideSearch {{
                background: #2C2C2E; border: 1px solid {br};
                border-radius: 7px; color: {t}; font-size: 12px; padding: 4px 10px;
            }}
            QLineEdit#sideSearch:focus {{ border-color: {ACCENT}; }}
            QListWidget#sideList {{
                background: transparent; border: none; color: {t}; font-size: 12px;
            }}
            QListWidget#sideList::item {{ padding: 5px 8px; border-radius: 6px; }}
            QListWidget#sideList::item:selected {{
                background: {br}; color: {t};
            }}
            QListWidget#sideList::item:hover {{ background: rgba(255,255,255,0.06); }}
            QPushButton#newExpBtn {{
                background: {ACCENT}; color: #111; font-weight: 700;
                border: none; border-radius: 8px;
            }}
            QPushButton#newExpBtn:hover {{ background: #D4AF60; }}
            QPushButton#miniSelector {{
                background: {br}; color: {t}; border: none; border-radius: 5px;
            }}
            QPushButton#miniSelector:hover {{ background: #4A4A4C; }}
            QPushButton#moreBtn {{
                background: transparent; color: {s};
                border: 1px solid {br}; border-radius: 6px;
            }}
            QPushButton#moreBtn:hover {{ color: {t}; border-color: {ACCENT}; }}

            /* ── Right panel ── */
            QFrame#rightPanel {{
                background: {PANEL_BG_DARK}; border-left: 1px solid {br};
            }}
            QTabWidget#contextTabs::pane {{ border: none; background: {PANEL_BG_DARK}; }}
            QTabBar {{ background: transparent; }}
            QTabBar::tab {{
                background: transparent; color: {s};
                padding: 6px 12px; font-size: 11px;
                border: none; border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {t}; border-bottom: 2px solid {ACCENT}; font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{ color: {t}; }}
            QTextBrowser#ctxView {{
                background: transparent; border: none; color: {t}; font-size: 12px;
            }}
            QListWidget#sourcesList, QListWidget#historyList {{
                background: transparent; border: none; color: {t}; font-size: 12px;
            }}
            QListWidget#sourcesList::item, QListWidget#historyList::item {{
                padding: 4px 8px; border-radius: 4px;
            }}
            QListWidget#sourcesList::item:hover, QListWidget#historyList::item:hover {{
                background: rgba(255,255,255,0.06);
            }}
            QLabel#toolBadge {{
                background: rgba(201,168,76,0.18); color: {ACCENT};
                border-radius: 5px; font-size: 11px; padding: 0 8px;
            }}

            /* ── Command palette ── */
            QDialog#cmdPalette {{ background: transparent; }}
            QFrame#paletteInner {{
                background: #2C2C2E; border: 1px solid {br}; border-radius: 14px;
            }}
            QLineEdit#paletteSearch {{
                background: transparent; border: none; color: {t}; font-size: 16px; padding: 0 18px;
            }}
            QFrame#palSep {{ background: {br}; max-height: 1px; border: none; }}
            QListWidget#paletteList {{
                background: transparent; border: none; color: {t}; font-size: 13px;
            }}
            QListWidget#paletteList::item {{
                padding: 6px 10px; border-radius: 6px; margin: 0 6px;
            }}
            QListWidget#paletteList::item:selected {{ background: {br}; }}
            QListWidget#paletteList::item:hover {{ background: rgba(255,255,255,0.06); }}

            /* ── Floating toolbar ── */
            QFrame#floatingToolbar {{
                background: #2C2C2E; border: 1px solid {br}; border-radius: 10px;
            }}
            QPushButton#floatBtn {{
                background: transparent; border: none; color: {t}; font-size: 12px;
            }}
            QPushButton#floatBtn:hover {{ background: {br}; border-radius: 5px; }}

            /* ── Infrastructure ── */
            QSplitter#mainSplitter::handle {{ background: {br}; width: 1px; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: #555557; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #6E6E70; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """
