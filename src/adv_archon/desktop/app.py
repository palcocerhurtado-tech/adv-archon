# mypy: ignore-errors
from __future__ import annotations

import json
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from adv_archon import __beta_label__
from adv_archon.core.attachments import normalize_attachment_paths
from adv_archon.core.profiles import ProfileManager
from adv_archon.desktop.branding import (
    ACCENT,
    ERR,
    INFO,
    OK,
    TEXT_SUB,
    WARN,
    desktop_stylesheet,
    logo_path,
)
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

if TYPE_CHECKING:
    from adv_archon.core.config import AppConfig
    from adv_archon.core.llm import LLMRouter


def launch_desktop_app(
    *,
    config: AppConfig,
    llm: LLMRouter | None,
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
            QUrl,
            Signal,
        )
        from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QFileDialog,
            QFrame,
            QGridLayout,
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
            QStatusBar,
            QTextBrowser,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "La app de escritorio necesita PySide6. Instálalo con "
            "`uv pip install PySide6` o añade el extra desktop antes de lanzarla."
        ) from exc

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
        live_requested = Signal(int, str)
        mode_requested   = Signal(str)
        profile_requested = Signal(str)
        ollama_model_requested = Signal(str)
        cancel_requested  = Signal()
        shutdown_requested = Signal()
        expediente_selected = Signal(object)

        def __init__(self) -> None:
            super().__init__()
            self._logo_path   = logo_path()
            self._logo_pixmap = (
                QPixmap(str(self._logo_path)) if self._logo_path.exists() else None
            )
            self.setWindowTitle(f"ADV ARCHON — {__beta_label__}")
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
            self._active_exp_store: Any = None   # set when expediente analysis starts
            self._active_exp_id: str = ""
            self._active_exp_context: str = ""   # injected once into next user message
            self._warmup_agent_ref: tuple[Any, Any] | None = None
            self._onboarding_dialog: Any = None
            self._expedientes_dialog: Any = None
            self._studio_demo_dialog: Any = None
            self._client_license_dialog: Any = None
            self._studio_pack_dialog: Any = None
            self._qa_dialog: Any = None
            self._qa_runner_ref: tuple[Any, Any] | None = None
            self._system_diag_ref: tuple[Any, Any] | None = None
            self._training_lab_ref: tuple[Any, Any] | None = None
            self._last_performance_report: Any = None
            self._professional_review_filter = "all"
            self._onboarding_config_path = config.paths.root / "config.json"
            initial_mode = config.llm.mode
            self._ollama_state = "Pendiente" if initial_mode == "local" else "Cloud"
            self._ollama_model = config.llm.ollama_model
            self._last_exp_label = "Sin expediente"

            self._confirm_bridge   = ConfirmBridge()
            self._confirm_bridge.requested.connect(self._show_confirmation_dialog)
            self._profile_manager  = ProfileManager(
                config.paths.profile_state_file,
                default_profile=config.profiles.default_profile,
                definitions=config.profiles.definitions,
            )
            self._selected_mode    = initial_mode
            self._selected_profile = self._profile_manager.active_profile
            self._attachments: list[Path] = []
            self._recent_history_entries: list[str] = []
            self._recent_attachment_entries: list[str] = []
            self._active_tool_names: list[str] = []
            self._last_snapshot: Any | None = None
            self._pending_prompt    = ""
            self._pending_attachments: list[Path] = []
            self._current_stream_edit: _AutoTextEdit | None = None
            self._current_stream_text = ""
            self._stream_buffer = ""
            self._voice_transcript_edit: _AutoTextEdit | None = None
            self._home_visible = False
            self._active_nav_context = "home"
            self._progress_animation  = None
            self._model_loader_ref: tuple[Any, Any] | None = None
            self._active_file_picker: Any = None
            self._busy_state = DesktopBusyState(
                backend_ready=False, busy=True, task="initializing"
            )
            self._close_requested = False
            self._stream_flush_timer = QTimer(self)
            self._stream_flush_timer.setInterval(45)
            self._stream_flush_timer.timeout.connect(self._flush_assistant_stream)

            # Worker
            self._backend_thread = QThread(self)
            self._backend_thread.setObjectName("adv-archon-backend")
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
            self.live_requested.connect(self._backend_worker.run_live_voice)
            self.mode_requested.connect(self._backend_worker.set_mode)
            self.profile_requested.connect(self._backend_worker.set_profile)
            self.ollama_model_requested.connect(self._backend_worker.set_ollama_model)
            self.cancel_requested.connect(
                self._backend_worker.cancel_prompt,
                Qt.ConnectionType.DirectConnection,  # noqa: E501 — fires in UI thread even when worker is blocked
            )
            self.shutdown_requested.connect(self._backend_worker.shutdown)
            self.expediente_selected.connect(self._backend_worker.on_expediente_selected)
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
            self._backend_worker.voice_intent.connect(self._handle_voice_intent)
            self._backend_worker.voice_transcription.connect(self._handle_voice_transcription)
            self._backend_worker.shutdown_finished.connect(self._handle_shutdown_finished)
            self._backend_thread.finished.connect(self._handle_backend_thread_finished)
            self._backend_thread.finished.connect(self._backend_worker.deleteLater)
            self._backend_thread.finished.connect(self._backend_thread.deleteLater)

            self._build_ui()
            self._apply_branding()
            self._build_professional_status_bar()
            self._load_controls_state()
            self._fit_to_screen()
            self._show_dashboard_home(defer_load=True)
            # Do not start the Ollama warmup thread in the window constructor:
            # on macOS/Finder it can abort startup with
            # "QThread: Destroyed while thread is still running" before the
            # first window is visible. Verification remains available from
            # onboarding/settings and when switching back to local mode.
            QTimer.singleShot(600, self._maybe_show_onboarding)

        # ── Lifecycle ─────────────────────────────────────────────────────────
        def _start_backend(self) -> None:
            if self._backend_thread is not None and not self._backend_thread.isRunning():
                self._status_label.setText("Preparando motor local…")
                self.statusBar().showMessage("Preparando motor local…", 3000)
                self._backend_thread.start()

        def closeEvent(self, ev) -> None:
            if self._backend_thread is None or not self._backend_thread.isRunning():
                ev.accept()
                if self._close_requested:
                    QTimer.singleShot(0, QApplication.quit)
                return
            if self._close_requested:
                # Second close attempt while thread is still blocked — force quit.
                QApplication.quit()
                ev.accept()
                return
            self._close_requested = True
            self.cancel_requested.emit()      # interrupt any running prompt
            self.shutdown_requested.emit()
            ev.ignore()
            # Safety net: if the worker thread doesn't stop in 4 s, force quit.
            QTimer.singleShot(4000, QApplication.quit)

        def _stop_background_threads(self) -> None:
            """Stop Qt workers before QApplication tears down Python wrappers."""
            for ref_name in (
                "_system_diag_ref",
                "_model_loader_ref",
                "_qa_runner_ref",
                "_warmup_agent_ref",
            ):
                ref = getattr(self, ref_name, None)
                if not ref:
                    continue
                thread = ref[0] if ref_name != "_warmup_agent_ref" else ref[1]
                with suppress(Exception):
                    if thread is not None and thread.isRunning():
                        thread.quit()
                        thread.wait(1500)
                setattr(self, ref_name, None)

            thread = self._backend_thread
            if thread is None or not thread.isRunning():
                return
            with suppress(Exception):
                self.cancel_requested.emit()
                self.shutdown_requested.emit()
            if thread.isRunning():
                with suppress(Exception):
                    thread.quit()
                    thread.wait(3000)
            if thread.isRunning():
                with suppress(Exception):
                    thread.terminate()
                    thread.wait(1000)

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

            pgou_action = QAction("Importar normativa PGOU…", self)
            pgou_action.triggered.connect(self._open_pgou_import)
            self.menuBar().addAction(pgou_action)

        def _build_sidebar(self) -> QFrame:
            sidebar = QFrame()
            sidebar.setObjectName("Sidebar")
            sidebar.setFixedWidth(196)
            sl = QVBoxLayout(sidebar)
            sl.setContentsMargins(10, 18, 10, 18)
            sl.setSpacing(2)

            # Brand
            brand = QHBoxLayout()
            brand.setSpacing(10)
            brand.addWidget(self._make_logo(32))
            name_lbl = QLabel("ADV ARCHON")
            name_lbl.setObjectName("AppName")
            brand.addWidget(name_lbl, 1)
            sl.addLayout(brand)

            tagline = QLabel(f"ARQUITECTURA · IA · {__beta_label__.upper()}")
            tagline.setObjectName("Eyebrow")
            sl.addWidget(tagline)
            sl.addSpacing(14)
            sl.addWidget(self._make_divider())
            sl.addSpacing(8)

            # Navigation
            self._nav_home_btn = self._make_nav_btn("  Inicio", active=True)
            self._nav_home_btn.clicked.connect(self._show_dashboard_home)
            sl.addWidget(self._nav_home_btn)

            self._nav_exp_btn = self._make_nav_btn("  Expedientes")
            self._nav_exp_btn.clicked.connect(lambda: self._open_expedientes())
            sl.addWidget(self._nav_exp_btn)

            self._nav_review_btn = self._make_nav_btn("  Revisión Pro")
            self._nav_review_btn.clicked.connect(self._show_professional_review)
            sl.addWidget(self._nav_review_btn)

            self._nav_demo_btn = self._make_nav_btn("  Studio Demo")
            self._nav_demo_btn.setObjectName("NavBtnGold")
            self._nav_demo_btn.clicked.connect(self._open_studio_demo)
            sl.addWidget(self._nav_demo_btn)

            self._nav_chat_btn = self._make_nav_btn("  Chat contextual")
            self._nav_chat_btn.clicked.connect(self._show_chat_home)
            sl.addWidget(self._nav_chat_btn)

            self._nav_research_btn = self._make_nav_btn("  Research")
            self._nav_research_btn.clicked.connect(self._open_research_workbench)
            sl.addWidget(self._nav_research_btn)

            self._nav_pgou_btn = self._make_nav_btn("  PGOU")
            self._nav_pgou_btn.clicked.connect(self._show_pgou_status)
            sl.addWidget(self._nav_pgou_btn)

            self._nav_geo_btn = self._make_nav_btn("  Geo")
            self._nav_geo_btn.clicked.connect(self._send_geo_prompt)
            sl.addWidget(self._nav_geo_btn)

            self._nav_daily_btn = self._make_nav_btn("  Briefing")
            self._nav_daily_btn.clicked.connect(self._send_daily_prompt)
            sl.addWidget(self._nav_daily_btn)

            self._nav_client_btn = self._make_nav_btn("  Cliente")
            self._nav_client_btn.clicked.connect(self._open_client_license)
            sl.addWidget(self._nav_client_btn)

            self._nav_pack_btn = self._make_nav_btn("  Pack")
            self._nav_pack_btn.clicked.connect(self._open_studio_pack)
            sl.addWidget(self._nav_pack_btn)

            self._nav_training_btn = self._make_nav_btn("  Training Lab")
            self._nav_training_btn.clicked.connect(self._open_training_lab)
            sl.addWidget(self._nav_training_btn)

            self._nav_beta_btn = self._make_nav_btn("  Guía beta")
            self._nav_beta_btn.clicked.connect(self._show_beta_guide)
            sl.addWidget(self._nav_beta_btn)

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

            sl.addSpacing(8)
            self._settings_button = self._make_nav_btn("  Ajustes")
            self._settings_button.clicked.connect(self._open_settings)
            sl.addWidget(self._settings_button)

            self._qa_button = self._make_nav_btn("  QA permisos")
            self._qa_button.clicked.connect(self._open_qa_panel)
            sl.addWidget(self._qa_button)

            self._system_button = self._make_nav_btn("  Estado sistema")
            self._system_button.clicked.connect(self._open_system_status)
            sl.addWidget(self._system_button)

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

        def _build_professional_status_bar(self) -> None:
            bar = QStatusBar(self)
            bar.setObjectName("BottomBar")
            self.setStatusBar(bar)
            self._beta_badge_lbl = QLabel(__beta_label__)
            self._beta_badge_lbl.setObjectName("Accent")
            self._ollama_badge_lbl = QLabel("")
            self._ollama_badge_lbl.setObjectName("Sub")
            self._model_badge_lbl = QLabel("")
            self._model_badge_lbl.setObjectName("Sub")
            self._last_exp_badge_lbl = QLabel("")
            self._last_exp_badge_lbl.setObjectName("Faint")
            bar.addPermanentWidget(self._beta_badge_lbl)
            bar.addPermanentWidget(self._ollama_badge_lbl)
            bar.addPermanentWidget(self._model_badge_lbl)
            bar.addPermanentWidget(self._last_exp_badge_lbl, 1)
            self._refresh_status_bar()

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

            # Context bar — shows active expediente above the composer
            self._exp_context_bar = QFrame()
            self._exp_context_bar.setFixedHeight(32)
            self._exp_context_bar.setStyleSheet(
                "background:rgba(201,162,39,0.08);"
                "border-bottom:1px solid rgba(201,162,39,0.25);"
                "border-top:none;border-left:none;border-right:none;"
            )
            _ctx_row = QHBoxLayout(self._exp_context_bar)
            _ctx_row.setContentsMargins(12, 0, 8, 0)
            _ctx_row.setSpacing(6)
            self._exp_context_label = QLabel()
            self._exp_context_label.setStyleSheet(
                f"color:{ACCENT};font-size:12px;font-weight:600;background:transparent;"
            )
            _ctx_row.addWidget(self._exp_context_label, 1)
            _ctx_dismiss = QPushButton("×")
            _ctx_dismiss.setObjectName("Ghost")
            _ctx_dismiss.setFixedSize(22, 22)
            _ctx_dismiss.setStyleSheet(
                "background:transparent;border:none;color:#77746B;"
                "font-size:16px;padding:0;"
            )
            _ctx_dismiss.clicked.connect(self._dismiss_exp_context)
            _ctx_row.addWidget(_ctx_dismiss)
            self._exp_context_bar.setVisible(False)
            cl.addWidget(self._exp_context_bar)

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

            self._attachment_hint_label = QLabel("")
            self._attachment_hint_label.setObjectName("Faint")
            self._attachment_hint_label.setWordWrap(True)
            self._attachment_hint_label.setVisible(False)
            fl.addWidget(self._attachment_hint_label)

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

            self._voice_button = QPushButton("Hablar con ARCHON")
            self._voice_button.setObjectName("Primary")
            self._voice_button.setToolTip("Escuchar por micrófono y responder con voz local")
            self._voice_button.clicked.connect(lambda _=False: self._submit_live_prompt("/live"))
            btn_col.addWidget(self._voice_button)

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

        # ── Expediente context bar ────────────────────────────────────────────
        def _set_active_expediente(self, exp: Any) -> None:
            self._active_exp_context = self._build_expediente_voice_context(exp)
            label = f"  \U0001f4c1 {exp.title[:45]}  ·  {exp.municipality or ''}"
            self._exp_context_label.setText(label)
            self._exp_context_bar.setVisible(True)

        def _build_expediente_voice_context(self, exp: Any) -> str:
            lines = [
                "[Contexto del expediente activo — incluir en la respuesta si es relevante]",
                f"Expediente: {exp.title}",
                f"Tipo de actuación: {getattr(exp, 'case_type', '') or 'No indicado'}",
                f"Dirección: {exp.address or 'No indicada'}",
                f"Municipio: {exp.municipality or 'No indicado'} / {exp.province or ''}",
                f"Ref. catastral: {exp.cadastral_ref or 'No disponible'}",
                f"Estado: {exp.status or 'borrador'}",
                f"Plano: {getattr(exp, 'plan_path', '') or 'Sin plano adjunto'}",
                f"Informe: {getattr(exp, 'report_path', '') or 'Sin informe generado'}",
            ]
            try:
                import json as _json

                if exp.analysis_result:
                    analysis = _json.loads(exp.analysis_result)
                    if isinstance(analysis, dict):
                        if analysis.get("verdict_label"):
                            lines.append(f"Veredicto: {analysis['verdict_label']}")
                        if analysis.get("summary"):
                            lines.append(f"Resumen: {str(analysis['summary'])[:500]}")
                if exp.site_context:
                    ctx = _json.loads(exp.site_context)
                    checks = ctx.get("legal_checks") if isinstance(ctx, dict) else None
                    if isinstance(checks, list):
                        risk_lines = []
                        for check in checks[:8]:
                            if not isinstance(check, dict):
                                continue
                            name = check.get("name") or check.get("title") or check.get("id")
                            status = check.get("status")
                            detail = check.get("detail") or check.get("recommendation") or ""
                            risk_lines.append(f"{name}: {status} — {str(detail)[:120]}")
                        if risk_lines:
                            lines.append("Checks/riesgos: " + " | ".join(risk_lines))
            except Exception:
                pass
            lines.append("[Fin contexto expediente]\n")
            return "\n".join(lines) + "\n"

        def _dismiss_exp_context(self) -> None:
            self._active_exp_context = ""
            self._exp_context_bar.setVisible(False)

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
        ) -> _AutoTextEdit:
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
            return body

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
            self._stream_buffer = ""
            self._stream_flush_timer.stop()
            fl.addWidget(self._current_stream_edit)

            self._insert_bubble(frame)

        def _insert_bubble(self, frame: QFrame) -> None:
            self._home_visible = False
            idx = self._messages_layout.count() - 1  # before trailing stretch
            self._messages_layout.insertWidget(idx, frame)
            QTimer.singleShot(0, self._scroll_to_bottom)

        def _scroll_to_bottom(self) -> None:
            sb = self._messages_scroll.verticalScrollBar()
            sb.setValue(sb.maximum())

        def _clear_message_area(self) -> None:
            self._current_stream_edit = None
            self._current_stream_text = ""
            self._stream_buffer = ""
            while self._messages_layout.count():
                item = self._messages_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self._messages_layout.addStretch(1)

        def _add_notice(self, text: str, *, object_name: str = "Faint") -> None:
            self._home_visible = False
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
            self._stream_buffer += chunk
            if not self._stream_flush_timer.isActive():
                self._stream_flush_timer.start()

        def _flush_assistant_stream(self) -> None:
            if not self._stream_buffer:
                self._stream_flush_timer.stop()
                return
            self._current_stream_text += self._stream_buffer
            self._stream_buffer = ""
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
            if all(
                hasattr(snapshot, attr)
                for attr in (
                    "intent",
                    "profile",
                    "execution_mode",
                    "checkpoint",
                )
            ):
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
            self._flush_assistant_stream()
            if not self._current_stream_text and text:
                self._add_message_bubble("assistant", text)
            self._current_stream_edit = None
            self._current_stream_text = ""
            self._stream_buffer = ""
            self._stream_flush_timer.stop()
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
            self._stream_buffer = ""
            self._stream_flush_timer.stop()
            self._voice_transcript_edit = None
            self._add_notice(f"Error: {message}", object_name="Err")
            self._set_busy(False)

        def _handle_worker_cancelled(self, message: str) -> None:
            self._current_stream_edit = None
            self._current_stream_text = ""
            self._stream_buffer = ""
            self._stream_flush_timer.stop()
            self._voice_transcript_edit = None
            self._append_system(message)
            self._set_busy(False)

        def _handle_voice_transcription(self, text: str, is_final: bool) -> None:
            display = text if is_final else f"{text}…"
            if self._voice_transcript_edit is None:
                self._voice_transcript_edit = self._add_message_bubble("user", display)
            else:
                self._voice_transcript_edit.setPlainText(display)
            if is_final:
                self._voice_transcript_edit.setStyleSheet("")
                self._voice_transcript_edit = None
            elif self._voice_transcript_edit is not None:
                self._voice_transcript_edit.setStyleSheet(
                    "color:#77746B;font-style:italic;"
                )
            QTimer.singleShot(0, self._scroll_to_bottom)

        def _handle_voice_intent(self, action: str, detail_prompt: str) -> None:
            if action == "new_expediente":
                self._append_system("Abriendo el flujo de expedientes para crear uno nuevo.")
                QTimer.singleShot(50, self._show_expedientes_dialog)
                return
            if action == "export_report":
                if self._active_exp_store and self._active_exp_id:
                    exp = self._active_exp_store.get(self._active_exp_id)
                    raw_report = getattr(exp, "report_path", "") if exp else ""
                    report_path = Path(raw_report) if raw_report else None
                    if report_path is not None and report_path.exists():
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(report_path)))
                        self._append_system("Informe del expediente activo abierto.")
                        return
                self._append_system(
                    "No encuentro un informe generado en el expediente activo. "
                    "Abre Expedientes y pulsa Exportar informe PDF."
                )
                return
            if detail_prompt:
                if self._active_exp_context:
                    self._input.setPlainText(detail_prompt)
                    self._append_system(
                        "He preparado la consulta contextual en el cuadro de texto. "
                        "Pulsa Enviar cuando termine el modo voz."
                    )
                else:
                    self._append_system(
                        "Para responder con precisión necesito un expediente activo. "
                        "Abre Expedientes y selecciona uno."
                    )

        def _handle_backend_ready(self, greeting: str) -> None:
            if self._home_visible:
                self.statusBar().showMessage(greeting, 5000)
                return
            self._append_system(greeting)

        def _handle_shutdown_finished(self) -> None:
            pass

        def _handle_backend_thread_finished(self) -> None:
            self._backend_thread = None
            self._backend_worker = None
            if self._close_requested:
                self.close()
                QTimer.singleShot(0, QApplication.quit)

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
                self._refresh_attachments_panel()
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
            self._render_attachment_hint()
            self._refresh_attachments_panel()
            if not has:
                self._compliance.reset()
            self._refresh_compliance_ui()
            self._handle_busy_state_changed(self._busy_state)

        def _refresh_attachments_panel(self) -> None:
            if not hasattr(self, "_recent_attachments_list"):
                return
            self._recent_attachments_list.clear()
            if self._attachments:
                self._recent_attachments_list.addItem("Adjuntos del turno")
                for path in self._attachments[:8]:
                    self._recent_attachments_list.addItem(path.name or str(path))
                if self._recent_attachment_entries:
                    self._recent_attachments_list.addItem("— recientes —")
            self._recent_attachments_list.addItems(self._recent_attachment_entries)

        def _render_attachment_hint(self) -> None:
            if not self._attachments:
                self._attachment_hint_label.setVisible(False)
                self._attachment_hint_label.setText("")
                return
            from adv_archon.core.vision_preflight import (
                build_attachment_vision_hints,
                summarize_vision_readiness,
            )

            hints = build_attachment_vision_hints(self._attachments)
            needs_vision = any(hint.needs_vision for hint in hints)
            readiness = summarize_vision_readiness(
                [self._ollama_model],
                configured_model=str(config.llm.vision_local_model),
            )
            kinds = ", ".join(dict.fromkeys(hint.kind for hint in hints))
            if needs_vision and not readiness.can_analyze_images:
                self._attachment_hint_label.setText(
                    f"Adjuntos: {kinds}. {readiness.label}: se usará texto/OCR "
                    "o se pedirá conversión si el archivo requiere inspección visual."
                )
            else:
                self._attachment_hint_label.setText(
                    f"Adjuntos listos: {kinds}. ARCHON puede usarlos para informe, "
                    "Excel, análisis o entrega."
                )
            self._attachment_hint_label.setVisible(True)

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
            raw_prompt = self._input.toPlainText()
            prompt = raw_prompt.strip()
            if not prompt:
                return
            if prompt.casefold().startswith("/live"):
                self._submit_live_prompt(prompt)
                return
            attachments = list(self._attachments)
            if self._home_visible:
                self._clear_message_area()
                self._home_visible = False
                self._set_nav_context("chat")
            self._input.clear()
            self._pending_prompt = prompt
            self._pending_attachments = attachments
            self._active_tool_names = []
            self._last_snapshot = None
            self._refresh_sources_view()
            self._refresh_tool_badges()
            self._append_user(raw_prompt, attachments)
            self._append_assistant_prefix()
            self._current_stream_text = ""
            self._stream_buffer = ""
            # Capture municipality hint from user text before sending
            self._try_extract_municipality_from_input(prompt)
            self._set_busy(True, task="prompt")
            # Inject expediente context once into the next outgoing message
            if self._active_exp_context:
                full_prompt = self._active_exp_context + prompt
                self._active_exp_context = ""  # consume once
                self._exp_context_bar.setVisible(False)
            else:
                full_prompt = prompt
            if attachments:
                from adv_archon.core.vision_preflight import (
                    build_attachment_vision_hints,
                    build_multimodal_prompt,
                    summarize_vision_readiness,
                )

                readiness = summarize_vision_readiness(
                    [self._ollama_model],
                    configured_model=str(config.llm.vision_local_model),
                )
                full_prompt = build_multimodal_prompt(
                    full_prompt,
                    build_attachment_vision_hints(attachments),
                    readiness,
                )
            self.prompt_requested.emit(full_prompt, [str(p) for p in attachments])

        def _submit_live_prompt(self, prompt: str) -> None:
            from adv_archon.desktop.voice_commands import parse_live_turns

            try:
                max_turns = parse_live_turns(prompt)
            except ValueError as exc:
                self._append_system(str(exc))
                self._input.clear()
                return
            if max_turns is None:
                return
            if self._home_visible:
                self._clear_message_area()
                self._home_visible = False
                self._set_nav_context("chat")
            self._input.clear()
            self._pending_prompt = prompt
            self._pending_attachments = []
            self._active_tool_names = []
            self._last_snapshot = None
            self._refresh_sources_view()
            self._refresh_tool_badges()
            self._append_user(prompt, [])
            self._append_assistant_prefix()
            self._current_stream_text = ""
            self._stream_buffer = ""
            self._voice_transcript_edit = None
            self._set_busy(True, task="prompt")
            self.live_requested.emit(max_turns, self._active_exp_context)

        def _send_nav_prompt(self, prompt: str) -> None:
            self._input.setPlainText(prompt)
            self._submit_prompt()

        def _set_nav_context(self, active: str) -> None:
            self._active_nav_context = active
            navs = {
                "home": getattr(self, "_nav_home_btn", None),
                "review": getattr(self, "_nav_review_btn", None),
                "chat": getattr(self, "_nav_chat_btn", None),
                "research": getattr(self, "_nav_research_btn", None),
                "system": getattr(self, "_system_button", None),
                "training": getattr(self, "_nav_training_btn", None),
            }
            for key, btn in navs.items():
                if btn is not None:
                    btn.setObjectName("NavBtnActive" if key == active else "NavBtn")
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)

        def _show_dashboard_home(self, *, defer_load: bool = False) -> None:
            if defer_load:
                self._show_dashboard_home_skeleton()
                QTimer.singleShot(700, self._load_dashboard_home_if_visible)
                return

            from adv_archon.core.expediente import ExpedienteStore
            from adv_archon.core.workspace_v2 import build_workspace_snapshot

            self._close_workspace_panels()
            self._clear_message_area()
            self._home_visible = True
            self._set_nav_context("home")
            data_dir = self._studio_data_dir()
            workspace_snapshot = build_workspace_snapshot(
                (Path.home() / "Desktop", data_dir),
                engine_status=self._ollama_state,
                ollama_model=self._ollama_model,
                last_expediente=self._last_exp_label,
            )
            store = ExpedienteStore(data_dir / "expedientes.db")
            expedientes = store.list_all()
            recent = expedientes[:5]
            reports = sum(1 for exp in expedientes if getattr(exp, "report_path", ""))
            risks = 0
            for exp in expedientes:
                try:
                    ctx = json.loads(exp.site_context) if exp.site_context else {}
                except (TypeError, ValueError):
                    ctx = {}
                checks = ctx.get("legal_checks") if isinstance(ctx, dict) else []
                if isinstance(checks, list):
                    risks += sum(
                        1
                        for check in checks
                        if isinstance(check, dict)
                        and str(check.get("status") or "")
                        in {"conditional", "pending_review", "missing"}
                    )

            page = QFrame()
            page.setObjectName("HomeStudio")
            page_lay = QVBoxLayout(page)
            page_lay.setContentsMargins(6, 4, 6, 4)
            page_lay.setSpacing(14)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QHBoxLayout(hero)
            hero_lay.setContentsMargins(18, 16, 18, 16)
            hero_lay.setSpacing(16)
            hero_lay.addWidget(self._make_logo(58))
            hero_text = QVBoxLayout()
            eyebrow = QLabel("ADV ARCHON STUDIO")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Expedientes urbanísticos, de la parcela al informe.")
            title.setObjectName("StudioTitle")
            title.setWordWrap(True)
            subtitle = QLabel(
                "Crea un expediente, ADV ARCHON consulta fuentes oficiales, detecta "
                "riesgos y genera un informe preliminar profesional."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            hero_text.addWidget(eyebrow)
            hero_text.addWidget(title)
            hero_text.addWidget(subtitle)
            hero_lay.addLayout(hero_text, 1)
            new_btn = QPushButton("Nuevo expediente")
            new_btn.setObjectName("Primary")
            new_btn.clicked.connect(lambda: self._open_expedientes(open_new=True))
            hero_lay.addWidget(new_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
            page_lay.addWidget(hero)

            action_grid = QGridLayout()
            action_grid.setHorizontalSpacing(10)
            action_grid.setVerticalSpacing(10)
            actions = [
                (
                    "Research",
                    "Investiga fuentes, extrae fórmulas y prepara entregables.",
                    self._open_research_workbench,
                    "Primary",
                ),
                (
                    "Documentos",
                    f"{len(workspace_snapshot.documents)} entregables generados.",
                    lambda: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(str(Path.home() / "Desktop"))
                    ),
                    "Ghost",
                ),
                (
                    "Estado sistema",
                    "Motor local, rendimiento, permisos y modelos.",
                    self._open_system_status,
                    "Ghost",
                ),
                (
                    "Acciones rápidas",
                    "Chat, voz, adjuntos y primer borrador desde un único flujo.",
                    self._show_chat_home,
                    "Ghost",
                ),
                (
                    "Expedientes",
                    "Lista, detalle, plano, análisis y exportación PDF.",
                    lambda: self._open_expedientes(),
                    "Ghost",
                ),
            ]
            for index, (heading, copy, callback, btn_style) in enumerate(actions):
                card = QFrame()
                card.setObjectName("StudioCard")
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(14, 14, 14, 14)
                card_lay.setSpacing(8)
                h = QLabel(heading)
                h.setObjectName("StudioCase")
                body = QLabel(copy)
                body.setObjectName("Sub")
                body.setWordWrap(True)
                btn = QPushButton("Abrir")
                btn.setObjectName(btn_style)
                btn.clicked.connect(callback)
                card_lay.addWidget(h)
                card_lay.addWidget(body)
                card_lay.addStretch(1)
                card_lay.addWidget(btn)
                action_grid.addWidget(card, index // 3, index % 3)
            page_lay.addLayout(action_grid)

            metrics_row = QHBoxLayout()
            metrics_row.setSpacing(10)
            metrics = [
                ("Expedientes", str(len(expedientes))),
                ("Informes", str(reports)),
                ("Documentos", str(len(workspace_snapshot.documents))),
                ("Riesgos", str(risks)),
                ("Ollama", self._ollama_state),
                ("Modelo", self._ollama_model),
            ]
            for label, value in metrics:
                box = QFrame()
                box.setObjectName("StudioMetric")
                box_lay = QVBoxLayout(box)
                box_lay.setContentsMargins(12, 10, 12, 10)
                value_lbl = QLabel(value)
                value_lbl.setObjectName("StudioDecision")
                value_lbl.setWordWrap(True)
                label_lbl = QLabel(label)
                label_lbl.setObjectName("Faint")
                box_lay.addWidget(value_lbl)
                box_lay.addWidget(label_lbl)
                metrics_row.addWidget(box)
            page_lay.addLayout(metrics_row)

            bottom_row = QHBoxLayout()
            bottom_row.setSpacing(12)
            recent_card = QFrame()
            recent_card.setObjectName("Panel")
            recent_lay = QVBoxLayout(recent_card)
            recent_lay.setContentsMargins(14, 14, 14, 14)
            recent_lay.setSpacing(8)
            recent_title = QLabel("Últimos expedientes")
            recent_title.setObjectName("StudioCase")
            recent_lay.addWidget(recent_title)
            if recent:
                for exp in recent:
                    row = QFrame()
                    row.setObjectName("StudioMetric")
                    row_lay = QHBoxLayout(row)
                    row_lay.setContentsMargins(10, 8, 10, 8)
                    txt = QLabel(
                        f"{exp.title}\n{exp.municipality or exp.address or 'Sin ubicación'}"
                    )
                    txt.setObjectName("Sub")
                    txt.setWordWrap(True)
                    open_btn = QPushButton("Abrir")
                    open_btn.setObjectName("Ghost")
                    open_btn.clicked.connect(
                        lambda _checked=False, eid=exp.id: self._open_expedientes(
                            selected_id=eid
                        )
                    )
                    row_lay.addWidget(txt, 1)
                    row_lay.addWidget(open_btn)
                    recent_lay.addWidget(row)
            else:
                empty = QLabel("Aún no hay expedientes. Empieza por Nuevo expediente.")
                empty.setObjectName("Sub")
                empty.setWordWrap(True)
                recent_lay.addWidget(empty)
            bottom_row.addWidget(recent_card, 2)

            docs_card = QFrame()
            docs_card.setObjectName("Panel")
            docs_lay = QVBoxLayout(docs_card)
            docs_lay.setContentsMargins(14, 14, 14, 14)
            docs_lay.setSpacing(8)
            docs_title = QLabel("Documentos generados")
            docs_title.setObjectName("StudioCase")
            docs_lay.addWidget(docs_title)
            if workspace_snapshot.documents:
                for document in workspace_snapshot.documents[:5]:
                    row = QFrame()
                    row.setObjectName("StudioMetric")
                    row_lay = QHBoxLayout(row)
                    row_lay.setContentsMargins(10, 8, 10, 8)
                    txt = QLabel(f"{document.title}\n{document.kind.upper()}")
                    txt.setObjectName("Sub")
                    txt.setWordWrap(True)
                    open_btn = QPushButton("Abrir")
                    open_btn.setObjectName("Ghost")
                    open_btn.clicked.connect(
                        lambda _checked=False, p=document.path: QDesktopServices.openUrl(
                            QUrl.fromLocalFile(p)
                        )
                    )
                    row_lay.addWidget(txt, 1)
                    row_lay.addWidget(open_btn)
                    docs_lay.addWidget(row)
            else:
                empty_docs = QLabel(
                    "Aún no hay PDF/DOCX/XLSX generados. Usa Research o Expedientes."
                )
                empty_docs.setObjectName("Sub")
                empty_docs.setWordWrap(True)
                docs_lay.addWidget(empty_docs)
            docs_lay.addStretch(1)
            bottom_row.addWidget(docs_card, 1)

            activity_card = QFrame()
            activity_card.setObjectName("Panel")
            activity_lay = QVBoxLayout(activity_card)
            activity_lay.setContentsMargins(14, 14, 14, 14)
            activity_lay.setSpacing(8)
            activity_title = QLabel("Última actividad")
            activity_title.setObjectName("StudioCase")
            activity_lay.addWidget(activity_title)
            for item in workspace_snapshot.recent_activity[:5]:
                activity = QLabel(f"• {item}")
                activity.setObjectName("Sub")
                activity.setWordWrap(True)
                activity_lay.addWidget(activity)
            activity_lay.addStretch(1)
            bottom_row.addWidget(activity_card, 1)
            page_lay.addLayout(bottom_row, 1)

            idx = self._messages_layout.count() - 1
            self._messages_layout.insertWidget(idx, page)
            self._status_label.setText("Inicio Studio listo.")
            self.statusBar().showMessage("Inicio Studio listo.", 2500)

        def _load_dashboard_home_if_visible(self) -> None:
            if self._home_visible:
                self._show_dashboard_home()

        def _show_dashboard_home_skeleton(self) -> None:
            self._close_workspace_panels()
            self._clear_message_area()
            self._home_visible = True
            self._set_nav_context("home")

            page = QFrame()
            page.setObjectName("HomeStudio")
            page_lay = QVBoxLayout(page)
            page_lay.setContentsMargins(6, 4, 6, 4)
            page_lay.setSpacing(14)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QHBoxLayout(hero)
            hero_lay.setContentsMargins(18, 16, 18, 16)
            hero_lay.setSpacing(16)
            hero_lay.addWidget(self._make_logo(58))
            hero_text = QVBoxLayout()
            eyebrow = QLabel("ADV ARCHON STUDIO")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Expedientes urbanísticos, de la parcela al informe.")
            title.setObjectName("StudioTitle")
            title.setWordWrap(True)
            subtitle = QLabel(
                "Ventana lista. Preparando motor local, expedientes y métricas en segundo plano."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            hero_text.addWidget(eyebrow)
            hero_text.addWidget(title)
            hero_text.addWidget(subtitle)
            hero_lay.addLayout(hero_text, 1)
            page_lay.addWidget(hero)

            action_row = QHBoxLayout()
            action_row.setSpacing(10)
            for heading, copy in (
                ("Nuevo expediente", "Disponible en cuanto termine la carga ligera."),
                ("Studio Demo", "Casos de muestra, informes y trazabilidad."),
                ("Research", "Investigación, evidencias y Excel auditable."),
            ):
                card = QFrame()
                card.setObjectName("StudioCard")
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(14, 14, 14, 14)
                card_lay.setSpacing(8)
                h = QLabel(heading)
                h.setObjectName("StudioCase")
                body = QLabel(copy)
                body.setObjectName("Sub")
                body.setWordWrap(True)
                card_lay.addWidget(h)
                card_lay.addWidget(body)
                card_lay.addStretch(1)
                action_row.addWidget(card)
            page_lay.addLayout(action_row)

            loading = QLabel(
                "Motor cargando · Knowledge diferido · Voz inactiva hasta pulsar Hablar"
            )
            loading.setObjectName("Faint")
            loading.setWordWrap(True)
            page_lay.addWidget(loading)
            page_lay.addStretch(1)

            idx = self._messages_layout.count() - 1
            self._messages_layout.insertWidget(idx, page)
            self._status_label.setText("Ventana lista. Preparando motor local…")
            self.statusBar().showMessage("Ventana lista. Preparando motor local…", 3000)

        def _show_professional_review(self, filter_key: str = "all") -> None:
            import html as _html

            from adv_archon.core.expediente import ExpedienteStore
            from adv_archon.core.professional_review import (
                REVIEW_FILTER_LABELS,
                build_professional_review_dashboard,
                normalize_review_filter,
            )

            self._close_workspace_panels()
            self._clear_message_area()
            self._home_visible = False
            self._professional_review_filter = normalize_review_filter(filter_key)
            self._set_nav_context("review")

            store = ExpedienteStore(self._studio_data_dir() / "expedientes.db")
            dashboard = build_professional_review_dashboard(store.list_all())
            active_steps = dashboard.filtered(self._professional_review_filter)
            summary = dashboard.summary

            page = QFrame()
            page.setObjectName("HomeStudio")
            page_lay = QVBoxLayout(page)
            page_lay.setContentsMargins(6, 4, 6, 4)
            page_lay.setSpacing(12)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QHBoxLayout(hero)
            hero_lay.setContentsMargins(18, 14, 18, 14)
            hero_lay.setSpacing(16)
            hero_lay.addWidget(self._make_logo(52))
            hero_text = QVBoxLayout()
            eyebrow = QLabel("CENTRO DE REVISIÓN PROFESIONAL")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Decisiones técnicas de expediente, trazables y revisables.")
            title.setObjectName("StudioTitle")
            title.setWordWrap(True)
            subtitle = QLabel(
                "Valida pasos del agente, acepta advertencias, decide qué entra en "
                "informe y localiza lo que necesita revisión humana."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            hero_text.addWidget(eyebrow)
            hero_text.addWidget(title)
            hero_text.addWidget(subtitle)
            hero_lay.addLayout(hero_text, 1)
            open_btn = QPushButton("Abrir expedientes")
            open_btn.setObjectName("Primary")
            open_btn.clicked.connect(lambda: self._open_expedientes())
            hero_lay.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
            page_lay.addWidget(hero)

            metrics_row = QHBoxLayout()
            metrics_row.setSpacing(8)
            metrics = [
                ("Pasos", summary.total_steps),
                ("Pendientes", summary.pending),
                ("Necesitan revisión", summary.needs_review),
                ("Validados", summary.validated),
                ("Advertencias", summary.accepted_warnings),
                ("Excluidos", summary.excluded),
            ]
            for label, value in metrics:
                box = QFrame()
                box.setObjectName("StudioMetric")
                box_lay = QVBoxLayout(box)
                box_lay.setContentsMargins(10, 8, 10, 8)
                value_lbl = QLabel(str(value))
                value_lbl.setObjectName("StudioDecision")
                label_lbl = QLabel(label)
                label_lbl.setObjectName("Faint")
                label_lbl.setWordWrap(True)
                box_lay.addWidget(value_lbl)
                box_lay.addWidget(label_lbl)
                metrics_row.addWidget(box)
            page_lay.addLayout(metrics_row)

            filter_row = QHBoxLayout()
            filter_row.setSpacing(6)
            for key in (
                "all",
                "needs_review",
                "pending",
                "validated",
                "warnings",
                "excluded",
                "repeat",
            ):
                btn = QPushButton(
                    f"{REVIEW_FILTER_LABELS[key]} · {summary.count_for_filter(key)}"
                )
                btn.setObjectName(
                    "Primary" if key == self._professional_review_filter else "Ghost"
                )
                btn.clicked.connect(
                    lambda _checked=False, selected=key: self._show_professional_review(
                        selected
                    )
                )
                filter_row.addWidget(btn)
            filter_row.addStretch(1)
            page_lay.addLayout(filter_row)

            browser = QTextBrowser()
            browser.setObjectName("Panel")
            browser.setOpenExternalLinks(False)
            browser.anchorClicked.connect(self._handle_professional_review_link)
            browser.setHtml(
                self._professional_review_html(
                    active_steps,
                    total_steps=summary.total_steps,
                    active_label=REVIEW_FILTER_LABELS[self._professional_review_filter],
                    escape=_html.escape,
                )
            )
            page_lay.addWidget(browser, 1)

            idx = self._messages_layout.count() - 1
            self._messages_layout.insertWidget(idx, page)
            self._status_label.setText("Vista Revisión Profesional lista.")
            self.statusBar().showMessage("Revisión Profesional actualizada.", 2500)

        def _professional_review_html(
            self,
            steps: object,
            *,
            total_steps: int,
            active_label: str,
            escape: object,
        ) -> str:
            esc = escape
            step_items = list(steps) if steps else []
            if not step_items:
                rows = (
                    "<div class='empty'>No hay pasos en este filtro. "
                    "Crea o analiza expedientes para alimentar la revisión profesional.</div>"
                )
            else:
                chunks: list[str] = []
                for step in step_items:
                    include_label = (
                        "Incluido en informe"
                        if step.include_in_report
                        else "Excluido del informe"
                    )
                    risk_class = {
                        "alto": "risk-high",
                        "medio": "risk-medium",
                        "bajo": "risk-low",
                    }.get(step.risk_level, "risk-medium")
                    action_links = [
                        self._professional_review_action_link(step, "validate", "Validar"),
                        self._professional_review_action_link(
                            step,
                            "accept-warning",
                            "Aceptar advertencia",
                        ),
                        self._professional_review_action_link(step, "repeat", "Repetir"),
                    ]
                    if step.include_in_report:
                        action_links.append(
                            self._professional_review_action_link(
                                step,
                                "exclude",
                                "Excluir informe",
                            )
                        )
                    else:
                        action_links.append(
                            self._professional_review_action_link(
                                step,
                                "include",
                                "Incluir informe",
                            )
                        )
                    action_links.append(
                        "<a class='ghost' href='professional-review:open:"
                        f"{esc(step.expediente_id)}'>Abrir expediente</a>"
                    )
                    note_html = (
                        f"<p class='note'>{esc(step.review_note)}</p>"
                        if step.review_note
                        else ""
                    )
                    chunks.append(
                        "<section class='card'>"
                        "<div class='topline'>"
                        f"<span class='case'>{esc(step.expediente_title)}</span>"
                        f"<span class='muted'>{esc(step.municipality)}</span>"
                        f"<span class='risk {risk_class}'>{esc(step.risk_label)}</span>"
                        "</div>"
                        f"<h3>{esc(step.step_title)}</h3>"
                        "<div class='badges'>"
                        f"<span>{esc(step.step_status_label)}</span>"
                        f"<span>{esc(step.review_label)}</span>"
                        f"<span>{esc(include_label)}</span>"
                        f"<span>Confianza {esc(step.confidence)}</span>"
                        "</div>"
                        "<dl>"
                        f"<dt>Dato oficial consultado</dt><dd>{esc(step.official_data)}</dd>"
                        f"<dt>Inferencia de ARCHON</dt><dd>{esc(step.archon_inference)}</dd>"
                        f"<dt>Acción recomendada</dt><dd>{esc(step.recommended_action)}</dd>"
                        "</dl>"
                        f"{note_html}"
                        f"<div class='actions'>{' '.join(action_links)}</div>"
                        "</section>"
                    )
                rows = "\n".join(chunks)
            return f"""
            <html>
            <head>
            <style>
                body {{
                    background: #F7F7F4;
                    color: #050505;
                    font-family: -apple-system, BlinkMacSystemFont, "Inter", sans-serif;
                    margin: 0;
                    padding: 16px;
                }}
                .heading {{
                    color: #77746B;
                    font-size: 12px;
                    font-weight: 700;
                    letter-spacing: 1px;
                    text-transform: uppercase;
                    margin: 0 0 12px 0;
                }}
                .card {{
                    background: #FFFFFF;
                    border: 1px solid #D9D3C2;
                    border-radius: 8px;
                    margin: 0 0 12px 0;
                    padding: 14px 16px;
                }}
                .topline {{
                    color: #77746B;
                    font-size: 12px;
                    font-weight: 600;
                    margin-bottom: 5px;
                }}
                .case {{
                    color: #050505;
                    font-weight: 800;
                    margin-right: 8px;
                }}
                .muted {{
                    color: #8F897A;
                    margin-right: 8px;
                }}
                .risk {{
                    border-radius: 8px;
                    padding: 2px 7px;
                    font-size: 11px;
                    font-weight: 800;
                }}
                .risk-high {{ background: #F7DFDA; color: #B44535; }}
                .risk-medium {{ background: #FFF3CC; color: #9A7210; }}
                .risk-low {{ background: #E4F2E7; color: #367A48; }}
                h3 {{
                    color: #050505;
                    font-family: "Libre Baskerville", Georgia, serif;
                    font-size: 17px;
                    margin: 3px 0 8px 0;
                }}
                .badges span {{
                    background: #F7F7F4;
                    border: 1px solid #E4DCC8;
                    border-radius: 8px;
                    color: #504D46;
                    display: inline-block;
                    font-size: 11px;
                    font-weight: 700;
                    margin: 0 5px 6px 0;
                    padding: 4px 7px;
                }}
                dl {{
                    margin: 5px 0 8px 0;
                }}
                dt {{
                    color: #C9A227;
                    font-size: 11px;
                    font-weight: 800;
                    margin-top: 7px;
                    text-transform: uppercase;
                }}
                dd {{
                    color: #2E2E2C;
                    font-size: 13px;
                    margin: 2px 0 0 0;
                }}
                .note {{
                    background: #FFF8E5;
                    border-left: 3px solid #C9A227;
                    color: #504D46;
                    font-size: 12px;
                    margin: 8px 0;
                    padding: 7px 9px;
                }}
                .actions {{
                    border-top: 1px solid #E7E1D2;
                    margin-top: 10px;
                    padding-top: 9px;
                }}
                a {{
                    background: #C9A227;
                    border-radius: 8px;
                    color: #050505;
                    display: inline-block;
                    font-size: 12px;
                    font-weight: 800;
                    margin: 0 6px 6px 0;
                    padding: 6px 9px;
                    text-decoration: none;
                }}
                a.ghost {{
                    background: #F7F7F4;
                    border: 1px solid #D9D3C2;
                    color: #2E2E2C;
                }}
                .empty {{
                    background: #FFFFFF;
                    border: 1px dashed #D9D3C2;
                    border-radius: 8px;
                    color: #77746B;
                    font-size: 14px;
                    padding: 24px;
                    text-align: center;
                }}
            </style>
            </head>
            <body>
                <p class='heading'>
                    {esc(active_label)} · {len(step_items)} de {total_steps} pasos
                </p>
                {rows}
            </body>
            </html>
            """

        def _professional_review_action_link(
            self,
            step: object,
            action: str,
            label: str,
        ) -> str:
            import html as _html

            return (
                "<a href='professional-review:action:"
                f"{_html.escape(action)}:{_html.escape(step.expediente_id)}:"
                f"{_html.escape(step.step_code)}'>{_html.escape(label)}</a>"
            )

        def _handle_professional_review_link(self, url: object) -> None:
            import dataclasses

            from adv_archon.core.agent_plan import (
                append_agent_event,
                update_agent_step_review,
            )
            from adv_archon.core.expediente import ExpedienteStore

            raw = str(url.toString())
            if raw.startswith("professional-review:open:"):
                expediente_id = raw.split(":", 2)[2]
                self._open_expedientes(selected_id=expediente_id)
                return
            if not raw.startswith("professional-review:action:"):
                return
            parts = raw.split(":", 4)
            if len(parts) != 5:
                return
            _, _, action, expediente_id, step_code = parts
            store = ExpedienteStore(self._studio_data_dir() / "expedientes.db")
            exp = store.get(expediente_id)
            if not exp:
                self.statusBar().showMessage("No se encontró el expediente.", 3500)
                return
            action_messages = {
                "validate": "Paso validado por arquitecto.",
                "accept-warning": "Advertencia aceptada por arquitecto.",
                "repeat": "Repetición solicitada; abre el expediente para ejecutarla.",
                "include": "Paso incluido expresamente en el informe.",
                "exclude": "Paso excluido del informe por arquitecto.",
            }
            message = action_messages.get(action, "Decisión registrada.")
            updated = dataclasses.replace(
                exp,
                agent_step_reviews=update_agent_step_review(
                    exp.agent_step_reviews,
                    step_code=step_code,
                    action=action,
                ),
                agent_history=append_agent_event(
                    exp.agent_history,
                    step_code=step_code,
                    title="Decisión arquitecto",
                    status="completed" if action != "repeat" else "pending",
                    message=message,
                ),
            )
            store.update(updated)
            from adv_archon.core.office_memory import OfficeMemoryStore

            office_store = OfficeMemoryStore(self._studio_data_dir() / "office_memory.db")
            try:
                office_store.record_step_decision(
                    municipality=exp.municipality,
                    step_code=step_code,
                    action=action,
                    label=message,
                    source="professional_review",
                )
            finally:
                office_store.close()
            self._last_exp_label = updated.title
            self._refresh_status_bar()
            self._show_professional_review(self._professional_review_filter)
            self.statusBar().showMessage(message, 4000)
            if action == "repeat":
                QTimer.singleShot(
                    250,
                    lambda eid=expediente_id: self._open_expedientes(selected_id=eid),
                )

        def _open_system_status(self) -> None:
            self._close_workspace_panels()
            self._clear_message_area()
            self._home_visible = False
            self._set_nav_context("system")

            page = QFrame()
            page.setObjectName("HomeStudio")
            lay = QVBoxLayout(page)
            lay.setContentsMargins(6, 4, 6, 4)
            lay.setSpacing(14)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QHBoxLayout(hero)
            hero_lay.setContentsMargins(18, 16, 18, 16)
            hero_lay.setSpacing(16)
            hero_lay.addWidget(self._make_logo(52))
            text_col = QVBoxLayout()
            eyebrow = QLabel("ESTADO DEL SISTEMA")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Diagnóstico operativo antes de enseñar ADV ARCHON.")
            title.setObjectName("StudioTitle")
            title.setWordWrap(True)
            subtitle = QLabel(
                "Comprueba motor local, warmup, SQLite, fuentes oficiales y PDF. "
                "El análisis corre en segundo plano para no congelar la app."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            text_col.addWidget(eyebrow)
            text_col.addWidget(title)
            text_col.addWidget(subtitle)
            hero_lay.addLayout(text_col, 1)
            self._system_run_btn = QPushButton("Diagnosticar rendimiento")
            self._system_run_btn.setObjectName("Primary")
            self._system_run_btn.clicked.connect(self._run_system_diagnostics)
            hero_lay.addWidget(
                self._system_run_btn,
                alignment=Qt.AlignmentFlag.AlignVCenter,
            )
            lay.addWidget(hero)

            cards = QHBoxLayout()
            cards.setSpacing(10)
            self._system_cards: dict[str, QLabel] = {}
            for key, label, value in (
                ("demo", "Demo", "Pendiente"),
                ("ollama", "Ollama", self._ollama_state),
                ("model", "Modelo", self._ollama_model),
                ("sources", "Fuentes", "Sin medir"),
                ("pdf", "PDF", "Sin medir"),
            ):
                card = QFrame()
                card.setObjectName("StudioMetric")
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(12, 10, 12, 10)
                value_lbl = QLabel(value)
                value_lbl.setObjectName("StudioDecision")
                value_lbl.setWordWrap(True)
                label_lbl = QLabel(label)
                label_lbl.setObjectName("Faint")
                card_lay.addWidget(value_lbl)
                card_lay.addWidget(label_lbl)
                self._system_cards[key] = value_lbl
                cards.addWidget(card)
            lay.addLayout(cards)

            report_panel = QFrame()
            report_panel.setObjectName("Panel")
            report_lay = QVBoxLayout(report_panel)
            report_lay.setContentsMargins(14, 14, 14, 14)
            report_lay.setSpacing(10)
            report_header = QHBoxLayout()
            report_title = QLabel("Informe accionable")
            report_title.setObjectName("StudioCase")
            report_header.addWidget(report_title, 1)
            self._system_export_btn = QPushButton("Exportar diagnóstico")
            self._system_export_btn.setObjectName("Ghost")
            self._system_export_btn.setEnabled(self._last_performance_report is not None)
            self._system_export_btn.clicked.connect(self._export_system_diagnostics)
            report_header.addWidget(self._system_export_btn)
            report_lay.addLayout(report_header)
            self._system_report_view = QTextEdit()
            self._system_report_view.setReadOnly(True)
            self._system_report_view.setMinimumHeight(330)
            self._system_report_view.setPlainText(
                self._last_performance_report.render_markdown()
                if self._last_performance_report is not None
                else (
                    "Pulsa “Diagnosticar rendimiento” para generar una lectura real "
                    "del estado de ADV ARCHON en este Mac.\n\n"
                    "El resultado indicará si está listo para demo, qué puede ir lento "
                    "y qué conviene arreglar antes de enseñarlo a un despacho."
                )
            )
            report_lay.addWidget(self._system_report_view, 1)
            lay.addWidget(report_panel, 1)

            idx = self._messages_layout.count() - 1
            self._messages_layout.insertWidget(idx, page)
            self._status_label.setText("Estado del sistema listo.")
            self.statusBar().showMessage("Panel Estado del Sistema listo.", 2500)
            if self._last_performance_report is not None:
                self._render_system_report(self._last_performance_report)

        def _open_research_workbench(self) -> None:
            self._close_workspace_panels()
            self._clear_message_area()
            self._home_visible = False
            self._set_nav_context("research")

            page = QFrame()
            page.setObjectName("HomeStudio")
            lay = QVBoxLayout(page)
            lay.setContentsMargins(6, 4, 6, 4)
            lay.setSpacing(14)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QHBoxLayout(hero)
            hero_lay.setContentsMargins(18, 16, 18, 16)
            hero_lay.setSpacing(16)
            hero_lay.addWidget(self._make_logo(52))
            text_col = QVBoxLayout()
            eyebrow = QLabel("AGENTIC STUDIO")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Research Workbench")
            title.setObjectName("StudioTitle")
            subtitle = QLabel(
                "Investiga, extrae evidencias, detecta fórmulas y exporta entregables."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            text_col.addWidget(eyebrow)
            text_col.addWidget(title)
            text_col.addWidget(subtitle)
            hero_lay.addLayout(text_col, 1)
            lay.addWidget(hero)

            body = QHBoxLayout()
            body.setSpacing(12)

            brief_panel = QFrame()
            brief_panel.setObjectName("Panel")
            brief_lay = QVBoxLayout(brief_panel)
            brief_lay.setContentsMargins(14, 14, 14, 14)
            brief_lay.setSpacing(10)
            brief_title = QLabel("Brief")
            brief_title.setObjectName("StudioCase")
            brief_lay.addWidget(brief_title)

            question_input = QPlainTextEdit()
            question_input.setPlaceholderText(
                "Ej.: resuelve este trabajo, busca fuentes y prepara entrega..."
            )
            question_input.setMinimumHeight(140)
            brief_lay.addWidget(question_input)

            attachments_label = QLabel("Adjuntos: ninguno")
            attachments_label.setObjectName("Faint")
            attachments_label.setWordWrap(True)
            brief_lay.addWidget(attachments_label)

            actions = QHBoxLayout()
            attach_btn = QPushButton("Adjuntar")
            attach_btn.setObjectName("Ghost")
            run_btn = QPushButton("Ejecutar investigación")
            run_btn.setObjectName("Primary")
            actions.addWidget(attach_btn)
            actions.addWidget(run_btn)
            brief_lay.addLayout(actions)

            export_docx_btn = QPushButton("Exportar DOCX")
            export_docx_btn.setObjectName("Ghost")
            export_pdf_btn = QPushButton("Exportar PDF")
            export_pdf_btn.setObjectName("Ghost")
            export_xlsx_btn = QPushButton("Exportar Excel auditoría")
            export_xlsx_btn.setObjectName("Ghost")
            export_docx_btn.setEnabled(False)
            export_pdf_btn.setEnabled(False)
            export_xlsx_btn.setEnabled(False)
            brief_lay.addWidget(export_docx_btn)
            brief_lay.addWidget(export_pdf_btn)
            brief_lay.addWidget(export_xlsx_btn)
            brief_lay.addStretch(1)
            body.addWidget(brief_panel, 1)

            result_panel = QFrame()
            result_panel.setObjectName("Panel")
            result_lay = QVBoxLayout(result_panel)
            result_lay.setContentsMargins(14, 14, 14, 14)
            result_lay.setSpacing(10)
            result_title = QLabel("Resultado")
            result_title.setObjectName("StudioCase")
            result_view = QTextEdit()
            result_view.setReadOnly(True)
            result_view.setMinimumHeight(420)
            result_view.setPlainText(
                "Research Workbench listo. Adjunta un enunciado/PDF o escribe el brief."
            )
            result_lay.addWidget(result_title)
            result_lay.addWidget(result_view, 1)
            body.addWidget(result_panel, 2)

            from adv_archon.desktop.document_intelligence_panel import (
                DocumentIntelligencePanel,
            )
            from adv_archon.desktop.draft_editor import DraftEditorWidget

            draft_editor = DraftEditorWidget()
            draft_editor.setMinimumWidth(320)
            draft_editor.load_draft(
                {
                    "title": "Borrador de entrega",
                    "status": "Pendiente de investigación",
                    "executive_summary": "",
                    "sections": [
                        {
                            "id": "synthesis",
                            "title": "Síntesis",
                            "content": (
                                "Ejecuta una investigación para generar el borrador "
                                "editable."
                            ),
                        }
                    ],
                }
            )
            intelligence_panel = DocumentIntelligencePanel()
            intelligence_panel.setMinimumWidth(320)
            document_column = QWidget()
            document_column_lay = QVBoxLayout(document_column)
            document_column_lay.setContentsMargins(0, 0, 0, 0)
            document_column_lay.setSpacing(10)
            document_column_lay.addWidget(draft_editor, 2)
            document_column_lay.addWidget(intelligence_panel, 1)
            body.addWidget(document_column, 1)
            lay.addLayout(body, 1)

            state: dict[str, Any] = {
                "attachments": [],
                "result": None,
                "thread": None,
                "worker": None,
            }

            def render_attachments() -> None:
                names = [Path(path).name for path in state["attachments"]]
                attachments_label.setText(
                    "Adjuntos: " + (", ".join(names) if names else "ninguno")
                )

            def choose_attachments() -> None:
                paths, _filter = QFileDialog.getOpenFileNames(
                    self,
                    "Adjuntar material de investigación",
                    str(Path.home()),
                    "Documentos (*.pdf *.docx *.pptx *.xlsx *.txt *.md);;Todos (*)",
                )
                if paths:
                    state["attachments"] = list(dict.fromkeys([*state["attachments"], *paths]))
                    render_attachments()
                    intelligence_panel.set_empty(
                        "Adjuntos listos. Ejecuta la investigacion para detectar tablas, "
                        "formulas y magnitudes."
                    )

            def set_exports_enabled(enabled: bool) -> None:
                export_docx_btn.setEnabled(enabled)
                export_pdf_btn.setEnabled(enabled)
                export_xlsx_btn.setEnabled(enabled)

            class _ResearchWorker(QObject):
                completed = Signal(object)
                failed = Signal(str)
                finished = Signal()

                def __init__(self, question: str, attachments: list[str]) -> None:
                    super().__init__()
                    self._question = question
                    self._attachments = attachments

                def run(self) -> None:
                    try:
                        from adv_archon.core.research_workbench import (
                            run_research_workbench,
                        )

                        self.completed.emit(
                            run_research_workbench(
                                self._question,
                                attachment_paths=self._attachments,
                                search_results_per_query=4,
                                fetch_top_results=2,
                            )
                        )
                    except Exception as exc:
                        self.failed.emit(str(exc))
                    finally:
                        self.finished.emit()

            def render_result(result: object) -> str:
                payload = result.as_payload()
                lines = [
                    f"Pregunta: {payload['question']}",
                    "",
                    "Subpreguntas:",
                    *[f"- {item}" for item in payload["subquestions"]],
                    "",
                    "Síntesis:",
                    str(payload["synthesis"]),
                    "",
                    "Evidencias:",
                ]
                for item in payload["evidences"]:
                    lines.append(f"- {item['id']} · {item['title']} · {item['url']}")
                    lines.append(f"  {item['excerpt']}")
                if payload["formula_candidates"]:
                    lines.append("")
                    lines.append("Fórmulas / métodos detectados:")
                    lines.extend(f"- {item}" for item in payload["formula_candidates"])
                if payload["gaps"]:
                    lines.append("")
                    lines.append("Pendiente de validar:")
                    lines.extend(f"- {item}" for item in payload["gaps"])
                return "\n".join(lines)

            def run_research() -> None:
                question = question_input.toPlainText().strip()
                if not question:
                    self.statusBar().showMessage(
                        "Escribe primero el brief de investigación.",
                        3500,
                    )
                    return
                if state["thread"] is not None:
                    self.statusBar().showMessage("Investigación ya en curso.", 2500)
                    return
                set_exports_enabled(False)
                run_btn.setEnabled(False)
                result_view.setPlainText("Investigando fuentes y leyendo adjuntos...")
                thread = QThread(self)
                worker = _ResearchWorker(question, list(state["attachments"]))
                worker.moveToThread(thread)
                thread.started.connect(worker.run)

                def done(result: object) -> None:
                    state["result"] = result
                    result_view.setPlainText(render_result(result))
                    from adv_archon.core.document_draft import build_research_draft

                    draft = build_research_draft(result).to_dict()
                    draft_editor.load_draft(draft)
                    intelligence_panel.analyze_draft(
                        draft,
                        attachment_names=[Path(path).name for path in state["attachments"]],
                    )
                    set_exports_enabled(True)
                    self.statusBar().showMessage(
                        f"Investigación lista: {getattr(result, 'evidence_count', 0)} evidencias.",
                        5000,
                    )

                def failed(message: str) -> None:
                    result_view.setPlainText(f"No se pudo completar la investigación:\n{message}")
                    self.statusBar().showMessage("Research Workbench falló.", 6000)

                def cleanup() -> None:
                    state["thread"] = None
                    state["worker"] = None
                    run_btn.setEnabled(True)

                worker.completed.connect(done)
                worker.failed.connect(failed)
                worker.finished.connect(worker.deleteLater)
                worker.finished.connect(thread.quit)
                thread.finished.connect(thread.deleteLater)
                thread.finished.connect(cleanup)
                state["thread"] = thread
                state["worker"] = worker
                thread.start()

            def export_docx() -> None:
                result = state.get("result")
                if result is None:
                    return
                from adv_archon.core.document_draft import DocumentDraft
                from adv_archon.core.docx_generator import generate_research_docx

                output = Path.home() / "Desktop" / "adv_archon_research_workbench.docx"
                draft = DocumentDraft.from_dict(draft_editor.current_draft())
                generate_research_docx(draft, output)
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

            def export_pdf() -> None:
                result = state.get("result")
                if result is None:
                    return
                from adv_archon.core.document_draft import DocumentDraft
                from adv_archon.core.pdf_generator_v2 import generate_draft_pdf

                output = Path.home() / "Desktop" / "adv_archon_research_workbench.pdf"
                draft = DocumentDraft.from_dict(draft_editor.current_draft())
                generate_draft_pdf(draft, output, archon_logo_path=logo_path())
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

            def export_xlsx() -> None:
                result = state.get("result")
                if result is None:
                    return
                from adv_archon.core.document_draft import DocumentDraft
                from adv_archon.core.xlsx_generator import generate_research_xlsx

                output = Path.home() / "Desktop" / "adv_archon_research_auditoria.xlsx"
                draft = DocumentDraft.from_dict(draft_editor.current_draft())
                generate_research_xlsx(draft, output)
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

            attach_btn.clicked.connect(choose_attachments)
            run_btn.clicked.connect(run_research)
            export_docx_btn.clicked.connect(export_docx)
            export_pdf_btn.clicked.connect(export_pdf)
            export_xlsx_btn.clicked.connect(export_xlsx)
            draft_editor.export_requested.connect(
                lambda kind: {
                    "docx": export_docx,
                    "pdf": export_pdf,
                    "xlsx": export_xlsx,
                }.get(str(kind), lambda: None)()
            )
            intelligence_panel.export_requested.connect(
                lambda kind: {
                    "docx": export_docx,
                    "pdf": export_pdf,
                    "xlsx": export_xlsx,
                }.get(str(kind), lambda: None)()
            )

            idx = self._messages_layout.count() - 1
            self._messages_layout.insertWidget(idx, page)
            self._status_label.setText("Research Workbench listo.")
            self.statusBar().showMessage("Research Workbench listo.", 2500)

        def _open_training_lab(self) -> None:
            from adv_archon.core.training_lab import (
                build_training_lab_status,
                default_synthetic_dataset_path,
                default_templates_path,
                render_training_lab_status,
            )

            self._close_workspace_panels()
            self._clear_message_area()
            self._home_visible = False
            self._set_nav_context("training")

            data_dir = self._studio_data_dir()
            status = build_training_lab_status(
                feedback_db=config.paths.feedback_db,
                templates_path=default_templates_path(project_root),
                synthetic_dataset_path=default_synthetic_dataset_path(data_dir),
            )

            page = QFrame()
            page.setObjectName("HomeStudio")
            lay = QVBoxLayout(page)
            lay.setContentsMargins(6, 4, 6, 4)
            lay.setSpacing(14)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QHBoxLayout(hero)
            hero_lay.setContentsMargins(18, 16, 18, 16)
            hero_lay.setSpacing(16)
            hero_lay.addWidget(self._make_logo(52))
            text_col = QVBoxLayout()
            eyebrow = QLabel("TRAINING LAB LOCAL")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Dataset, feedback y fine-tuning sin tocar scripts.")
            title.setObjectName("StudioTitle")
            title.setWordWrap(True)
            subtitle = QLabel(
                "Revisa ejemplos reales aprobados por el juez local, exporta dataset "
                "y genera sintéticos con Ollama para preparar experimentos LoRA offline."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            text_col.addWidget(eyebrow)
            text_col.addWidget(title)
            text_col.addWidget(subtitle)
            hero_lay.addLayout(text_col, 1)
            lay.addWidget(hero)

            cards = QHBoxLayout()
            cards.setSpacing(10)
            metrics = (
                ("Reales", str(status.feedback.total)),
                ("Aprobados", str(status.feedback.approved)),
                ("Sintéticos", str(status.synthetic_examples)),
                ("Plantillas", str(status.templates_count)),
                ("Estado", status.readiness_label),
            )
            for label, value in metrics:
                card = QFrame()
                card.setObjectName("StudioMetric")
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(12, 10, 12, 10)
                value_lbl = QLabel(value)
                value_lbl.setObjectName("StudioDecision")
                value_lbl.setWordWrap(True)
                label_lbl = QLabel(label)
                label_lbl.setObjectName("Faint")
                card_lay.addWidget(value_lbl)
                card_lay.addWidget(label_lbl)
                cards.addWidget(card)
            lay.addLayout(cards)

            body_row = QHBoxLayout()
            body_row.setSpacing(12)

            report_panel = QFrame()
            report_panel.setObjectName("Panel")
            report_lay = QVBoxLayout(report_panel)
            report_lay.setContentsMargins(14, 14, 14, 14)
            report_lay.setSpacing(10)
            report_title = QLabel("Preparación del dataset")
            report_title.setObjectName("StudioCase")
            report_lay.addWidget(report_title)
            self._training_lab_view = QTextEdit()
            self._training_lab_view.setReadOnly(True)
            self._training_lab_view.setMinimumHeight(300)
            self._training_lab_view.setPlainText(render_training_lab_status(status))
            report_lay.addWidget(self._training_lab_view, 1)
            body_row.addWidget(report_panel, 2)

            actions_panel = QFrame()
            actions_panel.setObjectName("Panel")
            actions_lay = QVBoxLayout(actions_panel)
            actions_lay.setContentsMargins(14, 14, 14, 14)
            actions_lay.setSpacing(10)
            actions_title = QLabel("Acciones")
            actions_title.setObjectName("StudioCase")
            actions_lay.addWidget(actions_title)
            export_btn = QPushButton("Exportar dataset real")
            export_btn.setObjectName("Primary")
            export_btn.clicked.connect(self._export_training_feedback_dataset)
            synth_btn = QPushButton("Generar 20 sintéticos")
            synth_btn.setObjectName("Ghost")
            synth_btn.clicked.connect(self._generate_training_synthetic_dataset)
            refresh_btn = QPushButton("Actualizar estado")
            refresh_btn.setObjectName("Ghost")
            refresh_btn.clicked.connect(self._open_training_lab)
            note = QLabel(
                "Fine-tuning sigue siendo offline y opcional. No se activa dentro "
                "del flujo normal de expedientes."
            )
            note.setObjectName("Sub")
            note.setWordWrap(True)
            actions_lay.addWidget(export_btn)
            actions_lay.addWidget(synth_btn)
            actions_lay.addWidget(refresh_btn)
            actions_lay.addSpacing(8)
            actions_lay.addWidget(note)
            actions_lay.addStretch(1)
            body_row.addWidget(actions_panel, 1)
            lay.addLayout(body_row, 1)

            idx = self._messages_layout.count() - 1
            self._messages_layout.insertWidget(idx, page)
            self._status_label.setText("Training Lab listo.")
            self.statusBar().showMessage("Training Lab listo.", 2500)

        def _export_training_feedback_dataset(self) -> None:
            from adv_archon.core.training_lab import (
                default_export_path,
                export_feedback_dataset,
            )

            result = export_feedback_dataset(
                feedback_db=config.paths.feedback_db,
                output_path=default_export_path(),
            )
            self.statusBar().showMessage(
                f"Dataset real exportado: {result.examples_exported} ejemplos.",
                5000,
            )
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.output_path.parent)))
            self._open_training_lab()

        def _generate_training_synthetic_dataset(self) -> None:
            if self._training_lab_ref is not None:
                self.statusBar().showMessage("Generación sintética ya en curso.", 2500)
                return

            class _SyntheticWorker(QObject):
                completed = Signal(object)
                failed = Signal(str)
                finished = Signal()

                def run(self) -> None:
                    try:
                        from adv_archon.core.training_lab import (
                            build_ollama_client,
                            default_synthetic_dataset_path,
                            default_templates_path,
                            generate_synthetic_dataset,
                        )

                        self.completed.emit(
                            generate_synthetic_dataset(
                                templates_path=default_templates_path(project_root),
                                output_path=default_synthetic_dataset_path(
                                    self_ref._studio_data_dir()
                                ),
                                client=build_ollama_client(config),
                                count=20,
                            )
                        )
                    except Exception as exc:
                        self.failed.emit(str(exc))
                    finally:
                        self.finished.emit()

            self_ref = self
            thread = QThread(self)
            worker = _SyntheticWorker()
            worker.moveToThread(thread)
            thread.started.connect(worker.run)

            def _done(result: object) -> None:
                generated = getattr(result, "generated", 0)
                requested = getattr(result, "requested", 0)
                self.statusBar().showMessage(
                    f"Dataset sintético generado: {generated}/{requested}.",
                    7000,
                )
                self._open_training_lab()

            def _failed(message: str) -> None:
                self.statusBar().showMessage(
                    f"No se pudo generar dataset sintético: {message}",
                    9000,
                )

            def _cleanup() -> None:
                self._training_lab_ref = None

            worker.completed.connect(_done)
            worker.failed.connect(_failed)
            worker.finished.connect(worker.deleteLater)
            worker.finished.connect(thread.quit)
            thread.finished.connect(_cleanup)
            thread.finished.connect(thread.deleteLater)
            self._training_lab_ref = (thread, worker)
            self.statusBar().showMessage("Generando dataset sintético con Ollama…", 5000)
            thread.start()

        def _run_system_diagnostics(self) -> None:
            if self._system_diag_ref is not None:
                self.statusBar().showMessage("Diagnóstico ya en curso.", 2500)
                return

            class _SystemDiagWorker(QObject):
                completed = Signal(object)
                failed = Signal(str)
                finished = Signal()

                def run(self) -> None:
                    try:
                        from adv_archon.core.performance_profiler import (
                            PerformanceProfiler,
                        )

                        profiler = PerformanceProfiler(
                            config=config,
                            project_root=project_root,
                        )
                        self.completed.emit(
                            profiler.run(
                                include_ollama=True,
                                include_qthread=False,
                                include_official_sources=True,
                            )
                        )
                    except Exception as exc:
                        self.failed.emit(str(exc))
                    finally:
                        self.finished.emit()

            self._system_run_btn.setEnabled(False)
            self._system_run_btn.setText("Diagnosticando…")
            self._system_export_btn.setEnabled(False)
            self._system_report_view.setPlainText(
                "Diagnosticando ADV ARCHON...\n\n"
                "- Comprobando Ollama y modelo local.\n"
                "- Midiendo SQLite y stores del producto.\n"
                "- Consultando fuentes oficiales españolas.\n"
                "- Generando PDF directo de prueba.\n\n"
                "Puedes seguir usando la ventana; este proceso no corre en el hilo UI."
            )
            self._system_cards["demo"].setText("Midiendo")
            self._status_label.setText("Diagnosticando rendimiento…")
            self.statusBar().showMessage("Diagnóstico del sistema en curso…")
            started = time.perf_counter()

            thread = QThread(self)
            thread.setObjectName("adv-archon-system-diagnostics")
            worker = _SystemDiagWorker()
            worker.moveToThread(thread)

            def _complete(report: object) -> None:
                from adv_archon.core.performance_profiler import (
                    PerformanceProbe,
                    PerformanceReport,
                )

                if isinstance(report, PerformanceReport):
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    qthread_probe = PerformanceProbe(
                        name="desktop_profiler_worker_roundtrip",
                        category="desktop",
                        elapsed_ms=round(elapsed_ms, 3),
                        status="ok" if elapsed_ms < 1000 else "warning",
                        detail="Profiler ejecutado desde QThread sin bloquear la UI",
                    )
                    report = PerformanceReport(
                        generated_at=report.generated_at,
                        project=report.project,
                        active_model=report.active_model,
                        fast_model=report.fast_model,
                        probes=report.probes + (qthread_probe,),
                        findings=report.findings,
                    )
                self._render_system_report(report)

            worker.completed.connect(_complete)
            worker.failed.connect(self._handle_system_diag_error)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(self._finish_system_diag)
            thread.started.connect(worker.run)
            self._system_diag_ref = (thread, worker)
            thread.start()

        def _render_system_report(self, report: object) -> None:
            self._last_performance_report = report
            with suppress(RuntimeError):
                markdown = report.render_markdown()
                self._system_report_view.setPlainText(markdown)
                self._system_export_btn.setEnabled(True)

            probes = {probe.name: probe for probe in report.probes}
            official = [
                probe for probe in report.probes if probe.category == "official_sources"
            ]
            official_errors = sum(1 for probe in official if probe.status == "error")
            official_slow = sum(1 for probe in official if probe.status == "warning")
            pdf = probes.get("generate_expediente_pdf")
            model = probes.get("ollama_model_available")
            ollama = probes.get("ollama_tags")
            worst = report.worst_severity
            ready_label = {
                "critical": "No apto",
                "warning": "Revisar",
                "info": "Listo",
            }.get(worst, "Revisar")
            with suppress(RuntimeError):
                self._system_cards["demo"].setText(ready_label)
                self._system_cards["ollama"].setText(
                    "OK" if ollama and ollama.status == "ok" else "Revisar"
                )
                self._system_cards["model"].setText(
                    "Instalado" if model and model.status == "ok" else "Falta"
                )
                if official_errors:
                    self._system_cards["sources"].setText(f"{official_errors} fallan")
                elif official_slow:
                    self._system_cards["sources"].setText(f"{official_slow} lentas")
                else:
                    self._system_cards["sources"].setText("OK")
                self._system_cards["pdf"].setText(
                    "OK" if pdf and pdf.status == "ok" else "Revisar"
                )
                self._status_label.setText(f"Estado del sistema: {ready_label}.")
                self.statusBar().showMessage(
                    f"Diagnóstico completado: {ready_label}.", 5000
                )

        def _handle_system_diag_error(self, message: str) -> None:
            with suppress(RuntimeError):
                self._system_report_view.setPlainText(
                    "No se pudo completar el diagnóstico.\n\n"
                    f"Detalle técnico: {message}\n\n"
                    "La app sigue operativa; revisa Ollama, red local y permisos antes "
                    "de una demo comercial."
                )
                self._system_cards["demo"].setText("Revisar")
                self._status_label.setText("Diagnóstico fallido.")
                self.statusBar().showMessage(
                    "No se pudo completar el diagnóstico.", 5000
                )

        def _finish_system_diag(self) -> None:
            self._system_diag_ref = None
            if hasattr(self, "_system_run_btn"):
                with suppress(RuntimeError):
                    self._system_run_btn.setEnabled(True)
                    self._system_run_btn.setText("Diagnosticar rendimiento")

        def _export_system_diagnostics(self) -> None:
            if self._last_performance_report is None:
                QMessageBox.information(
                    self,
                    "Estado del Sistema",
                    "Primero ejecuta un diagnóstico.",
                )
                return
            desktop = Path.home() / "Desktop"
            target = desktop / "ADV_ARCHON_diagnostico_sistema.md"
            target.write_text(
                self._last_performance_report.render_markdown(),
                encoding="utf-8",
            )
            self.statusBar().showMessage(f"Diagnóstico exportado: {target}", 5000)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

        def _send_daily_prompt(self) -> None:
            self._input.setPlainText(
                "Dame un briefing ejecutivo del día. Antes de responder usa mis "
                "fuentes personales disponibles: calendario local, Google Calendar, "
                "recordatorios, tareas, Gmail, Drive, Notes y conocimiento local. "
                "No hagas un briefing genérico: si una fuente falla, indícalo en "
                "el briefing y usa el resto."
            )
            self._submit_prompt()

        def _send_pgou_prompt(self) -> None:
            self._input.setPlainText(
                "muestra el estado de los municipios en el catálogo PGOU y dime "
                "cuáles están indexados y disponibles para análisis"
            )
            self._submit_prompt()

        def _show_pgou_status(self) -> None:
            runtime = getattr(self._backend_worker, "_runtime", None)
            try:
                tools = getattr(runtime, "urban_compliance_tools", None)
                if tools is not None:
                    result = tools.pgou_status()
                    payload = result.payload if hasattr(result, "payload") else {}
                else:
                    from adv_archon.core.pgou_store import PGOUStore

                    store = PGOUStore(config.paths.pgou_db)
                    munis = store.list_municipalities()
                    payload = {
                        "municipalities": [
                            {
                                "name": muni.name,
                                "chunks": muni.chunk_count,
                                "source": muni.source,
                                "indexed_at": muni.indexed_at,
                            }
                            for muni in munis
                        ],
                        "total": len(munis),
                    }
                municipalities = payload.get("municipalities", [])
                if not isinstance(municipalities, list):
                    municipalities = []
                indexed = [
                    str(item.get("name") or "")
                    for item in municipalities
                    if isinstance(item, dict) and item.get("name")
                ]
                total = payload.get("total", len(indexed))
                if indexed:
                    preview = ", ".join(indexed[:12])
                    if len(indexed) > 12:
                        preview += f"… (+{len(indexed) - 12})"
                    text = (
                        f"PGOU operativo: {total} municipio(s) indexado(s).\n\n"
                        f"Disponibles ahora: {preview}\n\n"
                        "Para analizar un plano, crea o abre un expediente, adjunta el "
                        "PDF y pulsa “Analizar con PGOU”."
                    )
                else:
                    text = (
                        "PGOU operativo, pero todavía no hay municipios indexados.\n\n"
                        "Usa el menú “Importar normativa PGOU…” para añadir una normativa "
                        "municipal antes de analizar planos."
                    )
                self._add_message_bubble("assistant", text)
            except Exception as exc:
                self._add_notice(
                    f"No se pudo consultar el catálogo PGOU: {exc}",
                    object_name="Err",
                )

        def _send_geo_prompt(self) -> None:
            self._add_message_bubble(
                "assistant",
                "Geolocalización lista para expedientes.\n\n"
                "Uso recomendado:\n"
                "1. Abre Expedientes.\n"
                "2. Crea un expediente nuevo.\n"
                "3. En Dirección puedes pegar coordenadas GPS, dirección postal "
                "o referencia catastral.\n"
                "4. ADV ARCHON resuelve municipio, Catastro, afecciones sectoriales "
                "y contexto PGOU preliminar.\n\n"
                "Ejemplos válidos:\n"
                "- 40.415363, -3.707398\n"
                "- Calle Mayor 24, Madrid\n"
                "- 2807901VK4720G0001ZX\n\n"
                "Este panel ya no espera al motor local: para consultar fuentes reales, "
                "entra por Expedientes o Modo demo.",
            )
            self.statusBar().showMessage("Geolocalización: guía rápida mostrada.", 3000)

        # ── Mode / profile ────────────────────────────────────────────────────
        def _load_controls_state(self) -> None:
            self._mode_combo.setCurrentText(self._selected_mode)
            self._profile_combo.setCurrentText(self._selected_profile)
            self._handle_busy_state_changed(self._busy_state)

        def _change_mode(self, mode: str) -> None:
            self._selected_mode = mode
            self._ollama_state = "Cargando…" if mode == "local" else "Cloud"
            self.mode_requested.emit(mode)
            self._refresh_status()
            if mode == "local":
                self._start_warmup_agent()

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
            self._refresh_status_bar()

        def _refresh_status_bar(self) -> None:
            if not hasattr(self, "_ollama_badge_lbl"):
                return
            colors = {
                "Listo": OK,
                "Cargando…": WARN,
                "Pendiente": WARN,
                "Sin conexión": ERR,
                "Cloud": INFO,
            }
            color = colors.get(self._ollama_state, TEXT_SUB)
            self._ollama_badge_lbl.setText(
                f"<span style='color:{color}'>●</span> Ollama: {self._ollama_state}"
            )
            self._ollama_badge_lbl.setTextFormat(Qt.TextFormat.RichText)
            self._model_badge_lbl.setText(f"Modelo: {self._ollama_model}")
            self._last_exp_badge_lbl.setText(f"Último expediente: {self._last_exp_label}")

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
            self._voice_button.setEnabled(can_send)
            self._add_button.setEnabled(accepts)
            self._import_button.setEnabled(can_send and has_attach)
            self._analyze_button.setEnabled(can_send and self._compliance.can_run)
            self._mode_combo.setEnabled(allows_cfg)
            self._profile_combo.setEnabled(allows_cfg)
            self._daily_action.setEnabled(can_send)
            self._nav_daily_btn.setEnabled(can_send)
            self._nav_pgou_btn.setEnabled(True)
            self._nav_geo_btn.setEnabled(True)
            self._nav_review_btn.setEnabled(accepts)
            self._nav_demo_btn.setEnabled(accepts)
            self._nav_client_btn.setEnabled(accepts)
            self._nav_pack_btn.setEnabled(accepts)
            self._nav_training_btn.setEnabled(accepts)
            self._nav_research_btn.setEnabled(accepts)
            self._settings_button.setEnabled(allows_cfg)
            self._system_button.setEnabled(accepts)
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

        # ── Settings ─────────────────────────────────────────────────────────
        def _open_settings(self) -> None:
            from PySide6.QtCore import QObject as _QObject
            from PySide6.QtCore import Signal as _Signal
            from PySide6.QtWidgets import QDialog, QDialogButtonBox

            class _ModelListWorker(_QObject):
                loaded = _Signal(object)
                failed = _Signal(str)
                finished = _Signal()

                def run(self) -> None:
                    try:
                        from adv_archon.desktop.ollama_models import fetch_ollama_models

                        self.loaded.emit(
                            fetch_ollama_models(
                                config.llm.ollama_base_url,
                                timeout=3.0,
                            )
                        )
                    except Exception as exc:
                        self.failed.emit(str(exc))
                    finally:
                        self.finished.emit()

            class _ModelListBridge(_QObject):
                loaded = _Signal(object)
                failed = _Signal(str)

            dlg = QDialog(self)
            dlg.setWindowTitle("Ajustes — ADV ARCHON")
            dlg.setMinimumWidth(500)
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(10)

            title = QLabel("Modelo local Ollama")
            title.setObjectName("AppName")
            layout.addWidget(title)

            help_lbl = QLabel(
                "Elige el modelo local que usará ADV ARCHON para análisis y chat. "
                "Los modelos más pequeños responden antes; los grandes suelen razonar mejor."
            )
            help_lbl.setObjectName("Sub")
            help_lbl.setWordWrap(True)
            layout.addWidget(help_lbl)

            model_combo = QComboBox()
            model_combo.addItem(f"{self._ollama_model} · actual", self._ollama_model)
            layout.addWidget(model_combo)

            status_lbl = QLabel("Consultando modelos instalados en Ollama…")
            status_lbl.setObjectName("Faint")
            status_lbl.setWordWrap(True)
            layout.addWidget(status_lbl)

            model_progress = QProgressBar()
            model_progress.setRange(0, 0)
            model_progress.setTextVisible(False)
            model_progress.setMaximumHeight(3)
            layout.addWidget(model_progress)

            refresh_btn = QPushButton("Actualizar lista")
            refresh_btn.setObjectName("Ghost")
            layout.addWidget(refresh_btn)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save
                | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
            layout.addWidget(buttons)

            def load_models() -> None:
                status_lbl.setText("Consultando modelos instalados en Ollama…")
                model_progress.setVisible(True)
                refresh_btn.setEnabled(False)
                thread = QThread(dlg)
                thread.setObjectName("adv-archon-model-loader")
                worker = _ModelListWorker()
                bridge = _ModelListBridge(dlg)
                worker.moveToThread(thread)

                def on_loaded(models: object) -> None:
                    current = self._ollama_model
                    model_combo.clear()
                    seen: set[str] = set()
                    for item in models if isinstance(models, list) else []:
                        name = getattr(item, "name", "")
                        if not name:
                            continue
                        seen.add(name)
                        model_combo.addItem(getattr(item, "display_label", name), name)
                    if current and current not in seen:
                        model_combo.insertItem(0, f"{current} · actual", current)
                    idx = model_combo.findData(current)
                    if idx >= 0:
                        model_combo.setCurrentIndex(idx)
                    count = model_combo.count()
                    status_lbl.setText(
                        f"{count} modelo{'s' if count != 1 else ''} disponible"
                        if count
                        else "Ollama responde, pero no hay modelos instalados."
                    )
                    model_progress.setVisible(False)
                    refresh_btn.setEnabled(True)
                    self._model_loader_ref = None

                def on_failed(message: str) -> None:
                    status_lbl.setText(
                        "No se pudo leer Ollama. Mantén la app usable y arranca "
                        f"Ollama cuando vayas a analizar. Detalle: {message[:140]}"
                    )
                    model_progress.setVisible(False)
                    refresh_btn.setEnabled(True)
                    self._model_loader_ref = None

                thread.started.connect(worker.run)
                worker.loaded.connect(bridge.loaded)
                worker.failed.connect(bridge.failed)
                worker.finished.connect(worker.deleteLater)
                worker.finished.connect(thread.quit)
                bridge.loaded.connect(on_loaded)
                bridge.failed.connect(on_failed)
                thread.finished.connect(thread.deleteLater)
                self._model_loader_ref = (thread, worker, bridge)
                thread.start()

            def save() -> None:
                selected = str(model_combo.currentData() or model_combo.currentText()).strip()
                if not selected:
                    status_lbl.setText("Selecciona un modelo válido.")
                    return
                try:
                    from adv_archon.core.config import save_ollama_model_preference

                    save_ollama_model_preference(config.paths.config_file, selected)
                except Exception as exc:
                    status_lbl.setText(f"No se pudo guardar la preferencia: {exc}")
                    return
                config.llm.ollama_model = selected
                self._ollama_model = selected
                self.ollama_model_requested.emit(selected)
                self._refresh_status_bar()
                self.statusBar().showMessage(f"Modelo local seleccionado: {selected}", 4000)
                if self._selected_mode == "local":
                    self._start_warmup_agent()
                dlg.accept()

            refresh_btn.clicked.connect(load_models)
            buttons.accepted.connect(save)
            buttons.rejected.connect(dlg.reject)
            load_models()
            dlg.open()

        def _open_qa_panel(self) -> None:
            from PySide6.QtCore import QObject as _QObject
            from PySide6.QtCore import Qt as _Qt
            from PySide6.QtCore import Signal as _Signal
            from PySide6.QtCore import Slot as _Slot
            from PySide6.QtWidgets import QDialog, QDialogButtonBox

            class _QAWorker(_QObject):
                loaded = _Signal(object)

                def run(self) -> None:
                    from adv_archon.desktop.qa import run_qa_checks

                    self.loaded.emit(run_qa_checks(config))

            class _QAReceiver(_QObject):
                @_Slot(object)
                def loaded(self, items: object) -> None:
                    on_loaded(items)

            dlg = QDialog(self)
            self._qa_dialog = dlg
            dlg.setWindowTitle("QA de permisos — ADV ARCHON")
            dlg.setMinimumWidth(560)
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(10)

            title = QLabel("QA de voz, Ollama y visión")
            title.setObjectName("AppName")
            layout.addWidget(title)
            intro = QLabel(
                "Comprueba micrófono, Ollama, modelo local, visión local y pantalla."
            )
            intro.setObjectName("Sub")
            intro.setWordWrap(True)
            layout.addWidget(intro)

            results = QVBoxLayout()
            results.setSpacing(6)
            layout.addLayout(results)

            status = QLabel("Ejecutando comprobaciones…")
            status.setObjectName("Faint")
            layout.addWidget(status)

            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            retry_btn = QPushButton("Volver a comprobar")
            retry_btn.setObjectName("Primary")
            buttons.addButton(retry_btn, QDialogButtonBox.ButtonRole.ActionRole)
            buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
            buttons.rejected.connect(dlg.reject)
            layout.addWidget(buttons)

            def clear_rows() -> None:
                while results.count():
                    item = results.takeAt(0)
                    if item and item.widget():
                        item.widget().deleteLater()

            def add_row(item: object) -> None:
                row = QFrame()
                row.setObjectName("Card")
                rl = QVBoxLayout(row)
                rl.setContentsMargins(10, 8, 10, 8)
                name = getattr(item, "nombre", "Check")
                ok = bool(getattr(item, "ok", False))
                detail = str(getattr(item, "detalle", ""))
                action = str(getattr(item, "accion", ""))
                head = QLabel(f"● {name}")
                head.setStyleSheet(f"color:{OK if ok else WARN};font-weight:700;")
                rl.addWidget(head)
                body = QLabel(detail + (f"\n{action}" if action and not ok else ""))
                body.setObjectName("Sub")
                body.setWordWrap(True)
                rl.addWidget(body)
                results.addWidget(row)

            def on_loaded(items: object) -> None:
                clear_rows()
                qa_items = items if isinstance(items, list) else []
                for item in qa_items:
                    add_row(item)
                failed = sum(1 for item in qa_items if not bool(getattr(item, "ok", False)))
                status.setText(
                    "Todo listo para voz local." if failed == 0
                    else f"{failed} punto(s) requieren atención."
                )
                self._qa_runner_ref = None

            def run() -> None:
                clear_rows()
                status.setText("Ejecutando comprobaciones…")
                thread = QThread(dlg)
                thread.setObjectName("adv-archon-qa")
                worker = _QAWorker()
                receiver = _QAReceiver(dlg)
                worker.moveToThread(thread)
                thread.started.connect(worker.run)
                worker.loaded.connect(receiver.loaded, _Qt.ConnectionType.QueuedConnection)
                worker.loaded.connect(worker.deleteLater)
                worker.loaded.connect(thread.quit)
                thread.finished.connect(thread.deleteLater)
                self._qa_runner_ref = (thread, worker, receiver)
                thread.start()

            retry_btn.clicked.connect(run)
            run()
            dlg.open()

        # ── Warmup agent (Phase 7B) ───────────────────────────────────────────
        def _start_warmup_agent(self) -> None:
            if self._selected_mode != "local":
                return
            if self._warmup_agent_ref is not None:
                _agent, thread = self._warmup_agent_ref
                if thread is not None and thread.isRunning():
                    self._handle_warmup_progress("Ollama ya se está verificando…")
                    return
                self._warmup_agent_ref = None
            try:
                from adv_archon.desktop.warmup_agent import start_warmup_agent

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
                _agent, thread = ref
                thread.finished.connect(self._clear_warmup_agent_ref)
            except Exception:
                pass  # warmup is optional; never block startup

        def _clear_warmup_agent_ref(self) -> None:
            self._warmup_agent_ref = None

        def _handle_warmup_progress(self, message: str) -> None:
            self._ollama_state = "Cargando…"
            self._refresh_status_bar()
            self.statusBar().showMessage(message, 3500)

        def _handle_warmup_model_found(self, model_name: str) -> None:
            self._ollama_model = model_name
            self._refresh_status_bar()

        def _handle_warmup_ready(self, elapsed: float) -> None:
            self._ollama_state = "Listo"
            self._refresh_status_bar()
            self.statusBar().showMessage(f"Modelo local listo en {elapsed:.1f}s", 4000)

        def _handle_warmup_failed(self, error: str) -> None:
            self._ollama_state = "Sin conexión"
            self._refresh_status_bar()
            self.statusBar().showMessage(f"Modelo no cargado: {error}", 6000)

        def _maybe_show_onboarding(self) -> None:
            if self._onboarding_done():
                return
            from PySide6.QtWidgets import QDialog as _QDialog

            dlg = _QDialog(self)
            dlg.setWindowTitle("Bienvenido a ADV ARCHON")
            dlg.setMinimumWidth(460)
            layout = QVBoxLayout(dlg)
            layout.addWidget(self._make_logo(72), alignment=Qt.AlignmentFlag.AlignCenter)
            title = QLabel("Bienvenido a ADV ARCHON")
            title.setObjectName("AppName")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title)
            body = QLabel("")
            body.setWordWrap(True)
            body.setObjectName("Sub")
            layout.addWidget(body)
            actions = QHBoxLayout()
            skip_btn = QPushButton("Omitir")
            skip_btn.setObjectName("Ghost")
            verify_btn = QPushButton("Verificar ahora")
            next_btn = QPushButton("Siguiente")
            next_btn.setObjectName("Primary")
            actions.addWidget(skip_btn)
            actions.addStretch()
            actions.addWidget(verify_btn)
            actions.addWidget(next_btn)
            layout.addLayout(actions)

            steps = [
                (
                    "ADV ARCHON para expedientes urbanísticos",
                    "Piensa en ADV ARCHON como una mesa de revisión preliminar para "
                    "despacho: abres un expediente, indicas la parcela, adjuntas el "
                    "plano y recibes un informe PDF con fuentes y advertencias.\n\n"
                    "No necesitas usar terminal ni escribir prompts para empezar.",
                ),
                (
                    "Motor local y privacidad",
                    "El análisis se ejecuta local-first con Ollama. Si el modelo no está "
                    "cargado, la app sigue siendo usable: puedes crear expedientes, ver "
                    "Catastro, afecciones y exportar contexto preliminar.\n\n"
                    "Pulsa “Verificar ahora” solo si quieres comprobar Ollama en este momento.",
                ),
                (
                    "Flujo recomendado para probarla",
                    "1. Crea un expediente o abre “Modo demo”.\n"
                    "2. Introduce dirección, coordenadas o referencia catastral.\n"
                    "3. Adjunta un PDF de plano.\n"
                    "4. Pulsa “Analizar con PGOU”.\n"
                    "5. Exporta el informe PDF.\n\n"
                    "Esto es lo que debería poder hacer un arquitecto sin ayuda.",
                ),
                (
                    "Qué significa el resultado",
                    "ADV ARCHON no emite una licencia ni sustituye criterio técnico. "
                    "Te da un cribado preliminar: viable, condicionado o revisar, con "
                    "fuentes oficiales, notas jurídicas y próximos pasos.\n\n"
                    f"{__beta_label__}: prueba recomendada en 10-15 minutos.",
                ),
            ]
            state = {"idx": 0}

            def render_step() -> None:
                heading, copy = steps[state["idx"]]
                title.setText(heading)
                body.setText(copy)
                verify_btn.setVisible(state["idx"] == 1)
                is_last = state["idx"] == len(steps) - 1
                next_btn.setText("Crear expediente" if is_last else "Siguiente")

            def finish(*, open_expedientes: bool = False) -> None:
                self._mark_onboarding_done()
                dlg.accept()
                if open_expedientes:
                    QTimer.singleShot(150, lambda: self._open_expedientes(open_new=True))

            def advance() -> None:
                if state["idx"] >= len(steps) - 1:
                    finish(open_expedientes=True)
                    return
                state["idx"] += 1
                render_step()

            skip_btn.clicked.connect(lambda: finish(open_expedientes=False))
            verify_btn.clicked.connect(lambda _checked=False: self._start_warmup_agent())
            next_btn.clicked.connect(advance)
            dlg.finished.connect(lambda _code: setattr(self, "_onboarding_dialog", None))
            self._onboarding_dialog = dlg
            render_step()
            dlg.open()

        def _show_beta_guide(self) -> None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                f"Guía de prueba — ADV ARCHON {__beta_label__}",
                "Prueba recomendada para un despacho:\n\n"
                "1. Abre Expedientes y crea un expediente nuevo.\n"
                "2. Introduce dirección, coordenadas o referencia catastral.\n"
                "3. Adjunta un plano PDF si tienes uno de prueba.\n"
                "4. Pulsa Analizar y revisa el veredicto preliminar.\n"
                "5. Exporta el informe PDF.\n\n"
                "Feedback útil:\n"
                "- ¿Entiendes el flujo sin explicación?\n"
                "- ¿El informe parece presentable ante un cliente interno?\n"
                "- ¿Qué dato falta para confiar en la revisión?\n"
                "- ¿Qué parte te hizo dudar o se sintió demasiado técnica?\n\n"
                "Aviso: esta beta es preliminar y no sustituye comprobación oficial "
                "ni criterio profesional.",
            )

        def _close_workspace_panels(self) -> None:
            for attr in (
                "_expedientes_dialog",
                "_studio_demo_dialog",
                "_client_license_dialog",
                "_studio_pack_dialog",
            ):
                dlg = getattr(self, attr, None)
                if dlg is not None:
                    with suppress(RuntimeError):
                        dlg.close()
                    setattr(self, attr, None)

        def _show_chat_home(self) -> None:
            was_chat = self._active_nav_context == "chat"
            self._close_workspace_panels()
            if self._home_visible or not was_chat:
                self._clear_message_area()
                self._home_visible = False
                self._append_system(
                    "Chat contextual listo. Abre un expediente para que ARCHON use "
                    "su parcela, municipio, PGOU y afecciones en la respuesta."
                )
            self._set_nav_context("chat")
            self._input.setFocus()
            self.statusBar().showMessage("Chat principal listo.", 2500)

        def _studio_data_dir(self) -> Path:
            import os

            data_dir = Path(os.getenv("ADV_ARCHON_HOME", str(Path.home() / ".adv-archon")))
            data_dir.mkdir(parents=True, exist_ok=True)
            return data_dir

        def _open_client_license(self) -> None:
            from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit

            from adv_archon.core.studio import (
                load_studio_client_config,
                save_default_studio_client_config,
                save_studio_client_config,
                studio_client_config_path,
            )

            self._close_workspace_panels()
            data_dir = self._studio_data_dir()
            save_default_studio_client_config(data_dir)
            client_cfg = load_studio_client_config(data_dir)

            dlg = QDialog(self)
            dlg.setWindowTitle("Cliente / Licencia — ADV ARCHON Studio")
            dlg.setMinimumSize(720, 580)
            dlg.setWindowModality(Qt.WindowModality.NonModal)

            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(12)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QVBoxLayout(hero)
            hero_lay.setContentsMargins(16, 14, 16, 14)
            hero_lay.setSpacing(6)
            eyebrow = QLabel("STUDIO EDITION")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Cliente / Licencia")
            title.setObjectName("StudioTitle")
            subtitle = QLabel(
                "Personaliza ADV ARCHON para que cada informe parezca preparado "
                "para un despacho real: nombre, logo, municipios y estado de licencia."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            hero_lay.addWidget(eyebrow)
            hero_lay.addWidget(title)
            hero_lay.addWidget(subtitle)
            layout.addWidget(hero)

            form = QFrame()
            form.setObjectName("Panel")
            form_lay = QVBoxLayout(form)
            form_lay.setContentsMargins(16, 14, 16, 14)
            form_lay.setSpacing(10)

            name_lbl = QLabel("Nombre del despacho")
            name_lbl.setObjectName("Eyebrow")
            name_input = QLineEdit(client_cfg.client_name)
            form_lay.addWidget(name_lbl)
            form_lay.addWidget(name_input)

            logo_lbl = QLabel("Logo del despacho")
            logo_lbl.setObjectName("Eyebrow")
            logo_row = QHBoxLayout()
            logo_input = QLineEdit(client_cfg.logo_path)
            logo_btn = QPushButton("Elegir logo…")
            logo_btn.setObjectName("Ghost")
            logo_row.addWidget(logo_input, 1)
            logo_row.addWidget(logo_btn)
            logo_preview = QLabel("")
            logo_preview.setObjectName("Sub")
            logo_preview.setFixedHeight(42)
            logo_preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            form_lay.addWidget(logo_lbl)
            form_lay.addLayout(logo_row)
            form_lay.addWidget(logo_preview)

            municipalities_lbl = QLabel("Municipios incluidos")
            municipalities_lbl.setObjectName("Eyebrow")
            municipalities_input = QPlainTextEdit()
            municipalities_input.setPlainText("\n".join(client_cfg.included_municipalities))
            municipalities_input.setFixedHeight(86)
            form_lay.addWidget(municipalities_lbl)
            form_lay.addWidget(municipalities_input)

            license_row = QHBoxLayout()
            license_box = QVBoxLayout()
            license_lbl = QLabel("Estado de licencia")
            license_lbl.setObjectName("Eyebrow")
            status_combo = QComboBox()
            status_options = [
                ("Beta privada", "beta_privada"),
                ("Piloto de despacho", "piloto_despacho"),
                ("Activa", "activa"),
                ("Pendiente de activar", "pendiente_activar"),
            ]
            for label, value in status_options:
                status_combo.addItem(label, value)
            idx = status_combo.findData(client_cfg.license_status)
            if idx >= 0:
                status_combo.setCurrentIndex(idx)
            license_box.addWidget(license_lbl)
            license_box.addWidget(status_combo)

            label_box = QVBoxLayout()
            license_label_lbl = QLabel("Etiqueta visible")
            license_label_lbl.setObjectName("Eyebrow")
            license_label_input = QLineEdit(client_cfg.license_label)
            label_box.addWidget(license_label_lbl)
            label_box.addWidget(license_label_input)
            license_row.addLayout(license_box, 1)
            license_row.addLayout(label_box, 1)
            form_lay.addLayout(license_row)

            config_path_lbl = QLabel(
                f"Archivo local: {studio_client_config_path(data_dir)}"
            )
            config_path_lbl.setObjectName("Faint")
            config_path_lbl.setWordWrap(True)
            form_lay.addWidget(config_path_lbl)
            layout.addWidget(form, 1)

            status_lbl = QLabel("")
            status_lbl.setObjectName("Sub")
            status_lbl.setWordWrap(True)
            layout.addWidget(status_lbl)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save
                | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cerrar")
            layout.addWidget(buttons)

            def update_logo_preview() -> None:
                path = Path(logo_input.text().strip()).expanduser()
                if not path.exists() or not path.is_file():
                    logo_preview.setPixmap(QPixmap())
                    logo_preview.setText("Sin logo de cliente. El informe usará solo ADV ARCHON.")
                    return
                pixmap = QPixmap(str(path))
                if pixmap.isNull():
                    logo_preview.setPixmap(QPixmap())
                    logo_preview.setText("No se pudo leer el logo seleccionado.")
                    return
                logo_preview.setText("")
                logo_preview.setPixmap(
                    pixmap.scaled(
                        120,
                        38,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            def choose_logo() -> None:
                selected, _filter = QFileDialog.getOpenFileName(
                    dlg,
                    "Elegir logo del despacho",
                    str(Path.home()),
                    "Imágenes (*.png *.jpg *.jpeg *.webp)",
                )
                if selected:
                    logo_input.setText(selected)
                    update_logo_preview()

            def municipalities() -> list[str]:
                raw = municipalities_input.toPlainText().replace(",", "\n")
                return [item.strip() for item in raw.splitlines() if item.strip()]

            def save() -> None:
                try:
                    save_studio_client_config(
                        client_name=name_input.text(),
                        logo_path=logo_input.text(),
                        included_municipalities=municipalities(),
                        license_status=str(status_combo.currentData() or ""),
                        license_label=license_label_input.text(),
                        root=data_dir,
                    )
                except Exception as exc:
                    status_lbl.setText(f"No se pudo guardar la configuración: {exc}")
                    return
                status_lbl.setText(
                    "Configuración guardada. Los próximos informes PDF usarán estos datos."
                )
                self.statusBar().showMessage(
                    "Cliente / Licencia actualizado para Studio Edition.", 5000
                )

            logo_btn.clicked.connect(choose_logo)
            logo_input.textChanged.connect(lambda _text: update_logo_preview())
            buttons.accepted.connect(save)
            buttons.rejected.connect(dlg.close)
            dlg.finished.connect(lambda _code: setattr(self, "_client_license_dialog", None))
            self._client_license_dialog = dlg
            update_logo_preview()
            dlg.show()

        def _open_studio_pack(self) -> None:
            from PySide6.QtWidgets import QDialog

            self._close_workspace_panels()
            dlg = QDialog(self)
            dlg.setWindowTitle("Pack Studio — ADV ARCHON")
            dlg.setMinimumSize(860, 560)
            dlg.setWindowModality(Qt.WindowModality.NonModal)

            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(12)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QVBoxLayout(hero)
            hero_lay.setContentsMargins(18, 16, 18, 16)
            hero_lay.setSpacing(6)
            eyebrow = QLabel("ADV ARCHON STUDIO")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Paquete profesional para despacho")
            title.setObjectName("StudioTitle")
            subtitle = QLabel(
                "Una forma cerrada y demostrable de presentar ADV ARCHON como "
                "infraestructura local de revisión urbanística preliminar."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            hero_lay.addWidget(eyebrow)
            hero_lay.addWidget(title)
            hero_lay.addWidget(subtitle)
            layout.addWidget(hero)

            cards = QHBoxLayout()
            cards.setSpacing(12)
            sections = [
                (
                    "Instalación local",
                    "ADV ARCHON.app configurado en el equipo del despacho, con motor "
                    "local, privacidad y flujo de expedientes preparado.",
                ),
                (
                    "Municipios configurados",
                    "Paquete inicial de municipios incluidos, con estado validado, "
                    "preliminar o pendiente según la curación normativa disponible.",
                ),
                (
                    "Expedientes demo",
                    "Casos de prueba del propio despacho o ejemplos guiados para formar "
                    "criterio interno antes de usar expedientes reales.",
                ),
            ]
            for heading, copy in sections:
                card = QFrame()
                card.setObjectName("StudioCard")
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(14, 14, 14, 14)
                card_lay.setSpacing(8)
                h = QLabel(heading)
                h.setObjectName("StudioCase")
                body = QLabel(copy)
                body.setObjectName("Sub")
                body.setWordWrap(True)
                card_lay.addWidget(h)
                card_lay.addWidget(body)
                card_lay.addStretch(1)
                cards.addWidget(card)
            layout.addLayout(cards, 1)

            scope = QFrame()
            scope.setObjectName("Panel")
            scope_lay = QVBoxLayout(scope)
            scope_lay.setContentsMargins(16, 14, 16, 14)
            scope_lay.setSpacing(6)
            scope_title = QLabel("Alcance del paquete")
            scope_title.setObjectName("StudioCase")
            scope_lay.addWidget(scope_title)
            items = [
                "Instalación local en el despacho.",
                "Municipios incluidos y etiquetados por estado de validación.",
                "Expedientes demo configurados para enseñar el flujo completo.",
                "Plantilla PDF personalizada con nombre y logo del cliente.",
                "Soporte beta privado durante la implantación inicial.",
                "Actualizaciones de producto durante el periodo contratado.",
            ]
            for item in items:
                lbl = QLabel(f"• {item}")
                lbl.setObjectName("Sub")
                lbl.setWordWrap(True)
                scope_lay.addWidget(lbl)
            layout.addWidget(scope)

            close_btn = QPushButton("Cerrar")
            close_btn.setObjectName("Primary")
            close_btn.clicked.connect(dlg.close)
            layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
            dlg.finished.connect(lambda _code: setattr(self, "_studio_pack_dialog", None))
            self._studio_pack_dialog = dlg
            dlg.show()

        def _open_studio_demo(self) -> None:
            import os

            from PySide6.QtWidgets import QDialog

            from adv_archon.core.demo import create_studio_demo_expedientes
            from adv_archon.core.expediente import ExpedienteStore
            from adv_archon.core.studio import (
                build_studio_payload,
                load_studio_client_config,
                save_default_studio_client_config,
            )

            self._close_workspace_panels()
            data_dir = Path(os.getenv("ADV_ARCHON_HOME", str(Path.home() / ".adv-archon")))
            data_dir.mkdir(parents=True, exist_ok=True)
            save_default_studio_client_config(data_dir)
            client_cfg = load_studio_client_config(data_dir)
            store = ExpedienteStore(data_dir / "expedientes.db")

            dlg = QDialog(self)
            dlg.setWindowTitle("Studio Demo — ADV ARCHON")
            dlg.setMinimumSize(980, 640)
            dlg.setWindowModality(Qt.WindowModality.NonModal)

            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(12)

            hero = QFrame()
            hero.setObjectName("StudioHero")
            hero_lay = QHBoxLayout(hero)
            hero_lay.setContentsMargins(18, 16, 18, 16)
            hero_lay.setSpacing(14)
            hero_lay.addWidget(self._make_logo(58))

            hero_text = QVBoxLayout()
            eyebrow = QLabel("ADV ARCHON STUDIO EDITION")
            eyebrow.setObjectName("Eyebrow")
            title = QLabel("Demo comercial guiada de 10 minutos")
            title.setObjectName("StudioTitle")
            subtitle = QLabel(
                "Tres expedientes preparados para enseñar valor: decisión, horas "
                "ahorradas, riesgos, fuentes oficiales e informe listo para abrir."
            )
            subtitle.setObjectName("Sub")
            subtitle.setWordWrap(True)
            client = QLabel(
                f"Preparado para: {client_cfg.client_name} · "
                f"{client_cfg.license_label} · "
                f"{', '.join(client_cfg.included_municipalities)}"
            )
            client.setObjectName("Accent")
            client.setWordWrap(True)
            hero_text.addWidget(eyebrow)
            hero_text.addWidget(title)
            hero_text.addWidget(subtitle)
            hero_text.addWidget(client)
            hero_lay.addLayout(hero_text, 1)

            start_btn = QPushButton("Iniciar demo comercial")
            start_btn.setObjectName("Primary")
            start_btn.setMinimumWidth(190)
            hero_lay.addWidget(start_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(hero)

            status_lbl = QLabel(
                "Pulsa iniciar para generar los tres casos demo y sus informes PDF. "
                "La demo no bloquea el chat principal."
            )
            status_lbl.setObjectName("Sub")
            status_lbl.setWordWrap(True)
            layout.addWidget(status_lbl)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            cards_host = QWidget()
            cards_lay = QHBoxLayout(cards_host)
            cards_lay.setContentsMargins(0, 0, 0, 0)
            cards_lay.setSpacing(12)
            scroll.setWidget(cards_host)
            layout.addWidget(scroll, 1)

            def clear_cards() -> None:
                while cards_lay.count():
                    item = cards_lay.takeAt(0)
                    widget = item.widget()
                    if widget is not None:
                        widget.deleteLater()

            def metric(label: str, value: str) -> QFrame:
                box = QFrame()
                box.setObjectName("StudioMetric")
                box_lay = QVBoxLayout(box)
                box_lay.setContentsMargins(10, 8, 10, 8)
                box_lay.setSpacing(2)
                value_lbl = QLabel(value)
                value_lbl.setObjectName("StudioDecision")
                label_lbl = QLabel(label)
                label_lbl.setObjectName("Faint")
                label_lbl.setWordWrap(True)
                box_lay.addWidget(value_lbl)
                box_lay.addWidget(label_lbl)
                return box

            def open_report(path_text: str) -> None:
                path = Path(path_text)
                if path.exists():
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                else:
                    status_lbl.setText("El informe no existe todavía. Regenera la demo.")

            def open_expediente(exp_id: str) -> None:
                dlg.close()
                QTimer.singleShot(80, lambda: self._open_expedientes(selected_id=exp_id))

            def loads_json(raw: object) -> dict[str, Any]:
                if not isinstance(raw, str) or not raw.strip():
                    return {}
                try:
                    parsed = json.loads(raw)
                except ValueError:
                    return {}
                return parsed if isinstance(parsed, dict) else {}

            def make_card(exp: object) -> QFrame:
                site_context = loads_json(getattr(exp, "site_context", ""))
                analysis = loads_json(getattr(exp, "analysis_result", ""))
                studio = build_studio_payload(
                    case_type=getattr(exp, "case_type", ""),
                    municipality=getattr(exp, "municipality", ""),
                    site_context=site_context,
                    analysis=analysis,
                )
                value = studio.get("estimated_value") or {}
                city = studio.get("city_pack") or {}

                card = QFrame()
                card.setObjectName("StudioCard")
                card.setMinimumWidth(280)
                card_lay = QVBoxLayout(card)
                card_lay.setContentsMargins(14, 14, 14, 14)
                card_lay.setSpacing(10)

                decision = QLabel(str(studio.get("decision") or "REVISAR"))
                decision.setObjectName("StudioDecision")
                card_lay.addWidget(decision)

                name = QLabel(str(studio.get("case_label") or getattr(exp, "title", "")))
                name.setObjectName("StudioCase")
                name.setWordWrap(True)
                card_lay.addWidget(name)

                focus = QLabel(str(studio.get("decision_focus") or ""))
                focus.setObjectName("Sub")
                focus.setWordWrap(True)
                card_lay.addWidget(focus)

                metrics_row_1 = QHBoxLayout()
                metrics_row_1.setSpacing(8)
                metrics_row_1.addWidget(
                    metric("horas ahorradas", str(value.get("hours_saved", 0)))
                )
                metrics_row_1.addWidget(metric("riesgos", str(value.get("risks_detected", 0))))
                card_lay.addLayout(metrics_row_1)

                metrics_row_2 = QHBoxLayout()
                metrics_row_2.setSpacing(8)
                metrics_row_2.addWidget(metric("fuentes", str(value.get("sources_consulted", 0))))
                metrics_row_2.addWidget(
                    metric("documentos", str(value.get("documents_generated", 0)))
                )
                card_lay.addLayout(metrics_row_2)

                pack = QLabel(
                    f"{city.get('label', 'Paquete municipal')} · "
                    f"estado {city.get('status', 'pendiente')} · "
                    f"act. {city.get('last_updated', '—')}"
                )
                pack.setObjectName("Faint")
                pack.setWordWrap(True)
                card_lay.addWidget(pack)
                card_lay.addStretch(1)

                buttons = QHBoxLayout()
                buttons.setSpacing(8)
                report_path = str(getattr(exp, "report_path", ""))
                exp_id = str(getattr(exp, "id", ""))
                report_btn = QPushButton("Abrir informe")
                report_btn.setObjectName("Primary")
                report_btn.clicked.connect(
                    lambda _checked=False, path=report_path: open_report(path)
                )
                exp_btn = QPushButton("Abrir expediente")
                exp_btn.setObjectName("Ghost")
                exp_btn.clicked.connect(
                    lambda _checked=False, eid=exp_id: open_expediente(eid)
                )
                buttons.addWidget(report_btn)
                buttons.addWidget(exp_btn)
                card_lay.addLayout(buttons)
                return card

            def start_demo() -> None:
                start_btn.setEnabled(False)
                start_btn.setText("Preparando…")
                status_lbl.setText("Generando expedientes demo e informes PDF…")
                try:
                    demos = create_studio_demo_expedientes(store, data_dir=data_dir)
                except Exception as exc:
                    status_lbl.setText(f"No se pudo crear la demo: {exc}")
                    start_btn.setEnabled(True)
                    start_btn.setText("Reintentar demo comercial")
                    return
                clear_cards()
                for exp in demos:
                    cards_lay.addWidget(make_card(exp))
                cards_lay.addStretch(1)
                if demos:
                    self._last_exp_label = demos[0].title
                    self._refresh_status_bar()
                self.statusBar().showMessage(
                    "Studio Demo lista: 3 casos comerciales y PDFs generados.", 5000
                )
                status_lbl.setText(
                    "Demo lista. Abre los informes o entra en cada expediente para "
                    "recorrer el flujo completo."
                )
                start_btn.setEnabled(True)
                start_btn.setText("Regenerar demo comercial")

            start_btn.clicked.connect(start_demo)
            dlg.finished.connect(lambda _code: setattr(self, "_studio_demo_dialog", None))
            self._studio_demo_dialog = dlg
            dlg.show()

        def _open_demo_expediente(self) -> None:
            self._open_studio_demo()

        def _onboarding_done(self) -> bool:
            try:
                data = json.loads(self._onboarding_config_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return False
            return bool(data.get("onboarding_done"))

        def _mark_onboarding_done(self) -> None:
            try:
                data = json.loads(self._onboarding_config_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            data["onboarding_done"] = True
            self._onboarding_config_path.parent.mkdir(parents=True, exist_ok=True)
            self._onboarding_config_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

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
                summary_snippet = text[:300].replace("\n", " ").strip()
                result = {
                    "summary": summary_snippet,
                    "annotations": [],
                    "full_analysis": text,
                }
                self._compliance.mark_done(result=result)
                self._refresh_compliance_ui()
                # Persist result to active expediente so Exportar works instantly
                if self._active_exp_store and self._active_exp_id:
                    try:
                        import dataclasses as _dc
                        import json as _json
                        exp = self._active_exp_store.get(self._active_exp_id)
                        if exp:
                            quality = result.get("quality")
                            quality_score = None
                            quality_result = ""
                            if isinstance(quality, dict):
                                raw_score = quality.get("score")
                                if isinstance(raw_score, int):
                                    quality_score = raw_score
                                quality_result = _json.dumps(quality, ensure_ascii=False)
                            _ep = result.get("extracted_params") or {}
                            updated = _dc.replace(
                                exp,
                                analysis_result=_json.dumps(result, ensure_ascii=False),
                                quality_score=quality_score,
                                quality_result=quality_result,
                                extracted_params=_json.dumps(_ep, ensure_ascii=False) if _ep else "",  # noqa: E501
                                status="analizado",
                            )
                            self._active_exp_store.update(updated)
                    except Exception:
                        pass
                    finally:
                        self._active_exp_id = ""
                        self._active_exp_store = None

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

        # ── PGOU import ───────────────────────────────────────────────────────
        def _open_pgou_import(self) -> None:
            if not self._busy_state.backend_ready:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "ADV ARCHON",
                    "El motor de IA todavía no está listo. Espera unos segundos.",
                )
                return
            from adv_archon.desktop.pgou_import_dialog import open_pgou_import_dialog
            runtime = self._backend_worker._runtime  # noqa: SLF001
            if runtime is None:
                return
            open_pgou_import_dialog(runtime.knowledge_store, parent=self)

        # ── Dashboard ────────────────────────────────────────────────────────
        def _open_dashboard(self) -> None:
            import os

            from PySide6.QtWidgets import QDialog
            from PySide6.QtWidgets import QVBoxLayout as _QVBoxLayout

            from adv_archon.core.expediente import ExpedienteStore
            from adv_archon.desktop.dashboard import ExpedientesDashboard

            data_dir = Path(os.getenv("ADV_ARCHON_HOME", str(Path.home() / ".adv-archon")))
            data_dir.mkdir(parents=True, exist_ok=True)
            store = ExpedienteStore(data_dir / "expedientes.db")

            dlg = QDialog(self)
            dlg.setWindowTitle("Dashboard — ADV ARCHON")
            dlg.resize(980, 680)
            from PySide6.QtCore import Qt as _Qt
            dlg.setWindowModality(_Qt.WindowModality.WindowModal)

            lay = _QVBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)

            board = ExpedientesDashboard()
            board.refresh(store)

            def _on_selected(eid: str) -> None:
                exp = store.get(eid)
                if exp:
                    self._set_active_expediente(exp)
                dlg.accept()
                # Open the full expediente dialog pre-selected
                QTimer.singleShot(80, self._open_expedientes)

            board.expediente_selected.connect(_on_selected)
            board.new_requested.connect(dlg.accept)
            board.new_requested.connect(
                lambda: QTimer.singleShot(
                    80, lambda: self._open_expedientes(open_new=True)
                )
            )

            lay.addWidget(board)
            dlg.exec()

        # ── Expedientes panel ─────────────────────────────────────────────────
        def _open_expedientes(
            self,
            selected_id: str | None = None,
            *,
            open_new: bool = False,
        ) -> None:
            import dataclasses
            import json
            import os
            import re
            from datetime import datetime

            from PySide6.QtCore import QObject, QThread
            from PySide6.QtCore import Signal as _Signal
            from PySide6.QtWidgets import (
                QDialog,
                QFrame,
                QInputDialog,
            )
            from PySide6.QtWidgets import (
                QHBoxLayout as _QHBoxLayout,
            )

            from adv_archon.core.document_store import DocumentStore
            from adv_archon.core.expediente import Expediente, ExpedienteStore
            from adv_archon.desktop.expediente_panel import (
                ExpedienteDetailPanel,
                ExpedienteListPanel,
                NewExpedienteDialog,
            )

            self._close_workspace_panels()

            data_dir = Path(os.getenv("ADV_ARCHON_HOME", str(Path.home() / ".adv-archon")))
            data_dir.mkdir(parents=True, exist_ok=True)
            store = ExpedienteStore(data_dir / "expedientes.db")
            document_store = DocumentStore(data_dir / "documents.db")
            runtime = getattr(self._backend_worker, "_runtime", None)
            if runtime is not None:
                for attr in (
                    "memoria_tools",
                    "memoria_pdf_tools",
                    "informe_tools",
                    "team_tools",
                ):
                    tool = getattr(runtime, attr, None)
                    if tool is not None and hasattr(tool, "set_expediente_store"):
                        with suppress(Exception):
                            tool.set_expediente_store(store)

            def _parse_coordinate_text(text: str) -> tuple[float, float] | None:
                match = re.search(
                    r"(-?\d+(?:\.\d+)?)\s*[,; ]\s*(-?\d+(?:\.\d+)?)",
                    text,
                )
                if not match:
                    return None
                lat = float(match.group(1))
                lon = float(match.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
                return None

            def _parse_cadastral_ref_text(text: str) -> str:
                normalized = re.sub(r"\s+", "", text).upper()
                return normalized if re.fullmatch(r"[A-Z0-9]{14,20}", normalized) else ""

            def _build_expediente_analysis(exp: Expediente) -> dict[str, Any]:
                from adv_archon.core.studio import get_case_template

                template = get_case_template(getattr(exp, "case_type", ""))
                try:
                    ctx = json.loads(exp.site_context) if exp.site_context else {}
                except (TypeError, ValueError):
                    ctx = {}
                checks = ctx.get("legal_checks") if isinstance(ctx, dict) else []
                checks = checks if isinstance(checks, list) else []
                statuses = {
                    str(check.get("status") or "")
                    for check in checks
                    if isinstance(check, dict)
                }
                if not checks:
                    verdict = "revisar"
                    verdict_label = "REVISAR"
                    summary = (
                        "El expediente no tiene todavía un contexto legal completo. "
                        "Debe resolverse la parcela y las fuentes sectoriales antes de "
                        "emitir un criterio preliminar."
                    )
                elif {"pending_review", "missing"} & statuses:
                    verdict = "revisar"
                    verdict_label = "REVISAR"
                    summary = (
                        "El expediente necesita revisión técnica antes de emitir criterio. "
                        "Hay datos pendientes o comprobaciones sectoriales que deben confirmarse."
                    )
                elif "conditional" in statuses:
                    verdict = "condicionado"
                    verdict_label = "CONDICIONADO"
                    summary = (
                        "El expediente es analizable, pero presenta afecciones o indicios "
                        "que condicionan la viabilidad y requieren contraste administrativo."
                    )
                else:
                    verdict = "viable"
                    verdict_label = "VIABLE"
                    summary = (
                        "No se detectan alertas sectoriales relevantes en el cribado preliminar. "
                        "La viabilidad queda sujeta a confirmar ordenanza y plano de proyecto."
                    )

                annotations: list[dict[str, str]] = []
                next_steps: list[str] = []
                status_map = {
                    "ready": "ok",
                    "not_applicable": "info",
                    "conditional": "warning",
                    "pending_review": "info",
                    "missing": "violation",
                }
                for check in checks:
                    if not isinstance(check, dict):
                        continue
                    status = str(check.get("status") or "")
                    title = str(check.get("title") or "")
                    detail = str(check.get("detail") or "")
                    action = str(check.get("recommended_action") or "")
                    annotations.append(
                        {
                            "status": status_map.get(status, "info"),
                            "description": f"{title}: {detail}".strip(": "),
                            "recommendation": action,
                        }
                    )
                    if status not in {"ready", "not_applicable"} and action:
                        next_steps.append(action)
                if exp.plan_path:
                    next_steps.append("Revisar el plano adjunto frente a la ordenanza aplicable.")
                for item in template.checklist:
                    if len(next_steps) >= 12:
                        break
                    next_steps.append(item)
                return {
                    "verdict": verdict,
                    "verdict_label": verdict_label,
                    "summary": f"{template.label}. {summary}",
                    "annotations": annotations[:30],
                    "next_steps": next_steps[:12],
                    "generated_at": datetime.now().isoformat(timespec="minutes"),
                }

            def _loads_agent_json(raw: str) -> dict[str, Any]:
                if not raw.strip():
                    return {}
                try:
                    parsed = json.loads(raw)
                except (TypeError, ValueError):
                    return {}
                return parsed if isinstance(parsed, dict) else {}

            # -- Background geo-resolver ----------------------------------------
            class _GeoWorker(QObject):
                resolved = _Signal(object)
                failed   = _Signal(str)

                def __init__(self, exp: Expediente, data_root: Path) -> None:
                    super().__init__()
                    self._exp = exp
                    self._data_root = data_root

                def run(self) -> None:
                    try:
                        from adv_archon.core.geo_store import GeoStore
                        from adv_archon.core.pgou_store import PGOUStore
                        from adv_archon.integrations import catastro as _catastro
                        from adv_archon.integrations import nominatim as _nominatim
                        from adv_archon.tools.geo_tools import GeoTools

                        coords = _parse_coordinate_text(self._exp.address)
                        if coords is None:
                            ref = _parse_cadastral_ref_text(self._exp.address)
                            if ref:
                                result = _catastro.get_coordinates_by_ref(ref)
                                if result.get("error"):
                                    self.failed.emit(str(result["error"]))
                                    return
                                lat = float(result.get("latitude", 0) or 0)
                                lon = float(result.get("longitude", 0) or 0)
                            else:
                                result = _nominatim.forward_geocode(self._exp.address)
                                if not result:
                                    self.failed.emit("Nominatim no encontró la dirección.")
                                    return
                                lat = float(result.get("lat", 0) or 0)
                                lon = float(result.get("lon", 0) or 0)
                        else:
                            lat, lon = coords

                        geo_tools = GeoTools(
                            GeoStore(self._data_root / "geo.db"),
                            PGOUStore(self._data_root / "pgou.db"),
                        )
                        site_result = geo_tools.site_compliance_context(lat, lon)
                        site_payload = dict(site_result.payload)
                        if not site_payload.get("ok"):
                            self.failed.emit(
                                str(
                                    site_payload.get("error")
                                    or "No se pudo resolver el contexto de parcela."
                                )
                            )
                            return
                        municipality = str(site_payload.get("municipality") or "")
                        province = str(site_payload.get("province") or "")
                        cadastral_ref = str(site_payload.get("cadastral_ref") or "")

                        if not cadastral_ref:
                            try:
                                cd = _catastro.get_cadastral_data(lat, lon)
                                cadastral_ref = cd.get("cadastral_ref", "") or ""
                            except Exception:
                                pass
                        site_ctx = json.dumps(site_payload, ensure_ascii=False)
                        updated = dataclasses.replace(
                            self._exp,
                            latitude=lat, longitude=lon,
                            municipality=municipality, province=province,
                            cadastral_ref=cadastral_ref,
                            site_context=site_ctx,
                            status="geocodificado",
                        )
                        self.resolved.emit(updated)
                    except Exception as exc:
                        self.failed.emit(str(exc))

            class _ExportWorker(QObject):
                exported = _Signal(str)
                failed = _Signal(str)
                finished = _Signal()

                def __init__(self, exp: Expediente, output_path: Path) -> None:
                    super().__init__()
                    self._exp = exp
                    self._output_path = output_path

                def run(self) -> None:
                    try:
                        from adv_archon.core.report_generator import generate_expediente_pdf

                        generate_expediente_pdf(
                            expediente=self._exp,
                            output_path=self._output_path,
                        )
                    except Exception as exc:
                        self.failed.emit(str(exc))
                    else:
                        self.exported.emit(str(self._output_path))
                    finally:
                        self.finished.emit()

            class _AgentReviewWorker(QObject):
                progress = _Signal(object, str)
                completed = _Signal(object)
                failed = _Signal(object, str)
                finished = _Signal()

                def __init__(self, exp: Expediente, data_root: Path) -> None:
                    super().__init__()
                    self._exp = exp
                    self._data_root = data_root
                    self._run_id = datetime.now().strftime("%Y%m%d%H%M%S")

                def run(self) -> None:
                    try:
                        from adv_archon.core.agent_plan import build_expediente_agent_plan
                        from adv_archon.core.expediente_autopilot import (
                            AutopilotStore,
                            append_autopilot_checkpoint,
                            build_expediente_autopilot,
                        )

                        initial_autopilot = build_expediente_autopilot(
                            self._exp,
                            office_memory_snapshot=self._office_memory_snapshot(),
                        )
                        AutopilotStore(self._data_root / "autopilot.db").save_run(
                            initial_autopilot,
                            run_id=self._run_id,
                        )
                        self._exp = dataclasses.replace(
                            self._exp,
                            status="autopilot_en_curso",
                            agent_history=append_autopilot_checkpoint(
                                getattr(self._exp, "agent_history", ""),
                                initial_autopilot,
                                run_id=self._run_id,
                            ),
                        )
                        self.progress.emit(self._exp, initial_autopilot.summary)

                        self._emit_event(
                            "resolve-location",
                            "Resolver parcela",
                            "in_progress",
                            "Autopilot está resolviendo parcela y coordenadas del expediente…",
                        )
                        if not self._ensure_site_context():
                            self._finish_with_current_plan()
                            return

                        self._emit_status_from_plan("resolve-location")
                        self._emit_status_from_plan("query-catastro")
                        self._emit_status_from_plan("sectorial-sources")
                        self._emit_status_from_plan("pgou-normativa")

                        plan_path = str(getattr(self._exp, "plan_path", "") or "").strip()
                        self._emit_event(
                            "plan-document",
                            "Revisar plano adjunto",
                            "completed" if plan_path else "needs_review",
                            (
                                "Plano localizado para contraste con PGOU."
                                if plan_path
                                else "No tengo plano; continuaré con Catastro y fuentes oficiales."
                            ),
                        )

                        if not str(getattr(self._exp, "analysis_result", "") or "").strip():
                            self._emit_event(
                                "preliminary-dictamen",
                                "Generar dictamen preliminar",
                                "in_progress",
                                "Generando dictamen preliminar a partir del contexto oficial…",
                            )
                            analysis = _build_expediente_analysis(self._exp)
                            next_status = (
                                "requiere_revision"
                                if analysis.get("verdict") == "revisar"
                                else "analizado"
                            )
                            self._exp = dataclasses.replace(
                                self._exp,
                                analysis_result=json.dumps(analysis, ensure_ascii=False),
                                status=next_status,
                            )
                        self._emit_status_from_plan("preliminary-dictamen")

                        plan = build_expediente_agent_plan(
                            self._exp,
                            include_history=False,
                            office_policy=self._office_policy(),
                        )
                        review_step = next(
                            (
                                step for step in plan.steps
                                if step.code == "architect-review"
                            ),
                            None,
                        )
                        self._emit_event(
                            "architect-review",
                            "Marcar puntos de arquitecto",
                            review_step.status if review_step else "needs_review",
                            (
                                review_step.recommended_action
                                if review_step
                                else "Arquitecto debe revisar el expediente."
                            ),
                        )

                        final_plan = build_expediente_agent_plan(
                            self._exp,
                            include_history=False,
                            office_policy=self._office_policy(),
                        )
                        final_status = (
                            "requiere_revision"
                            if final_plan.verdict in {"blocked", "review"}
                            else "analizado"
                        )
                        if getattr(self._exp, "report_path", ""):
                            final_status = getattr(self._exp, "status", "") or final_status
                        self._exp = dataclasses.replace(self._exp, status=final_status)
                        self._emit_event(
                            "agent-finish",
                            "Revisión completa",
                            "completed",
                            f"Resultado final del agente: {final_plan.verdict_label}.",
                        )
                        self.completed.emit(self._exp)
                    except Exception as exc:
                        self._exp = dataclasses.replace(
                            self._exp,
                            status="autopilot_bloqueado",
                        )
                        self._emit_event(
                            "agent-error",
                            "Revisión completa",
                            "blocked",
                            f"No se pudo completar la revisión guiada: {exc}",
                        )
                        self.failed.emit(self._exp, str(exc))
                    finally:
                        self.finished.emit()

                def _ensure_site_context(self) -> bool:
                    site_context = _loads_agent_json(
                        str(getattr(self._exp, "site_context", "") or "")
                    )
                    required_sources = (
                        "parcel_detail",
                        "flood_zone",
                        "natura2000",
                        "costas",
                        "carreteras",
                    )
                    has_full_context = bool(site_context) and all(
                        site_context.get(key) for key in required_sources
                    )
                    if has_full_context:
                        self._emit_event(
                            "resolve-location",
                            "Resolver parcela",
                            "completed",
                            "La parcela ya estaba resuelta en el expediente.",
                        )
                        return True

                    coords = _parse_coordinate_text(str(self._exp.address or ""))
                    if coords is None and self._exp.latitude and self._exp.longitude:
                        coords = (float(self._exp.latitude), float(self._exp.longitude))
                    if coords is None:
                        ref = _parse_cadastral_ref_text(str(self._exp.address or ""))
                        if ref:
                            self._emit_event(
                                "query-catastro",
                                "Consultar Catastro",
                                "in_progress",
                                "Consultando coordenadas por referencia catastral…",
                            )
                            from adv_archon.integrations import catastro as _catastro

                            result = _catastro.get_coordinates_by_ref(ref)
                            if result.get("error"):
                                self._emit_event(
                                    "query-catastro",
                                    "Consultar Catastro",
                                    "blocked",
                                    str(
                                        result.get("error")
                                        or "Catastro no resolvió la referencia."
                                    ),
                                )
                                return False
                            coords = (
                                float(result.get("latitude", 0) or 0),
                                float(result.get("longitude", 0) or 0),
                            )
                        elif str(self._exp.address or "").strip():
                            from adv_archon.integrations import nominatim as _nominatim

                            result = _nominatim.forward_geocode(self._exp.address)
                            if not result:
                                self._emit_event(
                                    "resolve-location",
                                    "Resolver parcela",
                                    "blocked",
                                    "No he podido resolver la dirección con Nominatim.",
                                )
                                return False
                            coords = (
                                float(result.get("lat", 0) or 0),
                                float(result.get("lon", 0) or 0),
                            )
                        else:
                            self._emit_event(
                                "resolve-location",
                                "Resolver parcela",
                                "blocked",
                                "Falta dirección, coordenadas o referencia catastral.",
                            )
                            return False

                    lat, lon = coords
                    self._emit_event(
                        "query-catastro",
                        "Consultar Catastro",
                        "in_progress",
                        "Consultando Catastro OVC y detalle parcelario…",
                    )
                    self._emit_event(
                        "sectorial-sources",
                        "Comprobar afecciones",
                        "in_progress",
                        "Comprobando SNCZI, Red Natura 2000, Costas y Carreteras…",
                    )
                    self._emit_event(
                        "pgou-normativa",
                        "Buscar normativa PGOU",
                        "in_progress",
                        "Buscando PGOU municipal y zonificación preliminar…",
                    )
                    from adv_archon.core.geo_store import GeoStore
                    from adv_archon.core.pgou_store import PGOUStore
                    from adv_archon.integrations import catastro as _catastro
                    from adv_archon.tools.geo_tools import GeoTools

                    geo_tools = GeoTools(
                        GeoStore(self._data_root / "geo.db"),
                        PGOUStore(self._data_root / "pgou.db"),
                    )
                    site_result = geo_tools.site_compliance_context(lat, lon)
                    site_payload = dict(site_result.payload)
                    if not site_payload.get("ok"):
                        self._emit_event(
                            "sectorial-sources",
                            "Comprobar afecciones",
                            "blocked",
                            str(
                                site_payload.get("error")
                                or "No se pudo resolver el contexto de parcela."
                            ),
                        )
                        return False
                    cadastral_ref = str(site_payload.get("cadastral_ref") or "")
                    if not cadastral_ref:
                        try:
                            cd = _catastro.get_cadastral_data(lat, lon)
                            cadastral_ref = cd.get("cadastral_ref", "") or ""
                        except Exception:
                            cadastral_ref = ""
                    self._exp = dataclasses.replace(
                        self._exp,
                        latitude=lat,
                        longitude=lon,
                        municipality=str(site_payload.get("municipality") or ""),
                        province=str(site_payload.get("province") or ""),
                        cadastral_ref=cadastral_ref,
                        site_context=json.dumps(site_payload, ensure_ascii=False),
                        status="geocodificado",
                    )
                    return True

                def _emit_status_from_plan(self, step_code: str) -> None:
                    from adv_archon.core.agent_plan import build_expediente_agent_plan

                    plan = build_expediente_agent_plan(
                        self._exp,
                        include_history=False,
                        office_policy=self._office_policy(),
                    )
                    step = next((item for item in plan.steps if item.code == step_code), None)
                    if step is None:
                        return
                    self._emit_event(
                        step.code,
                        step.title,
                        step.status,
                        step.recommended_action,
                    )

                def _finish_with_current_plan(self) -> None:
                    self._exp = dataclasses.replace(
                        self._exp,
                        status="autopilot_bloqueado",
                    )
                    self._emit_event(
                        "agent-finish",
                        "Revisión completa",
                        "blocked",
                        "La revisión guiada queda bloqueada hasta completar los datos mínimos.",
                    )
                    self.completed.emit(self._exp)

                def _emit_event(
                    self,
                    step_code: str,
                    title: str,
                    status: str,
                    message: str,
                ) -> None:
                    from adv_archon.core.agent_plan import append_agent_event

                    self._exp = dataclasses.replace(
                        self._exp,
                        agent_history=append_agent_event(
                            getattr(self._exp, "agent_history", ""),
                            step_code=step_code,
                            title=title,
                            status=status,
                            message=message,
                            run_id=self._run_id,
                        ),
                    )
                    self.progress.emit(self._exp, message)

                def _office_memory_snapshot(self) -> object:
                    from adv_archon.core.office_memory import OfficeMemoryStore

                    store = OfficeMemoryStore(self._data_root / "office_memory.db")
                    try:
                        return store.snapshot()
                    finally:
                        store.close()

                def _office_policy(self) -> object | None:
                    municipality = str(getattr(self._exp, "municipality", "") or "").strip()
                    if not municipality:
                        return None
                    snapshot = self._office_memory_snapshot()
                    return snapshot.policy_for(municipality)

            class _ExpedienteThreadBridge(QObject):
                geo_resolved = _Signal(object)
                geo_failed = _Signal(str)
                exported = _Signal(str)
                export_failed = _Signal(str)
                agent_progress = _Signal(object, str)
                agent_completed = _Signal(object)
                agent_failed = _Signal(object, str)

            _active_geo_threads: list[tuple[Any, Any]] = []
            _active_export_threads: list[tuple[Any, Any]] = []
            _active_agent_threads: list[tuple[Any, Any, Any]] = []

            def _launch_geo(exp: Expediente) -> None:
                detail_panel.set_operation_busy(
                    True,
                    "Resolviendo parcela y consultando fuentes oficiales…",
                )
                t = QThread(dlg)
                t.setObjectName("adv-archon-expediente-geo")
                w = _GeoWorker(exp, data_dir)
                bridge = _ExpedienteThreadBridge(dlg)
                w.moveToThread(t)
                t.started.connect(w.run)

                def _on_resolved(updated: Expediente) -> None:
                    store.update(updated)
                    list_panel.populate(store.list_all())
                    detail_panel.load_expediente(updated)
                    self._last_exp_label = updated.title
                    self._refresh_status_bar()
                    detail_panel.set_operation_busy(False)
                    t.quit()

                def _on_failed(msg: str) -> None:
                    self.statusBar().showMessage(f"No se pudo resolver el expediente: {msg}")
                    detail_panel.set_operation_busy(False)
                    t.quit()

                w.resolved.connect(bridge.geo_resolved)
                w.failed.connect(bridge.geo_failed)
                bridge.geo_resolved.connect(_on_resolved)
                bridge.geo_failed.connect(_on_failed)
                t.finished.connect(t.deleteLater)
                _active_geo_threads.append((t, w, bridge))
                t.start()

            # -- Dialog ----------------------------------------------------------
            dlg = QDialog(self)
            dlg.setWindowTitle("Expedientes — ADV ARCHON")
            dlg.resize(1100, 680)
            from PySide6.QtCore import Qt as _Qt
            dlg.setWindowModality(_Qt.WindowModality.NonModal)
            root_layout = QVBoxLayout(dlg)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            topbar = _QHBoxLayout()
            topbar.setContentsMargins(12, 10, 12, 10)
            topbar_title = QLabel("Expedientes")
            topbar_title.setObjectName("AppName")
            back_btn = QPushButton("Volver al chat")
            back_btn.setObjectName("Ghost")
            close_btn = QPushButton("Cerrar")
            close_btn.setObjectName("Ghost")
            topbar.addWidget(topbar_title)
            topbar.addStretch(1)
            topbar.addWidget(back_btn)
            topbar.addWidget(close_btn)
            root_layout.addLayout(topbar)

            dlg_layout = _QHBoxLayout()
            dlg_layout.setContentsMargins(0, 0, 0, 0)
            dlg_layout.setSpacing(0)
            root_layout.addLayout(dlg_layout, 1)
            back_btn.clicked.connect(self._show_chat_home)
            close_btn.clicked.connect(dlg.close)
            def _on_expedientes_finished(_code: int) -> None:
                self._expedientes_dialog = None
                with suppress(Exception):
                    document_store.close()

            dlg.finished.connect(_on_expedientes_finished)
            self._expedientes_dialog = dlg

            def _launch_agent_review(eid: str) -> None:
                exp = store.get(eid)
                if not exp:
                    return
                detail_panel.set_operation_busy(
                    True,
                    "ARCHON ejecutando Autopilot del expediente…",
                )
                self.statusBar().showMessage("ARCHON inicia Expediente Autopilot…")
                t = QThread(dlg)
                t.setObjectName("adv-archon-expediente-agent")
                w = _AgentReviewWorker(exp, data_dir)
                bridge = _ExpedienteThreadBridge(dlg)
                w.moveToThread(t)
                t.started.connect(w.run)

                def _on_agent_progress(updated: Expediente, message: str) -> None:
                    store.update(updated)
                    list_panel.populate(store.list_all())
                    detail_panel.load_expediente(updated)
                    self._last_exp_label = updated.title
                    self._refresh_status_bar()
                    self.statusBar().showMessage(message, 4000)

                def _on_agent_completed(updated: Expediente) -> None:
                    store.update(updated)
                    list_panel.populate(store.list_all())
                    detail_panel.load_expediente(updated)
                    detail_panel.set_operation_busy(False)
                    self._last_exp_label = updated.title
                    self._refresh_status_bar()
                    self.statusBar().showMessage(
                        "Expediente Autopilot completado por ARCHON.",
                        5000,
                    )
                    t.quit()

                def _on_agent_failed(updated: Expediente, message: str) -> None:
                    store.update(updated)
                    list_panel.populate(store.list_all())
                    detail_panel.load_expediente(updated)
                    detail_panel.set_operation_busy(False)
                    self.statusBar().showMessage(
                        f"No se pudo completar Autopilot: {message}",
                        6000,
                    )
                    t.quit()

                def _cleanup_agent_thread() -> None:
                    with suppress(ValueError):
                        _active_agent_threads.remove((t, w, bridge))

                w.progress.connect(bridge.agent_progress)
                w.completed.connect(bridge.agent_completed)
                w.failed.connect(bridge.agent_failed)
                w.finished.connect(w.deleteLater)
                w.finished.connect(t.quit)
                bridge.agent_progress.connect(_on_agent_progress)
                bridge.agent_completed.connect(_on_agent_completed)
                bridge.agent_failed.connect(_on_agent_failed)
                t.finished.connect(_cleanup_agent_thread)
                t.finished.connect(t.deleteLater)
                _active_agent_threads.append((t, w, bridge))
                t.start()

            def _on_analyze(eid: str) -> None:
                exp = store.get(eid)
                if not exp:
                    return

                plan = Path(exp.plan_path) if exp.plan_path else None
                if plan and plan.exists():
                    self._compliance.attach_pdf(plan)
                    self._add_attachments([plan])
                    if exp.latitude and exp.longitude:
                        self._compliance.set_coordinates(exp.latitude, exp.longitude)
                    if exp.municipality:
                        self._compliance.set_municipality(exp.municipality)
                    plan_path = Path(exp.plan_path)
                    if exp.latitude and exp.longitude:
                        prompt = build_coordinate_compliance_prompt(
                            plan_path, exp.latitude, exp.longitude
                        )
                    else:
                        parts = [f"Analiza el expediente «{exp.title}»."]
                        parts.append(f"Dirección: {exp.address}")
                        if exp.municipality:
                            parts.append(f"Municipio: {exp.municipality}")
                        if exp.cadastral_ref:
                            parts.append(f"Ref. catastral: {exp.cadastral_ref}")
                        parts.append(
                            "Usa plan_compliance_check con el plano adjunto "
                            "y el municipio indicado."
                        )
                        prompt = "\n".join(parts)
                    self._active_exp_store = store
                    self._active_exp_id = eid
                    self.expediente_selected.emit(exp)
                    self._set_active_expediente(exp)
                    dlg.accept()
                    QTimer.singleShot(50, lambda: self._send_nav_prompt(prompt))
                else:
                    analysis = _build_expediente_analysis(exp)
                    updated = dataclasses.replace(
                        exp,
                        analysis_result=json.dumps(analysis, ensure_ascii=False),
                        status="analizado",
                    )
                    store.update(updated)
                    list_panel.populate(store.list_all())
                    detail_panel.load_expediente(updated)
                    self._last_exp_label = updated.title
                    self._refresh_status_bar()
                    self.statusBar().showMessage(
                        f"Expediente analizado: {analysis['verdict_label']}"
                    )

            def _on_export(eid: str) -> None:
                exp = store.get(eid)
                if not exp:
                    return
                if not exp.analysis_result:
                    analysis = _build_expediente_analysis(exp)
                    exp = dataclasses.replace(
                        exp,
                        analysis_result=json.dumps(analysis, ensure_ascii=False),
                        status="analizado",
                    )
                    store.update(exp)
                safe_title = re.sub(r"[^a-zA-Z0-9_-]+", "_", exp.title).strip("_").lower()
                stamp = datetime.now().strftime("%Y%m%d_%H%M")
                output_path = (
                    Path.home()
                    / "Desktop"
                    / f"informe_adv_archon_{safe_title}_{stamp}.pdf"
                )
                detail_panel.set_operation_busy(True, "Generando informe PDF profesional…")
                self.statusBar().showMessage("Generando informe PDF…")
                t = QThread(dlg)
                t.setObjectName("adv-archon-expediente-export")
                w = _ExportWorker(exp, output_path)
                bridge = _ExpedienteThreadBridge(dlg)
                w.moveToThread(t)
                t.started.connect(w.run)

                def _on_exported(path_text: str) -> None:
                    path = Path(path_text)
                    updated = dataclasses.replace(
                        exp,
                        report_path=str(path),
                        status="informe_listo",
                    )
                    store.update(updated)
                    try:
                        from adv_archon.core.feedback_store import FeedbackStore

                        FeedbackStore(data_dir / "feedback.db").add_from_expediente(updated)
                    except Exception:
                        pass
                    list_panel.populate(store.list_all())
                    detail_panel.load_expediente(updated)
                    detail_panel.set_operation_busy(False)
                    self._last_exp_label = updated.title
                    self._refresh_status_bar()
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                    self.statusBar().showMessage(f"Informe exportado: {path.name}")

                def _on_export_failed(message: str) -> None:
                    detail_panel.set_operation_busy(False)
                    self.statusBar().showMessage(
                        f"No se pudo exportar el informe: {message}"
                    )

                def _cleanup_export_thread() -> None:
                    with suppress(ValueError):
                        _active_export_threads.remove((t, w, bridge))

                w.exported.connect(bridge.exported)
                w.failed.connect(bridge.export_failed)
                w.finished.connect(w.deleteLater)
                w.finished.connect(t.quit)
                bridge.exported.connect(_on_exported)
                bridge.export_failed.connect(_on_export_failed)
                t.finished.connect(_cleanup_export_thread)
                t.finished.connect(t.deleteLater)
                _active_export_threads.append((t, w, bridge))
                t.start()

            def _on_talk(eid: str) -> None:
                exp = store.get(eid)
                if not exp:
                    return
                detail_panel.load_expediente(exp)
                self._set_active_expediente(exp)
                self.expediente_selected.emit(exp)
                dlg.accept()
                QTimer.singleShot(80, lambda: self._submit_live_prompt("/live"))

            def _on_review(eid: str, action: str) -> None:
                exp = store.get(eid)
                if not exp:
                    return
                from adv_archon.core.expediente_quality import review_state_json

                note: str | None = None
                resolved_action: str | None = action
                if action == "note":
                    current = ""
                    try:
                        current_state = json.loads(exp.review_state or "{}")
                        current = str(current_state.get("note") or "")
                    except (TypeError, ValueError):
                        current = ""
                    note, ok = QInputDialog.getMultiLineText(
                        dlg,
                        "Nota de revisión",
                        "Añade una nota del arquitecto para este expediente:",
                        current,
                    )
                    if not ok:
                        return
                    resolved_action = None
                updated = dataclasses.replace(
                    exp,
                    review_state=review_state_json(
                        exp.review_state,
                        action=resolved_action,
                        note=note,
                    ),
                )
                store.update(updated)
                detail_panel.load_expediente(updated)
                list_panel.populate(store.list_all())
                self.statusBar().showMessage("Revisión de arquitecto guardada.", 4000)

            def _on_agent_step_action(eid: str, step_code: str, action: str) -> None:
                exp = store.get(eid)
                if not exp:
                    return
                from adv_archon.core.agent_plan import (
                    append_agent_event,
                    update_agent_step_review,
                )

                action_messages = {
                    "validate": "Paso validado por arquitecto.",
                    "accept-warning": "Advertencia aceptada por arquitecto.",
                    "repeat": "Repetición solicitada por arquitecto.",
                    "include": "Paso incluido expresamente en el informe.",
                    "exclude": "Paso excluido del informe por arquitecto.",
                }
                message = action_messages.get(action, "Decisión de arquitecto registrada.")
                updated = dataclasses.replace(
                    exp,
                    agent_step_reviews=update_agent_step_review(
                        exp.agent_step_reviews,
                        step_code=step_code,
                        action=action,
                    ),
                    agent_history=append_agent_event(
                        exp.agent_history,
                        step_code=step_code,
                        title="Decisión arquitecto",
                        status="completed" if action != "repeat" else "pending",
                        message=message,
                    ),
                )
                store.update(updated)
                from adv_archon.core.office_memory import OfficeMemoryStore

                office_store = OfficeMemoryStore(
                    self._studio_data_dir() / "office_memory.db"
                )
                try:
                    office_store.record_step_decision(
                        municipality=exp.municipality,
                        step_code=step_code,
                        action=action,
                        label=message,
                        source="expediente_panel",
                    )
                finally:
                    office_store.close()
                list_panel.populate(store.list_all())
                detail_panel.load_expediente(updated)
                self._last_exp_label = updated.title
                self._refresh_status_bar()
                self.statusBar().showMessage(message, 4000)
                if action == "repeat":
                    QTimer.singleShot(120, lambda: _launch_agent_review(eid))

            def _prepare_document_draft(eid: str) -> dict[str, Any]:
                exp = store.get(eid)
                if exp is None:
                    return {}
                from adv_archon.core.expediente_documents import ensure_expediente_draft

                draft = ensure_expediente_draft(document_store, exp)
                return draft.to_dict()

            def _save_document_draft(eid: str, payload: dict[str, Any]) -> dict[str, Any]:
                payload = dict(payload)
                payload["expediente_id"] = eid
                payload["kind"] = payload.get("kind") or "expediente"
                from adv_archon.core.expediente_documents import (
                    save_edited_expediente_draft,
                )

                draft = save_edited_expediente_draft(document_store, payload)
                self.statusBar().showMessage("Borrador de expediente guardado.", 3500)
                return draft.to_dict()

            def _export_document_draft(
                eid: str,
                kind: str,
                payload: dict[str, Any],
            ) -> str:
                del eid
                from adv_archon.core.expediente_documents import (
                    export_expediente_draft,
                    save_edited_expediente_draft,
                )

                draft = save_edited_expediente_draft(document_store, payload)
                output = export_expediente_draft(
                    draft,
                    kind,
                    Path.home() / "Desktop",
                    archon_logo_path=logo_path(),
                )
                document_store.mark_exported(draft.id, kind, output)
                self.statusBar().showMessage(f"Documento exportado: {output.name}", 5000)
                return str(output)

            detail_panel = ExpedienteDetailPanel(
                on_attach_plan=lambda eid: _attach_plan(eid),
                on_analyze=_on_analyze,
                on_export=_on_export,
                on_talk=_on_talk,
                on_review=_on_review,
                on_run_agent=_launch_agent_review,
                on_agent_step_action=_on_agent_step_action,
                on_prepare_document=_prepare_document_draft,
                on_save_document=_save_document_draft,
                on_export_document=_export_document_draft,
            )

            def _attach_plan(eid: str) -> None:
                from PySide6.QtWidgets import QFileDialog as _QFD
                picker = _QFD(dlg)
                self._active_file_picker = picker
                picker.setWindowTitle("Adjuntar plano arquitectónico")
                picker.setDirectory(str(Path.home()))
                picker.setNameFilter(
                    "Planos (*.pdf *.dwg *.dxf *.png *.jpg *.jpeg);;Todos (*)"
                )
                picker.setFileMode(_QFD.FileMode.ExistingFile)
                picker.setOption(_QFD.Option.DontUseNativeDialog, True)

                def _on_accepted() -> None:
                    paths = picker.selectedFiles()
                    if not paths:
                        return
                    exp = store.get(eid)
                    if not exp:
                        return
                    updated = dataclasses.replace(exp, plan_path=paths[0])
                    store.update(updated)
                    detail_panel.load_expediente(updated)
                    self._last_exp_label = updated.title
                    self._refresh_status_bar()
                    self._active_file_picker = None

                picker.accepted.connect(_on_accepted)
                picker.rejected.connect(lambda: setattr(self, "_active_file_picker", None))
                picker.open()   # non-blocking — avoids nested exec() crash on macOS

            def _select(eid: str) -> None:
                exp = store.get(eid)
                if exp:
                    detail_panel.load_expediente(exp)
                    self._set_active_expediente(exp)

            def _new() -> None:
                d = NewExpedienteDialog(dlg)
                from PySide6.QtWidgets import QDialog as _QD
                if d.exec() != _QD.DialogCode.Accepted:
                    return
                exp = store.create(
                    title=d.title_text(),
                    address=d.address_text(),
                    notes=d.notes_text(),
                    case_type=d.case_type(),
                )
                list_panel.populate(store.list_all())
                detail_panel.load_expediente(exp)
                self._set_active_expediente(exp)
                self._last_exp_label = exp.title
                self._refresh_status_bar()
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

            exps = store.list_all()
            list_panel.populate(exps)
            if exps:
                selected_row = 0
                if selected_id:
                    for idx, exp in enumerate(exps):
                        if exp.id == selected_id:
                            selected_row = idx
                            break
                detail_panel.load_expediente(exps[selected_row])
                list_panel._list.setCurrentRow(selected_row)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            if open_new:
                QTimer.singleShot(120, _new)

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
    app.setQuitOnLastWindowClosed(False)
    resolved_logo = logo_path()
    if resolved_logo.exists():
        app.setWindowIcon(QIcon(str(resolved_logo)))
    global _DESKTOP_WINDOW_REF
    from adv_archon.desktop.app_v2 import DesktopWindowV2
    window = DesktopWindowV2(
        config=config,
        project_root=project_root,
        system_prompt=system_prompt,
        incognito=incognito,
    )
    _DESKTOP_WINDOW_REF = window
    app._adv_archon_window = window  # keep a strong Python reference for Finder launches
    app.aboutToQuit.connect(window._stop_background_threads)
    window.show()
    window.raise_()
    window.activateWindow()
    QTimer.singleShot(150, window._start_backend)
    QTimer.singleShot(250, window.showNormal)
    QTimer.singleShot(300, window.raise_)
    QTimer.singleShot(350, window.activateWindow)
    QTimer.singleShot(1200, window.showNormal)
    QTimer.singleShot(1250, window.raise_)
    QTimer.singleShot(1300, window.activateWindow)
    return app.exec()
