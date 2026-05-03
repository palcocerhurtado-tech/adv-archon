# mypy: ignore-errors
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from adv_archon.core.attachments import normalize_attachment_paths
from adv_archon.core.config import AppConfig
from adv_archon.core.llm import LLMRouter
from adv_archon.core.profiles import ProfileManager
from adv_archon.desktop.branding import desktop_stylesheet, logo_path
from adv_archon.desktop.compliance_session import (
    ComplianceSession,
    build_compliance_prompt,
    build_coordinate_compliance_prompt,
    build_municipality_ask_prompt,
    extract_coordinate_hint,
    extract_municipality_hint,
)
from adv_archon.desktop.presenters import (
    build_history_entry,
    format_sources_summary,
    merge_recent_items,
    recommended_window_size,
)
from adv_archon.desktop.warmup_agent import start_warmup_agent


def launch_desktop_app(
    *,
    config: AppConfig,
    llm: LLMRouter,
    project_root: Path,
    system_prompt: str,
    incognito: bool = False,
) -> int:
    try:
        from PySide6.QtCore import (
            QEasingCurve,
            QObject,
            QPropertyAnimation,
            QSizeF,
            Qt,
            QThread,
            QTimer,
            Signal,
        )
        from PySide6.QtGui import QAction, QIcon, QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QFileDialog,
            QFrame,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QScrollArea,
            QSizePolicy,
            QSplitter,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "La app de escritorio necesita PySide6. Instálalo con "
            "`uv pip install PySide6` o añade el extra desktop antes de lanzarla."
        ) from exc

    from adv_archon.core.agent import TurnContextSnapshot
    from adv_archon.desktop.workers import DesktopBusyState, DesktopRuntimeWorker

    # ── Confirm bridge ────────────────────────────────────────────────────────
    class ConfirmBridge(QObject):
        requested = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self._accepted = False
            self._waiting = None

        def ask(self, question: str) -> bool:
            import threading
            waiting = threading.Event()
            self._accepted = False
            self._waiting = waiting
            self.requested.emit(question)
            waiting.wait()
            return self._accepted

        def resolve(self, accepted: bool) -> None:
            self._accepted = accepted
            if self._waiting is not None:
                self._waiting.set()
                self._waiting = None

    # ── Drag-and-drop frame ───────────────────────────────────────────────────
    class _DropZoneFrame(QFrame):
        files_dropped = Signal(list)

        def __init__(self) -> None:
            super().__init__()
            self.setObjectName("DropZone")
            self.setAcceptDrops(True)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(8, 8, 8, 8)
            lbl = QLabel("Suelta archivos aquí para adjuntarlos")
            lbl.setObjectName("Sub")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl)
            self.setFixedHeight(46)
            self.setVisible(False)

        def dragEnterEvent(self, ev) -> None:
            if ev.mimeData().hasUrls():
                self.setVisible(True)
                ev.acceptProposedAction()
            else:
                ev.ignore()

        def dragLeaveEvent(self, ev) -> None:
            self.setVisible(False)

        def dropEvent(self, ev) -> None:
            self.setVisible(False)
            paths = [Path(u.toLocalFile()) for u in ev.mimeData().urls() if u.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths)
                ev.acceptProposedAction()
            else:
                ev.ignore()

    # ── Auto-sizing read-only text widget (for streaming) ────────────────────
    class _AutoTextEdit(QTextEdit):
        """Read-only QTextEdit that shrinks/grows to fit its content."""

        def __init__(self) -> None:
            super().__init__()
            self.setReadOnly(True)
            self.setFrameShape(QFrame.Shape.NoFrame)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.document().contentsChanged.connect(self._adjust)
            self._adjust()

        def _adjust(self) -> None:
            self.document().setPageSize(QSizeF(max(self.viewport().width(), 200), -1))
            h = int(self.document().size().height()) + 6
            self.setFixedHeight(max(h, 20))

        def resizeEvent(self, ev) -> None:
            super().resizeEvent(ev)
            self._adjust()

    # ── Main window ───────────────────────────────────────────────────────────
    class DesktopWindow(QMainWindow):
        prompt_requested = Signal(str, object)
        import_requested = Signal(object)
        mode_requested   = Signal(str)
        profile_requested = Signal(str)
        cancel_requested  = Signal()
        shutdown_requested = Signal()

        def __init__(self) -> None:
            super().__init__()
            self._logo_path   = logo_path()
            self._logo_pixmap = (
                QPixmap(str(self._logo_path)) if self._logo_path.exists() else None
            )
            self.setWindowTitle("ADV ARCHON")
            self.setMinimumSize(1080, 720)
            if self._logo_pixmap is not None:
                self.setWindowIcon(QIcon(str(self._logo_path)))

            screen = QApplication.primaryScreen()
            if screen is not None:
                w, h = recommended_window_size(
                    screen.availableGeometry().width(),
                    screen.availableGeometry().height(),
                )
                self.resize(w, h)
            else:
                self.resize(1280, 860)

            self._compliance = ComplianceSession()
            self._warmup_agent_ref: tuple[Any, Any] | None = None

            self._confirm_bridge   = ConfirmBridge()
            self._confirm_bridge.requested.connect(self._show_confirmation_dialog)
            self._profile_manager  = ProfileManager(
                config.paths.profile_state_file,
                default_profile=config.profiles.default_profile,
                definitions=config.profiles.definitions,
            )
            self._selected_mode    = llm.mode
            self._selected_profile = self._profile_manager.active_profile
            self._attachments: list[Path] = []
            self._recent_history_entries: list[str] = []
            self._recent_attachment_entries: list[str] = []
            self._active_tool_names: list[str] = []
            self._last_snapshot: TurnContextSnapshot | None = None
            self._pending_prompt    = ""
            self._pending_attachments: list[Path] = []
            self._current_stream_edit: _AutoTextEdit | None = None
            self._current_stream_text = ""
            self._progress_animation  = None
            self._busy_state = DesktopBusyState(
                backend_ready=False, busy=True, task="initializing"
            )
            self._close_requested = False

            # Worker
            self._backend_thread = QThread(self)
            self._backend_worker = DesktopRuntimeWorker(
                config=config,
                project_root=project_root,
                system_prompt=system_prompt,
                confirm=self._confirm_bridge.ask,
                incognito=incognito,
                initial_mode=self._selected_mode,
                initial_profile=self._selected_profile,
            )
            self._backend_worker.moveToThread(self._backend_thread)
            self.prompt_requested.connect(self._backend_worker.run_prompt)
            self.import_requested.connect(self._backend_worker.import_paths)
            self.mode_requested.connect(self._backend_worker.set_mode)
            self.profile_requested.connect(self._backend_worker.set_profile)
            self.cancel_requested.connect(self._backend_worker.cancel_prompt)
            self.shutdown_requested.connect(self._backend_worker.shutdown)
            self._backend_thread.started.connect(self._backend_worker.initialize)
            self._backend_worker.ready.connect(self._handle_backend_ready)
            self._backend_worker.busy_state_changed.connect(self._handle_busy_state_changed)
            self._backend_worker.chunk.connect(self._append_assistant_chunk)
            self._backend_worker.tool.connect(self._append_tool_event)
            self._backend_worker.context.connect(self._show_context_snapshot)
            self._backend_worker.prompt_finished.connect(self._handle_prompt_finished)
            self._backend_worker.import_finished.connect(self._handle_import_finished)
            self._backend_worker.failed.connect(self._handle_worker_error)
            self._backend_worker.cancelled.connect(self._handle_worker_cancelled)
            self._backend_worker.shutdown_finished.connect(self._handle_shutdown_finished)
            self._backend_thread.finished.connect(self._handle_backend_thread_finished)
            self._backend_thread.finished.connect(self._backend_worker.deleteLater)
            self._backend_thread.finished.connect(self._backend_thread.deleteLater)

            self._build_ui()
            self._apply_branding()
            self._load_controls_state()
            self._fit_to_screen()
            self._append_system("Preparando motor…")
            self._backend_thread.start()
            self._start_warmup_agent()

        # ── Lifecycle ─────────────────────────────────────────────────────────
        def closeEvent(self, ev) -> None:
            if self._backend_thread is None or not self._backend_thread.isRunning():
                ev.accept()
                return
            if self._close_requested:
                ev.ignore()
                return
            self._close_requested = True
            self.shutdown_requested.emit()
            ev.ignore()

        def showEvent(self, ev) -> None:
            super().showEvent(ev)
            self._fit_to_screen()

        # ── UI construction ───────────────────────────────────────────────────
        def _build_ui(self) -> None:
            root = QWidget()
            root.setObjectName("Root")
            self.setCentralWidget(root)
            outer = QHBoxLayout(root)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)

            outer.addWidget(self._build_sidebar())
            outer.addWidget(self._build_main_area(), 1)

            # Menu
            daily_action = QAction("Daily Brief", self)
            daily_action.triggered.connect(self._send_daily_prompt)
            self._daily_action = daily_action
            self.menuBar().addAction(daily_action)

        def _build_sidebar(self) -> QFrame:
            sidebar = QFrame()
            sidebar.setObjectName("Sidebar")
            sidebar.setFixedWidth(220)
            sl = QVBoxLayout(sidebar)
            sl.setContentsMargins(12, 18, 12, 18)
            sl.setSpacing(2)

            # Brand
            brand = QHBoxLayout()
            brand.setSpacing(10)
            brand.addWidget(self._make_logo(32))
            name_lbl = QLabel("ADV ARCHON")
            name_lbl.setObjectName("AppName")
            brand.addWidget(name_lbl, 1)
            sl.addLayout(brand)

            tagline = QLabel("ARQUITECTURA · IA")
            tagline.setObjectName("Eyebrow")
            sl.addWidget(tagline)
            sl.addSpacing(14)
            sl.addWidget(self._make_divider())
            sl.addSpacing(8)

            # Navigation
            self._nav_chat_btn = self._make_nav_btn("  Chat", active=True)
            self._nav_chat_btn.clicked.connect(lambda: self._send_nav_prompt(
                "resume nuestra sesión de trabajo"
            ))
            sl.addWidget(self._nav_chat_btn)

            self._nav_pgou_btn = self._make_nav_btn("  Análisis PGOU")
            self._nav_pgou_btn.clicked.connect(self._send_pgou_prompt)
            sl.addWidget(self._nav_pgou_btn)

            self._nav_geo_btn = self._make_nav_btn("  Geolocalización")
            self._nav_geo_btn.clicked.connect(self._send_geo_prompt)
            sl.addWidget(self._nav_geo_btn)

            self._nav_daily_btn = self._make_nav_btn("  Briefing diario")
            self._nav_daily_btn.clicked.connect(self._send_daily_prompt)
            sl.addWidget(self._nav_daily_btn)

            self._nav_exp_btn = self._make_nav_btn("  Expedientes")
            self._nav_exp_btn.clicked.connect(self._open_expedientes)
            sl.addWidget(self._nav_exp_btn)

            sl.addStretch(1)
            sl.addWidget(self._make_divider())
            sl.addSpacing(10)

            # Mode selector
            mode_lbl = QLabel("MODO")
            mode_lbl.setObjectName("Eyebrow")
            sl.addWidget(mode_lbl)
            self._mode_combo = QComboBox()
            self._mode_combo.addItems(["local", "cloud"])
            self._mode_combo.currentTextChanged.connect(self._change_mode)
            sl.addWidget(self._mode_combo)

            sl.addSpacing(8)

            # Profile selector
            profile_lbl = QLabel("PERFIL")
            profile_lbl.setObjectName("Eyebrow")
            sl.addWidget(profile_lbl)
            self._profile_combo = QComboBox()
            self._profile_combo.addItems(self._profile_manager.available_profiles())
            self._profile_combo.currentTextChanged.connect(self._change_profile)
            sl.addWidget(self._profile_combo)

            sl.addSpacing(6)
            self._mode_status_lbl = QLabel("")
            self._mode_status_lbl.setObjectName("Faint")
            self._mode_status_lbl.setWordWrap(True)
            sl.addWidget(self._mode_status_lbl)

            return sidebar

        def _build_main_area(self) -> QWidget:
            area = QWidget()
            al = QVBoxLayout(area)
            al.setContentsMargins(0, 0, 0, 0)
            al.setSpacing(0)

            al.addWidget(self._build_topbar())

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.setHandleWidth(1)
            splitter.setChildrenCollapsible(False)
            splitter.addWidget(self._build_chat_column())
            splitter.addWidget(self._build_right_panel())
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 1)
            splitter.setSizes([860, 300])

            al.addWidget(splitter, 1)
            return area

        def _build_topbar(self) -> QFrame:
            bar = QFrame()
            bar.setObjectName("TopBar")
            bar.setFixedHeight(44)
            tl = QHBoxLayout(bar)
            tl.setContentsMargins(16, 0, 16, 0)
            tl.setSpacing(12)

            self._status_label = QLabel("Inicializando…")
            self._status_label.setObjectName("Faint")
            tl.addWidget(self._status_label, 1)

            self._progress_bar = QProgressBar()
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setFixedWidth(110)
            self._progress_bar.setVisible(False)
            tl.addWidget(self._progress_bar)

            self._cancel_button = QPushButton("Cancelar")
            self._cancel_button.setObjectName("Ghost")
            self._cancel_button.setVisible(False)
            self._cancel_button.clicked.connect(self._cancel_active_task)
            tl.addWidget(self._cancel_button)

            return bar

        def _build_chat_column(self) -> QWidget:
            col = QWidget()
            cl = QVBoxLayout(col)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)

            # Scroll area for messages
            self._messages_scroll = QScrollArea()
            self._messages_scroll.setWidgetResizable(True)
            self._messages_scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._messages_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self._messages_container = QWidget()
            self._messages_layout = QVBoxLayout(self._messages_container)
            self._messages_layout.setContentsMargins(20, 20, 20, 12)
            self._messages_layout.setSpacing(4)
            self._messages_layout.addStretch(1)
            self._messages_scroll.setWidget(self._messages_container)
            cl.addWidget(self._messages_scroll, 1)

            # Drop zone
            self._drop_zone = _DropZoneFrame()
            self._drop_zone.files_dropped.connect(self._add_attachments)
            cl.addWidget(self._drop_zone)

            # Composer
            cl.addWidget(self._build_composer())
            return col

        def _build_composer(self) -> QFrame:
            frame = QFrame()
            frame.setObjectName("Composer")
            frame.setAcceptDrops(True)
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(14, 10, 14, 10)
            fl.setSpacing(8)

            # Attachment pills row (hidden when empty)
            self._pills_row = QHBoxLayout()
            self._pills_row.setSpacing(6)
            self._pills_row.addStretch(1)
            fl.addLayout(self._pills_row)

            # Input + send
            input_row = QHBoxLayout()
            input_row.setSpacing(10)

            self._input = QTextEdit()
            self._input.setAcceptRichText(False)
            self._input.setPlaceholderText(
                "Escribe tu consulta… (Ctrl+Enter para enviar)"
            )
            self._input.setFixedHeight(80)
            self._input.installEventFilter(self)
            input_row.addWidget(self._input, 1)

            btn_col = QVBoxLayout()
            btn_col.setSpacing(6)

            self._send_button = QPushButton("Enviar")
            self._send_button.setObjectName("Primary")
            self._send_button.clicked.connect(self._submit_prompt)
            btn_col.addWidget(self._send_button)

            self._add_button = QPushButton("Adjuntar")
            self._add_button.setObjectName("Ghost")
            self._add_button.clicked.connect(self._pick_attachments)
            btn_col.addWidget(self._add_button)

            self._import_button = QPushButton("→ KB")
            self._import_button.setObjectName("Ghost")
            self._import_button.setToolTip("Añadir adjuntos al knowledge base local")
            self._import_button.clicked.connect(self._import_attachments_to_kb)
            self._import_button.setVisible(False)
            btn_col.addWidget(self._import_button)

            self._analyze_button = QPushButton("Analizar plano")
            self._analyze_button.setObjectName("Primary")
            self._analyze_button.setToolTip(
                "Analizar cumplimiento normativo del plano PDF adjunto contra el PGOU"
            )
            self._analyze_button.clicked.connect(self._trigger_compliance_analysis)
            self._analyze_button.setVisible(False)
            btn_col.addWidget(self._analyze_button)

            btn_col.addStretch(1)
            input_row.addLayout(btn_col)
            fl.addLayout(input_row)

            # Drag events forwarded from composer frame
            frame.dragEnterEvent = self._drop_zone.dragEnterEvent
            frame.dragLeaveEvent = self._drop_zone.dragLeaveEvent
            frame.dropEvent      = self._drop_zone.dropEvent

            return frame

        def _build_right_panel(self) -> QFrame:
            panel = QFrame()
            panel.setObjectName("Panel")
            panel.setMinimumWidth(250)
            panel.setMaximumWidth(320)
            pl = QVBoxLayout(panel)
            pl.setContentsMargins(14, 16, 14, 16)
            pl.setSpacing(10)

            ctx_lbl = QLabel("CONTEXTO")
            ctx_lbl.setObjectName("Eyebrow")
            pl.addWidget(ctx_lbl)
            self._context_view = QPlainTextEdit()
            self._context_view.setReadOnly(True)
            self._context_view.setPlaceholderText("Intención, perfil, modo, checkpoint…")
            self._context_view.setMaximumHeight(160)
            pl.addWidget(self._context_view)

            tools_lbl = QLabel("HERRAMIENTAS")
            tools_lbl.setObjectName("Eyebrow")
            pl.addWidget(tools_lbl)
            self._tools_container = QWidget()
            self._tools_layout = QHBoxLayout(self._tools_container)
            self._tools_layout.setContentsMargins(0, 0, 0, 0)
            self._tools_layout.setSpacing(4)
            self._tools_layout.addStretch(1)
            pl.addWidget(self._tools_container)

            sources_lbl = QLabel("FUENTES")
            sources_lbl.setObjectName("Eyebrow")
            pl.addWidget(sources_lbl)
            self._sources_view = QPlainTextEdit()
            self._sources_view.setReadOnly(True)
            self._sources_view.setPlaceholderText("Memoria y conocimiento local del turno.")
            self._sources_view.setMaximumHeight(110)
            pl.addWidget(self._sources_view)

            hist_lbl = QLabel("HISTORIAL")
            hist_lbl.setObjectName("Eyebrow")
            pl.addWidget(hist_lbl)
            self._history_list = QListWidget()
            pl.addWidget(self._history_list, 1)

            recent_lbl = QLabel("ADJUNTOS RECIENTES")
            recent_lbl.setObjectName("Eyebrow")
            pl.addWidget(recent_lbl)
            self._recent_attachments_list = QListWidget()
            self._recent_attachments_list.setMaximumHeight(90)
            pl.addWidget(self._recent_attachments_list)

            # Compliance result card (hidden until analysis completes)
            self._compliance_card = QFrame()
            self._compliance_card.setObjectName("Card")
            self._compliance_card.setVisible(False)
            cc = QVBoxLayout(self._compliance_card)
            cc.setContentsMargins(10, 10, 10, 10)
            cc.setSpacing(6)
            comp_hdr = QLabel("INFORME NORMATIVO")
            comp_hdr.setObjectName("Eyebrow")
            cc.addWidget(comp_hdr)
            self._compliance_summary_lbl = QLabel("")
            self._compliance_summary_lbl.setObjectName("Sub")
            self._compliance_summary_lbl.setWordWrap(True)
            cc.addWidget(self._compliance_summary_lbl)
            self._compliance_stats_lbl = QLabel("")
            self._compliance_stats_lbl.setObjectName("Faint")
            cc.addWidget(self._compliance_stats_lbl)
            self._export_button = QPushButton("Exportar PDF")
            self._export_button.setObjectName("Primary")
            self._export_button.clicked.connect(self._export_compliance_report)
            cc.addWidget(self._export_button)
            pl.addWidget(self._compliance_card)

            return panel

        # ── Keyboard shortcut: Ctrl+Enter sends ───────────────────────────────
        def eventFilter(self, obj, ev) -> bool:
            from PySide6.QtCore import QEvent
            if obj is self._input and ev.type() == QEvent.Type.KeyPress:
                key_ev = ev
                ctrl = key_ev.modifiers() & Qt.KeyboardModifier.ControlModifier
                meta = key_ev.modifiers() & Qt.KeyboardModifier.MetaModifier
                enter = key_ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                if enter and (ctrl or meta):
                    self._submit_prompt()
                    return True
            return super().eventFilter(obj, ev)

        # ── Message bubble helpers ────────────────────────────────────────────
        def _add_message_bubble(
            self,
            role: str,
            text: str,
            *,
            attachments: list[Path] | None = None,
        ) -> None:
            frame = QFrame()
            frame.setObjectName("MsgUser" if role == "user" else "MsgAssistant")
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(12, 10, 12, 10)
            fl.setSpacing(4)

            # Header
            hdr = QHBoxLayout()
            hdr.setSpacing(8)
            role_lbl = QLabel("Tú" if role == "user" else "ADV ARCHON")
            role_lbl.setObjectName("RoleTagUser" if role == "user" else "RoleTag")
            hdr.addWidget(role_lbl)
            hdr.addStretch(1)
            ts = QLabel(datetime.now().strftime("%H:%M"))
            ts.setObjectName("Timestamp")
            hdr.addWidget(ts)
            fl.addLayout(hdr)

            # Content — read-only auto-sizing edit for proper word-wrap
            body = _AutoTextEdit()
            body.setPlainText(text)
            fl.addWidget(body)

            if attachments:
                for att in attachments:
                    att_lbl = QLabel(f"  {att.name}")
                    att_lbl.setObjectName("Sub")
                    fl.addWidget(att_lbl)

            self._insert_bubble(frame)

        def _start_assistant_stream(self) -> None:
            frame = QFrame()
            frame.setObjectName("MsgAssistant")
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(12, 10, 12, 10)
            fl.setSpacing(4)

            hdr = QHBoxLayout()
            hdr.setSpacing(8)
            role_lbl = QLabel("ADV ARCHON")
            role_lbl.setObjectName("RoleTag")
            hdr.addWidget(role_lbl)
            hdr.addStretch(1)
            ts = QLabel(datetime.now().strftime("%H:%M"))
            ts.setObjectName("Timestamp")
            hdr.addWidget(ts)
            fl.addLayout(hdr)

            self._current_stream_edit = _AutoTextEdit()
            self._current_stream_text = ""
            fl.addWidget(self._current_stream_edit)

            self._insert_bubble(frame)

        def _insert_bubble(self, frame: QFrame) -> None:
            idx = self._messages_layout.count() - 1  # before trailing stretch
            self._messages_layout.insertWidget(idx, frame)
            QTimer.singleShot(0, self._scroll_to_bottom)

        def _scroll_to_bottom(self) -> None:
            sb = self._messages_scroll.verticalScrollBar()
            sb.setValue(sb.maximum())

        def _add_notice(self, text: str, *, object_name: str = "Faint") -> None:
            lbl = QLabel(text)
            lbl.setObjectName(object_name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            idx = self._messages_layout.count() - 1
            self._messages_layout.insertWidget(idx, lbl)
            QTimer.singleShot(0, self._scroll_to_bottom)

        # ── Message rendering methods (called from signals) ────────────────────
        def _append_system(self, message: str) -> None:
            self._add_notice(message)

        def _append_user(self, prompt: str, attachments: list[Path]) -> None:
            self._add_message_bubble("user", prompt, attachments=attachments or None)

        def _append_assistant_prefix(self) -> None:
            self._start_assistant_stream()

        def _append_assistant_chunk(self, chunk: str) -> None:
            self._current_stream_text += chunk
            if self._current_stream_edit is not None:
                self._current_stream_edit.setPlainText(self._current_stream_text)
            QTimer.singleShot(0, self._scroll_to_bottom)

        def _append_tool_event(self, name: str, arguments: object) -> None:
            self._active_tool_names = merge_recent_items(
                self._active_tool_names, [name], limit=8
            )
            self._refresh_tool_badges()
            self._refresh_sources_view()
            if config.ui.show_tool_input:
                self._add_notice(f"[{name}]")

        def _show_context_snapshot(self, snapshot: object) -> None:
            if isinstance(snapshot, TurnContextSnapshot):
                self._last_snapshot = snapshot
                lines = [
                    f"Intent: {snapshot.intent}",
                    f"Perfil: {snapshot.profile}",
                    f"Modo: {snapshot.execution_mode}",
                    f"Checkpoint: {snapshot.checkpoint}",
                ]
                if snapshot.reasons:
                    lines.append(f"Señales: {', '.join(snapshot.reasons)}")
                if snapshot.confidence_hint:
                    lines.append(f"Confianza: {snapshot.confidence_hint}")
                if snapshot.memory_hits:
                    lines.append("Memoria:")
                    lines.extend(f"- {item}" for item in snapshot.memory_hits)
                if snapshot.knowledge_hits:
                    lines.append("Conocimiento local:")
                    lines.extend(f"- {item}" for item in snapshot.knowledge_hits)
                self._context_view.setPlainText("\n".join(lines))
            else:
                self._context_view.setPlainText(str(snapshot))
            self._refresh_sources_view()

        def _handle_prompt_finished(self, text: str) -> None:
            if not self._current_stream_text and text:
                self._add_message_bubble("assistant", text)
            self._current_stream_edit = None
            self._current_stream_text = ""
            self._handle_compliance_result_from_text(text)
            self._remember_desktop_history(text)
            self._attachments = []
            self._render_attachment_pills()
            self._set_busy(False)

        def _handle_import_finished(self, result: object) -> None:
            scanned = getattr(result, "scanned_files", 0)
            indexed = getattr(result, "indexed_files", 0)
            failed  = getattr(result, "failed_files", 0)
            pending = getattr(result, "pending_files", 0)
            self._append_system(
                f"Knowledge base actualizado — {indexed} indexados, "
                f"{scanned} escaneados, {failed} fallidos, {pending} pendientes"
            )
            self._set_busy(False)

        def _handle_worker_error(self, message: str) -> None:
            self._current_stream_edit = None
            self._current_stream_text = ""
            self._add_notice(f"Error: {message}", object_name="Err")
            self._set_busy(False)

        def _handle_worker_cancelled(self, message: str) -> None:
            self._current_stream_edit = None
            self._current_stream_text = ""
            self._append_system(message)
            self._set_busy(False)

        def _handle_backend_ready(self, greeting: str) -> None:
            self._append_system(greeting)

        def _handle_shutdown_finished(self) -> None:
            pass

        def _handle_backend_thread_finished(self) -> None:
            self._backend_thread = None
            self._backend_worker = None
            if self._close_requested:
                self.close()

        def _show_confirmation_dialog(self, question: str) -> None:
            answer = QMessageBox.question(
                self,
                "Confirmación — ADV ARCHON",
                question,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            self._confirm_bridge.resolve(answer == QMessageBox.StandardButton.Yes)

        # ── Right panel updates ───────────────────────────────────────────────
        def _refresh_tool_badges(self) -> None:
            while self._tools_layout.count() > 1:
                item = self._tools_layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            for name in self._active_tool_names[-6:]:
                badge = QFrame()
                badge.setObjectName("ToolBadge")
                bl = QHBoxLayout(badge)
                bl.setContentsMargins(6, 3, 6, 3)
                bl.setSpacing(0)
                bl.addWidget(QLabel(name))
                self._tools_layout.insertWidget(self._tools_layout.count() - 1, badge)

        def _refresh_sources_view(self) -> None:
            snap = self._last_snapshot
            self._sources_view.setPlainText(
                format_sources_summary(
                    tool_names=self._active_tool_names,
                    memory_hits=snap.memory_hits if snap else (),
                    knowledge_hits=snap.knowledge_hits if snap else (),
                )
            )

        def _remember_desktop_history(self, response_text: str) -> None:
            if self._pending_prompt:
                entry = build_history_entry(
                    self._pending_prompt,
                    attachments=self._pending_attachments,
                    response_text=response_text,
                )
                self._recent_history_entries = merge_recent_items(
                    self._recent_history_entries, [entry], limit=12
                )
                self._history_list.clear()
                self._history_list.addItems(self._recent_history_entries)
            if self._pending_attachments:
                labels = [p.name or str(p) for p in self._pending_attachments]
                self._recent_attachment_entries = merge_recent_items(
                    self._recent_attachment_entries, labels, limit=12
                )
                self._recent_attachments_list.clear()
                self._recent_attachments_list.addItems(self._recent_attachment_entries)
            self._pending_prompt = ""
            self._pending_attachments = []

        # ── Attachments ───────────────────────────────────────────────────────
        def _pick_attachments(self) -> None:
            files, _ = QFileDialog.getOpenFileNames(
                self, "Selecciona archivos", str(Path.home()), "Todos los archivos (*)"
            )
            if files:
                self._add_attachments([Path(p) for p in files])

        def _add_attachments(self, paths: list[Path]) -> None:
            self._attachments = normalize_attachment_paths([*self._attachments, *paths])
            self._render_attachment_pills()
            # Trigger compliance flow for first PDF found
            for p in paths:
                if p.suffix.lower() == ".pdf" and self._compliance.state == "idle":
                    self._on_pdf_attached(p)
                    break

        def _remove_attachment(self, path: Path) -> None:
            self._attachments = [a for a in self._attachments if a != path]
            self._render_attachment_pills()

        def _render_attachment_pills(self) -> None:
            while self._pills_row.count() > 1:
                item = self._pills_row.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            for path in self._attachments:
                pill = QFrame()
                pill.setObjectName("ToolBadge")
                pl = QHBoxLayout(pill)
                pl.setContentsMargins(8, 3, 8, 3)
                pl.setSpacing(4)
                name_lbl = QLabel(path.name or str(path))
                name_lbl.setObjectName("Sub")
                pl.addWidget(name_lbl)
                rm = QPushButton("×")
                rm.setObjectName("IconBtn")
                rm.setFixedSize(16, 16)
                rm.clicked.connect(lambda _=False, p=path: self._remove_attachment(p))
                pl.addWidget(rm)
                self._pills_row.insertWidget(self._pills_row.count() - 1, pill)
            has = bool(self._attachments)
            self._import_button.setVisible(has)
            if not has:
                self._compliance.reset()
            self._refresh_compliance_ui()
            self._handle_busy_state_changed(self._busy_state)

        def _import_attachments_to_kb(self) -> None:
            paths = list(self._attachments)
            if not paths:
                return
            self._append_system(
                "Añadiendo al knowledge base: "
                + ", ".join(p.name or str(p) for p in paths)
            )
            self._set_busy(True, task="knowledge_import")
            self.import_requested.emit([str(p) for p in paths])

        # ── Prompt submission ─────────────────────────────────────────────────
        def _submit_prompt(self) -> None:
            prompt = self._input.toPlainText().strip()
            if not prompt:
                return
            attachments = list(self._attachments)
            self._input.clear()
            self._pending_prompt = prompt
            self._pending_attachments = attachments
            self._active_tool_names = []
            self._last_snapshot = None
            self._refresh_sources_view()
            self._refresh_tool_badges()
            self._append_user(prompt, attachments)
            self._append_assistant_prefix()
            self._current_stream_text = ""
            # Capture municipality hint from user text before sending
            self._try_extract_municipality_from_input(prompt)
            self._set_busy(True, task="prompt")
            self.prompt_requested.emit(prompt, [str(p) for p in attachments])

        def _send_nav_prompt(self, prompt: str) -> None:
            self._input.setPlainText(prompt)
            self._submit_prompt()

        def _send_daily_prompt(self) -> None:
            self._input.setPlainText(
                "prepara mi daily brief con agenda, tareas, gmail, drive y notas"
            )
            self._submit_prompt()

        def _send_pgou_prompt(self) -> None:
            self._input.setPlainText(
                "muestra el estado de los municipios en el catálogo PGOU y dime "
                "cuáles están indexados y disponibles para análisis"
            )
            self._submit_prompt()

        def _send_geo_prompt(self) -> None:
            self._input.setPlainText(
                "¿cómo resuelvo la normativa urbanística de una parcela por "
                "coordenadas GPS usando geolocalización?"
            )
            self._submit_prompt()

        # ── Mode / profile ────────────────────────────────────────────────────
        def _load_controls_state(self) -> None:
            self._mode_combo.setCurrentText(self._selected_mode)
            self._profile_combo.setCurrentText(self._selected_profile)
            self._handle_busy_state_changed(self._busy_state)

        def _change_mode(self, mode: str) -> None:
            self._selected_mode = mode
            self.mode_requested.emit(mode)
            self._refresh_status()

        def _change_profile(self, profile: str) -> None:
            resolved = self._profile_manager.resolve(profile)
            self._selected_profile = resolved
            self._profile_combo.setCurrentText(resolved)
            self.profile_requested.emit(resolved)
            self._refresh_status()

        def _refresh_status(self) -> None:
            text = self._busy_state.status_text(
                mode=self._selected_mode,
                profile=self._selected_profile,
            )
            self._status_label.setText(text)
            self._mode_status_lbl.setText(
                f"{self._selected_mode} · {self._selected_profile}"
            )

        def _set_busy(self, busy: bool, *, task: str | None = None) -> None:
            next_task = task or self._busy_state.task
            self._handle_busy_state_changed(
                DesktopBusyState(
                    backend_ready=self._busy_state.backend_ready,
                    busy=busy,
                    task=next_task if busy else "idle",
                    closing=self._busy_state.closing,
                    progress=self._busy_state.progress if busy else None,
                    detail=self._busy_state.detail if busy else None,
                    cancellable=busy and next_task == "prompt",
                )
            )

        def _handle_busy_state_changed(self, state: DesktopBusyState) -> None:
            self._busy_state = state
            accepts     = state.accepts_user_actions
            can_send    = state.can_dispatch_requests
            allows_cfg  = state.allows_configuration
            has_attach  = bool(self._attachments)

            self._input.setEnabled(accepts)
            self._send_button.setEnabled(can_send)
            self._add_button.setEnabled(accepts)
            self._import_button.setEnabled(can_send and has_attach)
            self._analyze_button.setEnabled(can_send and self._compliance.can_run)
            self._mode_combo.setEnabled(allows_cfg)
            self._profile_combo.setEnabled(allows_cfg)
            self._daily_action.setEnabled(can_send)
            self._nav_daily_btn.setEnabled(can_send)
            self._nav_pgou_btn.setEnabled(can_send)
            self._nav_geo_btn.setEnabled(can_send)
            self._cancel_button.setVisible(state.cancellable)

            if state.busy:
                self._progress_bar.setVisible(True)
                if state.progress is None:
                    self._progress_bar.setRange(0, 0)
                else:
                    self._progress_bar.setRange(0, 100)
                    self._animate_progress(max(0, min(100, state.progress)))
            else:
                self._progress_bar.setRange(0, 100)
                self._animate_progress(100)
                self._progress_bar.setVisible(False)

            self._refresh_status()

        def _animate_progress(self, value: int) -> None:
            current = self._progress_bar.value()
            anim = QPropertyAnimation(self._progress_bar, b"value", self)
            anim.setDuration(220)
            anim.setStartValue(current)
            anim.setEndValue(value)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            self._progress_animation = anim

        def _cancel_active_task(self) -> None:
            if self._busy_state.cancellable:
                self.cancel_requested.emit()

        # ── Helpers ───────────────────────────────────────────────────────────
        def _apply_branding(self) -> None:
            self.setStyleSheet(desktop_stylesheet())

        def _fit_to_screen(self) -> None:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is None:
                return
            avail = screen.availableGeometry()
            tw, th = recommended_window_size(avail.width(), avail.height())
            w = min(max(self.width(), self.minimumWidth()), tw)
            h = min(max(self.height(), self.minimumHeight()), th)
            self.resize(w, h)
            fg = self.frameGeometry()
            x = max(avail.left() + 12, min(fg.x(), avail.right()  - fg.width()  - 12))
            y = max(avail.top()  + 12, min(fg.y(), avail.bottom() - fg.height() - 12))
            self.move(x, y)

        def _make_logo(self, size: int) -> QLabel:
            lbl = QLabel()
            lbl.setFixedSize(size, size)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if self._logo_pixmap is not None and not self._logo_pixmap.isNull():
                lbl.setPixmap(
                    self._logo_pixmap.scaled(
                        size, size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            return lbl

        def _make_nav_btn(self, text: str, *, active: bool = False) -> QPushButton:
            btn = QPushButton(text)
            btn.setObjectName("NavBtnActive" if active else "NavBtn")
            return btn

        def _make_divider(self) -> QFrame:
            div = QFrame()
            div.setObjectName("Divider")
            return div

        # ── Warmup agent (Phase 7B) ───────────────────────────────────────────
        def _start_warmup_agent(self) -> None:
            if self._selected_mode != "local":
                return
            try:
                ref = start_warmup_agent(
                    base_url=config.llm.ollama_base_url,
                    model=config.llm.ollama_model,
                    timeout=float(config.llm.ollama_timeout_seconds),
                    on_progress=self._handle_warmup_progress,
                    on_model_found=self._handle_warmup_model_found,
                    on_ready=self._handle_warmup_ready,
                    on_failed=self._handle_warmup_failed,
                )
                self._warmup_agent_ref = ref
            except Exception:
                pass  # warmup is optional; never block startup

        def _handle_warmup_progress(self, message: str) -> None:
            self._append_system(f"[warmup] {message}")

        def _handle_warmup_model_found(self, model_name: str) -> None:
            self._append_system(f"Modelo local: {model_name}")

        def _handle_warmup_ready(self, elapsed: float) -> None:
            self._append_system(
                f"Modelo listo en {elapsed:.1f}s — respuestas locales a plena velocidad."
            )
            self._warmup_agent_ref = None

        def _handle_warmup_failed(self, error: str) -> None:
            self._add_notice(f"Warmup: {error}", object_name="Warn")
            self._warmup_agent_ref = None

        # ── Compliance flow (Phase 7) ─────────────────────────────────────────
        def _on_pdf_attached(self, path: Path) -> None:
            """Called whenever a PDF is added to the attachment list."""
            self._compliance.attach_pdf(path)
            hint = extract_municipality_hint(path)
            if hint:
                self._compliance.set_municipality(hint)
            self._refresh_compliance_ui()
            # Ask the user to confirm the municipality via the chat
            prompt = build_municipality_ask_prompt(path, hint=hint)
            self._append_system(prompt)

        def _trigger_compliance_analysis(self) -> None:
            """Send the compliance prompt to the agent."""
            if self._compliance.pdf_path is None:
                return
            if (
                not self._compliance.municipality
                and (
                    self._compliance.latitude is None
                    or self._compliance.longitude is None
                )
            ):
                self._append_system(
                    "Indica el municipio o las coordenadas GPS en el chat "
                    "antes de analizar el plano."
                )
                return
            self._compliance.mark_running()
            self._refresh_compliance_ui()
            if (
                self._compliance.latitude is not None
                and self._compliance.longitude is not None
            ):
                prompt = build_coordinate_compliance_prompt(
                    self._compliance.pdf_path,
                    self._compliance.latitude,
                    self._compliance.longitude,
                )
            else:
                prompt = build_compliance_prompt(
                    self._compliance.pdf_path,
                    self._compliance.municipality,
                )
            self._input.setPlainText(prompt)
            self._submit_prompt()

        def _refresh_compliance_ui(self) -> None:
            state = self._compliance.state
            pdf_attached = self._compliance.pdf_path is not None
            can_run  = self._compliance.can_run

            # "Analizar plano" button: visible when PDF is attached
            self._analyze_button.setVisible(pdf_attached and self._busy_state.backend_ready)
            self._analyze_button.setEnabled(can_run and not self._busy_state.busy)

            # Compliance result card
            if state == "done" and self._compliance.has_result:
                self._compliance_card.setVisible(True)
                self._compliance_summary_lbl.setText(
                    self._compliance.summary[:180] + "…"
                    if len(self._compliance.summary) > 180
                    else self._compliance.summary
                )
                ok  = self._compliance.ok_count
                wrn = self._compliance.warning_count
                vio = self._compliance.violation_count
                self._compliance_stats_lbl.setText(
                    f"OK {ok}  ·  Revisar {wrn}  ·  Incumple {vio}"
                )
                self._export_button.setEnabled(True)
            else:
                self._compliance_card.setVisible(False)

        def _handle_compliance_result_from_text(self, text: str) -> None:
            """
            Parse the LLM response to detect if a compliance check completed.
            Looks for 'plan_compliance_check' result signals in the final text.
            """
            if self._compliance.state != "running":
                return
            lowered = text.lower()
            if any(kw in lowered for kw in ("cumple", "incumple", "revisar", "análisis")):
                # Extract approximate summary from response text
                summary_snippet = text[:300].replace("\n", " ").strip()
                self._compliance.mark_done(
                    result={
                        "summary": summary_snippet,
                        "annotations": [],   # populated by tool result in real flow
                    }
                )
                self._refresh_compliance_ui()

        def _export_compliance_report(self) -> None:
            if self._compliance.pdf_path is None or not self._compliance.municipality:
                return
            prompt = (
                f"Exporta el informe de cumplimiento normativo del plano "
                f"'{self._compliance.pdf_path.name}' del municipio "
                f"{self._compliance.municipality} como PDF profesional "
                f"usando plan_compliance_export."
            )
            self._input.setPlainText(prompt)
            self._submit_prompt()

        # ── Expedientes panel ─────────────────────────────────────────────────
        def _open_expedientes(self) -> None:
            import dataclasses
            import json
            import os

            from PySide6.QtCore import QObject, QThread, Signal as _Signal
            from PySide6.QtWidgets import (
                QDialog,
                QFrame,
                QHBoxLayout as _QHBoxLayout,
            )

            from adv_archon.core.expediente import Expediente, ExpedienteStore
            from adv_archon.desktop.expediente_panel import (
                ExpedienteDetailPanel,
                ExpedienteListPanel,
                NewExpedienteDialog,
            )
            from adv_archon.integrations import catastro as _catastro
            from adv_archon.integrations import nominatim as _nominatim

            data_dir = Path(os.getenv("ADV_ARCHON_HOME", str(Path.home() / ".adv-archon")))
            data_dir.mkdir(parents=True, exist_ok=True)
            store = ExpedienteStore(data_dir / "expedientes.db")

            # -- Background geo-resolver ----------------------------------------
            class _GeoWorker(QObject):
                resolved = _Signal(object)
                failed   = _Signal(str)

                def __init__(self, exp: Expediente) -> None:
                    super().__init__()
                    self._exp = exp

                def run(self) -> None:
                    try:
                        result = _nominatim.forward_geocode(self._exp.address)
                        if not result:
                            self.failed.emit("Nominatim no encontró la dirección.")
                            return
                        lat = float(result.get("lat", 0) or 0)
                        lon = float(result.get("lon", 0) or 0)
                        municipality, province, _ = _nominatim.extract_municipality(result)
                        cadastral_ref = ""
                        try:
                            cd = _catastro.get_cadastral_data(lat, lon)
                            cadastral_ref = cd.get("cadastral_ref", "") or ""
                        except Exception:
                            pass
                        site_ctx = json.dumps(
                            {"latitude": lat, "longitude": lon,
                             "municipality": municipality, "province": province,
                             "cadastral_ref": cadastral_ref, "resolution": "nominatim"},
                            ensure_ascii=False,
                        )
                        updated = dataclasses.replace(
                            self._exp,
                            latitude=lat, longitude=lon,
                            municipality=municipality, province=province,
                            cadastral_ref=cadastral_ref,
                            site_context=site_ctx,
                        )
                        self.resolved.emit(updated)
                    except Exception as exc:
                        self.failed.emit(str(exc))

            _active_geo_threads: list[tuple[Any, Any]] = []

            def _launch_geo(exp: Expediente) -> None:
                t = QThread(dlg)
                w = _GeoWorker(exp)
                w.moveToThread(t)
                t.started.connect(w.run)

                def _on_resolved(updated: Expediente) -> None:
                    store.update(updated)
                    list_panel.populate(store.list_all())
                    detail_panel.load_expediente(updated)
                    t.quit()

                def _on_failed(msg: str) -> None:
                    t.quit()

                w.resolved.connect(_on_resolved)
                w.failed.connect(_on_failed)
                t.finished.connect(t.deleteLater)
                _active_geo_threads.append((t, w))
                t.start()

            # -- Dialog ----------------------------------------------------------
            dlg = QDialog(self)
            dlg.setWindowTitle("Expedientes — ADV ARCHON")
            dlg.resize(1100, 680)
            dlg_layout = _QHBoxLayout(dlg)
            dlg_layout.setContentsMargins(0, 0, 0, 0)
            dlg_layout.setSpacing(0)

            def _on_analyze(eid: str) -> None:
                exp = store.get(eid)
                if not exp:
                    return
                parts = [f"Analiza el expediente «{exp.title}»."]
                parts.append(f"Dirección: {exp.address}")
                if exp.municipality:
                    parts.append(f"Municipio: {exp.municipality}, {exp.province}")
                if exp.cadastral_ref:
                    parts.append(f"Ref. catastral: {exp.cadastral_ref}")
                if exp.latitude and exp.longitude:
                    parts.append(f"Coordenadas: {exp.latitude:.6f}, {exp.longitude:.6f}")
                parts.append(
                    "\nEjecuta plan_compliance_check con el plano adjunto "
                    "y el municipio indicado."
                )
                if exp.plan_path:
                    plan = Path(exp.plan_path)
                    if plan.exists():
                        self._add_attachments([plan])
                self._input.setPlainText("\n".join(parts))
                dlg.accept()   # close dialog, switch user to chat

            def _on_export(eid: str) -> None:
                exp = store.get(eid)
                if not exp:
                    return
                prompt = (
                    f"Exporta el informe de cumplimiento del expediente «{exp.title}» "
                    f"(municipio: {exp.municipality or '?'}) como PDF profesional "
                    "usando plan_compliance_export."
                )
                self._input.setPlainText(prompt)
                dlg.accept()

            detail_panel = ExpedienteDetailPanel(
                on_attach_plan=lambda eid: _attach_plan(eid),
                on_analyze=_on_analyze,
                on_export=_on_export,
            )

            def _attach_plan(eid: str) -> None:
                from PySide6.QtWidgets import QFileDialog as _QFD
                paths, _ = _QFD.getOpenFileNames(
                    dlg, "Adjuntar plano",
                    str(Path.home()),
                    "Planos (*.pdf *.dwg *.dxf *.png *.jpg);;Todos (*)",
                )
                if not paths:
                    return
                exp = store.get(eid)
                if not exp:
                    return
                updated = dataclasses.replace(exp, plan_path=paths[0])
                store.update(updated)
                detail_panel.load_expediente(updated)

            def _select(eid: str) -> None:
                exp = store.get(eid)
                if exp:
                    detail_panel.load_expediente(exp)

            def _new() -> None:
                d = NewExpedienteDialog(dlg)
                from PySide6.QtWidgets import QDialog as _QD
                if d.exec() != _QD.DialogCode.Accepted:
                    return
                exp = store.create(
                    title=d.title_text(),
                    address=d.address_text(),
                    notes=d.notes_text(),
                )
                list_panel.populate(store.list_all())
                detail_panel.load_expediente(exp)
                _launch_geo(exp)

            def _delete(eid: str) -> None:
                from PySide6.QtWidgets import QMessageBox as _QMB
                exp = store.get(eid)
                if not exp:
                    return
                reply = _QMB.question(
                    dlg, "Eliminar",
                    f"¿Eliminar «{exp.title}»?",
                    _QMB.StandardButton.Yes | _QMB.StandardButton.No,
                )
                if reply == _QMB.StandardButton.Yes:
                    store.delete(eid)
                    list_panel.populate(store.list_all())
                    detail_panel.clear()

            list_panel = ExpedienteListPanel(
                on_select=_select,
                on_new=_new,
                on_delete=_delete,
            )

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)

            dlg_layout.addWidget(list_panel)
            dlg_layout.addWidget(sep)
            dlg_layout.addWidget(detail_panel, 1)

            list_panel.populate(store.list_all())
            dlg.exec()

        # ── Municipality extraction from chat ────────────────────────────────
        def _try_extract_municipality_from_input(self, text: str) -> None:
            """
            When the user types a municipality name in response to the PDF prompt,
            capture it and update the compliance session.
            """
            if self._compliance.state != "pdf_attached":
                return
            coordinate_hint = extract_coordinate_hint(text)
            if coordinate_hint is not None:
                latitude, longitude = coordinate_hint
                self._compliance.set_coordinates(latitude, longitude)
                self._refresh_compliance_ui()
                self._append_system(
                    f"Coordenadas capturadas para el análisis: {latitude}, {longitude}."
                )
                return
            from adv_archon.desktop.compliance_session import _MUNI_PATTERN
            match = _MUNI_PATTERN.search(text)
            if match:
                for group in ("muni1", "muni2", "muni3"):
                    val = match.group(group)
                    if val:
                        self._compliance.set_municipality(val.strip())
                        self._refresh_compliance_ui()
                        return
            # Heuristic: if the message is short (< 5 words), treat it as a municipality name
            words = text.strip().split()
            if 1 <= len(words) <= 4 and text[0].isupper():
                self._compliance.set_municipality(text.strip())
                self._refresh_compliance_ui()

    # ── Launch ────────────────────────────────────────────────────────────────
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    resolved_logo = logo_path()
    if resolved_logo.exists():
        app.setWindowIcon(QIcon(str(resolved_logo)))
    window = DesktopWindow()
    window.show()
    return app.exec()
