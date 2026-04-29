# mypy: ignore-errors
from __future__ import annotations

from pathlib import Path

from adv_archon.core.attachments import normalize_attachment_paths
from adv_archon.core.config import AppConfig
from adv_archon.core.llm import LLMRouter
from adv_archon.core.profiles import ProfileManager
from adv_archon.desktop.branding import desktop_stylesheet, logo_path
from adv_archon.desktop.presenters import (
    build_history_entry,
    format_sources_summary,
    merge_recent_items,
    onboarding_cards,
    recommended_window_size,
)


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
            QSize,
            Qt,
            QThread,
            QTimer,
            Signal,
        )
        from PySide6.QtGui import QAction, QIcon, QPixmap, QTextCursor
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QFileDialog,
            QFrame,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QScrollArea,
            QSplitter,
            QStackedWidget,
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

    class ConfirmBridge(QObject):
        requested = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self._question: str | None = None
            self._accepted = False
            self._waiting = None

        def ask(self, question: str) -> bool:
            import threading

            waiting = threading.Event()
            self._question = question
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

    class AttachmentList(QListWidget):
        files_dropped = Signal(list)

        def __init__(self) -> None:
            super().__init__()
            self.setAcceptDrops(True)
            self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        def dragEnterEvent(self, event) -> None:  # type: ignore[override]
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                return
            event.ignore()

        def dropEvent(self, event) -> None:  # type: ignore[override]
            urls = event.mimeData().urls()
            paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
                return
            event.ignore()

    class DesktopWindow(QMainWindow):
        prompt_requested = Signal(str, object)
        import_requested = Signal(object)
        mode_requested = Signal(str)
        profile_requested = Signal(str)
        cancel_requested = Signal()
        shutdown_requested = Signal()

        def __init__(self) -> None:
            super().__init__()
            self._logo_path = logo_path()
            self._logo_pixmap = QPixmap(str(self._logo_path)) if self._logo_path.exists() else None
            self.setWindowTitle("ADV ARCHON")
            self.setMinimumSize(1080, 720)
            if self._logo_pixmap is not None:
                icon = QIcon(str(self._logo_path))
                self.setWindowIcon(icon)
            screen = QApplication.primaryScreen()
            if screen is not None:
                width, height = recommended_window_size(
                    screen.availableGeometry().width(),
                    screen.availableGeometry().height(),
                )
                self.resize(width, height)
            else:
                self.resize(1280, 860)
            self._confirm_bridge = ConfirmBridge()
            self._confirm_bridge.requested.connect(self._show_confirmation_dialog)
            self._profile_manager = ProfileManager(
                config.paths.profile_state_file,
                default_profile=config.profiles.default_profile,
                definitions=config.profiles.definitions,
            )
            self._selected_mode = llm.mode
            self._selected_profile = self._profile_manager.active_profile
            self._attachments: list[Path] = []
            self._recent_history_entries: list[str] = []
            self._recent_attachment_entries: list[str] = []
            self._active_tool_names: list[str] = []
            self._last_snapshot: TurnContextSnapshot | None = None
            self._pending_prompt = ""
            self._pending_attachments: list[Path] = []
            self._current_chunked_reply = False
            self._intro_played = False
            self._staged_widgets: list[QWidget] = []
            self._progress_animation = None
            self._busy_state = DesktopBusyState(backend_ready=False, busy=True, task="initializing")
            self._close_requested = False
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
            self._load_header_state()
            self._fit_window_to_available_screen()
            self._append_system("Preparando backend desktop…")
            self._backend_thread.start()

        def closeEvent(self, event) -> None:  # type: ignore[override]
            if self._backend_thread is None or not self._backend_thread.isRunning():
                event.accept()
                return
            if self._close_requested:
                event.ignore()
                return
            self._close_requested = True
            self._append_context_line(
                "Cierre solicitado. Esperando a que termine el worker activo…"
            )
            self._handle_busy_state_changed(
                DesktopBusyState(
                    backend_ready=self._busy_state.backend_ready,
                    busy=False,
                    task="idle",
                    closing=True,
                )
            )
            self.shutdown_requested.emit()
            event.ignore()

        def showEvent(self, event) -> None:  # type: ignore[override]
            super().showEvent(event)
            self._fit_window_to_available_screen()
            if self._intro_played:
                return
            self._intro_played = True
            QTimer.singleShot(80, self._play_intro_animation)

        def _build_ui(self) -> None:
            scroll = QScrollArea()
            scroll.setObjectName("RootScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            root = QWidget()
            root.setObjectName("Root")
            layout = QVBoxLayout(root)
            layout.setContentsMargins(18, 18, 18, 18)
            layout.setSpacing(14)

            self._hero_card = QFrame()
            self._hero_card.setObjectName("HeroCard")
            hero_layout = QVBoxLayout(self._hero_card)
            hero_layout.setContentsMargins(18, 18, 18, 18)
            hero_layout.setSpacing(14)

            hero_top = QHBoxLayout()
            hero_top.setSpacing(18)
            hero_top.addWidget(self._build_logo_label(88))

            hero_copy = QVBoxLayout()
            hero_copy.setSpacing(4)
            eyebrow = QLabel("Local-First Executive AI")
            eyebrow.setObjectName("HeroEyebrow")
            hero_title = QLabel("ADV ARCHON Desktop")
            hero_title.setObjectName("HeroTitle")
            hero_subtitle = QLabel(
                "Una consola ejecutiva privada para estudiar, decidir y operar desde tu Mac "
                "con memoria, documentos, agenda y automatización."
            )
            hero_subtitle.setWordWrap(True)
            hero_subtitle.setObjectName("HeroSubtitle")
            hero_copy.addWidget(eyebrow)
            hero_copy.addWidget(hero_title)
            hero_copy.addWidget(hero_subtitle)
            hero_top.addLayout(hero_copy, 1)

            controls_column = QVBoxLayout()
            controls_column.setSpacing(10)

            controls_row = QHBoxLayout()
            controls_row.setSpacing(8)
            mode_label = QLabel("Modo")
            mode_label.setObjectName("MetaLabel")
            self._mode_combo = QComboBox()
            self._mode_combo.addItems(["local", "cloud"])
            self._mode_combo.currentTextChanged.connect(self._change_mode)
            profile_label = QLabel("Perfil")
            profile_label.setObjectName("MetaLabel")
            self._profile_combo = QComboBox()
            self._profile_combo.addItems(self._profile_manager.available_profiles())
            self._profile_combo.currentTextChanged.connect(self._change_profile)
            controls_row.addWidget(mode_label)
            controls_row.addWidget(self._mode_combo)
            controls_row.addWidget(profile_label)
            controls_row.addWidget(self._profile_combo)
            controls_column.addLayout(controls_row)

            self._status_label = QLabel("")
            self._status_label.setObjectName("StatusPill")
            controls_column.addWidget(self._status_label, alignment=Qt.AlignmentFlag.AlignRight)
            hero_top.addLayout(controls_column)
            hero_layout.addLayout(hero_top)

            quick_actions = QHBoxLayout()
            quick_actions.setSpacing(10)
            self._daily_action_button = QPushButton("Briefing diario")
            self._daily_action_button.clicked.connect(self._send_daily_prompt)
            self._decorate_button(self._daily_action_button, role="primary")
            self._briefing_action_button = QPushButton("Modo ejecutivo")
            self._briefing_action_button.clicked.connect(self._send_briefing_prompt)
            self._decorate_button(self._briefing_action_button, role="accent")
            self._triage_action_button = QPushButton("Triage Gmail")
            self._triage_action_button.clicked.connect(self._send_triage_prompt)
            self._decorate_button(self._triage_action_button, role="secondary")
            self._study_action_button = QPushButton("Study partner")
            self._study_action_button.clicked.connect(self._send_study_prompt)
            self._decorate_button(self._study_action_button, role="ghost")
            quick_actions.addWidget(self._daily_action_button)
            quick_actions.addWidget(self._briefing_action_button)
            quick_actions.addWidget(self._triage_action_button)
            quick_actions.addWidget(self._study_action_button)
            quick_actions.addStretch(1)
            hero_layout.addLayout(quick_actions)

            layout.addWidget(self._hero_card)

            self._progress_bar = QProgressBar()
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
            layout.addWidget(self._progress_bar)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.setHandleWidth(10)
            splitter.setChildrenCollapsible(False)
            layout.addWidget(splitter, 1)

            chat_panel = QWidget()
            chat_layout = QVBoxLayout(chat_panel)
            chat_layout.setContentsMargins(0, 0, 0, 0)
            chat_layout.setSpacing(12)

            self._transcript_card = QFrame()
            self._transcript_card.setObjectName("TranscriptCard")
            transcript_layout = QVBoxLayout(self._transcript_card)
            transcript_layout.setContentsMargins(16, 16, 16, 16)
            transcript_layout.setSpacing(10)
            transcript_layout.addWidget(self._section_label("Conversación"))

            self._conversation_stack = QStackedWidget()
            self._conversation_stack.addWidget(self._build_onboarding_panel())

            self._transcript = QPlainTextEdit()
            self._transcript.setObjectName("Transcript")
            self._transcript.setReadOnly(True)
            self._transcript.setPlaceholderText(
                "Aquí aparecerá la conversación con ADV ARCHON."
            )
            self._conversation_stack.addWidget(self._transcript)
            self._conversation_stack.setCurrentIndex(0)
            transcript_layout.addWidget(self._conversation_stack, 1)
            chat_layout.addWidget(self._transcript_card, 5)

            self._attachments_card = QFrame()
            self._attachments_card.setObjectName("AttachmentsCard")
            attachments_layout = QVBoxLayout(self._attachments_card)
            attachments_layout.setContentsMargins(16, 16, 16, 16)
            attachments_layout.setSpacing(10)
            attachment_bar = QHBoxLayout()
            attachment_bar.addWidget(self._section_label("Adjuntos activos"))
            attachment_bar.addStretch(1)
            self._add_button = QPushButton("Añadir archivos")
            self._add_button.clicked.connect(self._pick_attachments)
            self._decorate_button(self._add_button, role="ghost")
            self._remove_button = QPushButton("Quitar seleccionados")
            self._remove_button.clicked.connect(self._remove_selected_attachments)
            self._decorate_button(self._remove_button, role="ghost")
            self._import_button = QPushButton("Añadir al conocimiento")
            self._import_button.clicked.connect(self._import_selected_attachments)
            self._decorate_button(self._import_button, role="accent")
            attachment_bar.addWidget(self._add_button)
            attachment_bar.addWidget(self._remove_button)
            attachment_bar.addWidget(self._import_button)
            attachments_layout.addLayout(attachment_bar)

            self._attachment_list = AttachmentList()
            self._attachment_list.setObjectName("AttachmentList")
            self._attachment_list.setAlternatingRowColors(True)
            self._attachment_list.files_dropped.connect(self._add_attachments)
            self._attachment_list.setToolTip(
                "Arrastra aquí archivos o carpetas desde Finder. "
                "Se usarán en el próximo mensaje o podrán añadirse al conocimiento."
            )
            attachments_layout.addWidget(self._attachment_list)
            chat_layout.addWidget(self._attachments_card, 2)

            self._composer_card = QFrame()
            self._composer_card.setObjectName("ComposerCard")
            composer_wrap = QVBoxLayout(self._composer_card)
            composer_wrap.setContentsMargins(16, 16, 16, 16)
            composer_wrap.setSpacing(10)
            composer_wrap.addWidget(self._section_label("Pide algo"))

            composer = QHBoxLayout()
            composer.setSpacing(12)
            self._input = QTextEdit()
            self._input.setObjectName("PromptInput")
            self._input.setAcceptRichText(False)
            self._input.setPlaceholderText(
                "Escribe tu petición con lenguaje natural. Puedes pedir briefings, "
                "resúmenes, comparaciones, notas o acciones sobre adjuntos."
            )
            self._input.setFixedHeight(110)
            composer.addWidget(self._input, 1)
            send_column = QVBoxLayout()
            send_column.setSpacing(10)
            self._send_button = QPushButton("Enviar")
            self._send_button.clicked.connect(self._submit_prompt)
            self._decorate_button(self._send_button, role="primary")
            self._cancel_button = QPushButton("Cancelar")
            self._cancel_button.clicked.connect(self._cancel_active_task)
            self._decorate_button(self._cancel_button, role="accent")
            self._clear_button = QPushButton("Limpiar adjuntos")
            self._clear_button.clicked.connect(self._clear_attachments)
            self._decorate_button(self._clear_button, role="ghost")
            send_column.addWidget(self._send_button)
            send_column.addWidget(self._cancel_button)
            send_column.addWidget(self._clear_button)
            send_column.addStretch(1)
            composer.addLayout(send_column)
            composer_wrap.addLayout(composer)
            chat_layout.addWidget(self._composer_card, 2)

            context_panel = QWidget()
            context_layout = QVBoxLayout(context_panel)
            context_layout.setContentsMargins(0, 0, 0, 0)
            context_layout.setSpacing(12)

            self._command_card = QFrame()
            self._command_card.setObjectName("SidebarCard")
            command_layout = QVBoxLayout(self._command_card)
            command_layout.setContentsMargins(16, 16, 16, 16)
            command_layout.setSpacing(10)
            command_header = QHBoxLayout()
            command_header.addWidget(self._build_logo_label(44))
            command_copy = QVBoxLayout()
            command_copy.setSpacing(2)
            command_title = QLabel("Centro de mando")
            command_title.setObjectName("SectionTitle")
            command_subtitle = QLabel("Contexto, fuentes y rastro útil del turno actual.")
            command_subtitle.setObjectName("HeroSubtitle")
            command_subtitle.setWordWrap(True)
            command_copy.addWidget(command_title)
            command_copy.addWidget(command_subtitle)
            command_header.addLayout(command_copy, 1)
            command_layout.addLayout(command_header)
            context_layout.addWidget(self._command_card)

            self._context_card = QFrame()
            self._context_card.setObjectName("PanelCard")
            context_card_layout = QVBoxLayout(self._context_card)
            context_card_layout.setContentsMargins(16, 16, 16, 16)
            context_card_layout.setSpacing(10)
            context_card_layout.addWidget(self._section_label("Contexto y actividad"))
            self._context_view = QPlainTextEdit()
            self._context_view.setObjectName("SidebarPanel")
            self._context_view.setReadOnly(True)
            self._context_view.setPlaceholderText(
                "Aquí verás intención, perfil, checkpoint y herramientas usadas."
            )
            context_card_layout.addWidget(self._context_view, 1)
            context_layout.addWidget(self._context_card, 2)

            self._sources_card = QFrame()
            self._sources_card.setObjectName("PanelCard")
            sources_layout = QVBoxLayout(self._sources_card)
            sources_layout.setContentsMargins(16, 16, 16, 16)
            sources_layout.setSpacing(10)
            sources_layout.addWidget(self._section_label("Fuentes usadas"))
            self._sources_view = QPlainTextEdit()
            self._sources_view.setObjectName("SidebarPanel")
            self._sources_view.setReadOnly(True)
            self._sources_view.setPlaceholderText(
                "Memoria, conocimiento local y herramientas relevantes del turno."
            )
            sources_layout.addWidget(self._sources_view, 1)
            context_layout.addWidget(self._sources_card, 2)

            self._history_card = QFrame()
            self._history_card.setObjectName("PanelCard")
            history_layout = QVBoxLayout(self._history_card)
            history_layout.setContentsMargins(16, 16, 16, 16)
            history_layout.setSpacing(10)
            history_layout.addWidget(self._section_label("Historial reciente"))
            self._history_list = QListWidget()
            self._history_list.setObjectName("CompactList")
            self._history_list.setAlternatingRowColors(True)
            history_layout.addWidget(self._history_list, 1)
            context_layout.addWidget(self._history_card, 2)

            self._recent_attachments_card = QFrame()
            self._recent_attachments_card.setObjectName("PanelCard")
            recent_attachments_layout = QVBoxLayout(self._recent_attachments_card)
            recent_attachments_layout.setContentsMargins(16, 16, 16, 16)
            recent_attachments_layout.setSpacing(10)
            recent_attachments_layout.addWidget(self._section_label("Adjuntos recientes"))
            self._recent_attachments_list = QListWidget()
            self._recent_attachments_list.setObjectName("CompactList")
            self._recent_attachments_list.setAlternatingRowColors(True)
            recent_attachments_layout.addWidget(self._recent_attachments_list, 1)
            context_layout.addWidget(self._recent_attachments_card, 2)

            chat_layout.setStretch(0, 5)
            chat_layout.setStretch(1, 2)
            chat_layout.setStretch(2, 2)
            context_layout.setStretch(0, 0)
            context_layout.setStretch(1, 2)
            context_layout.setStretch(2, 2)
            context_layout.setStretch(3, 2)
            context_layout.setStretch(4, 2)

            splitter.addWidget(chat_panel)
            splitter.addWidget(context_panel)
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 2)
            splitter.setSizes([860, 420])

            scroll.setWidget(root)
            self.setCentralWidget(scroll)

            daily_action = QAction("Daily Brief", self)
            daily_action.triggered.connect(self._send_daily_prompt)
            self._daily_action = daily_action
            self.menuBar().addAction(daily_action)

        def _apply_branding(self) -> None:
            self.setStyleSheet(desktop_stylesheet())

        def _fit_window_to_available_screen(self) -> None:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is None:
                return
            available = screen.availableGeometry()
            target_width, target_height = recommended_window_size(
                available.width(),
                available.height(),
            )
            width = min(max(self.width(), self.minimumWidth()), target_width)
            height = min(max(self.height(), self.minimumHeight()), target_height)
            self.resize(width, height)
            frame = self.frameGeometry()
            x = max(
                available.left() + 12,
                min(frame.x(), available.right() - frame.width() - 12),
            )
            y = max(
                available.top() + 12,
                min(frame.y(), available.bottom() - frame.height() - 12),
            )
            self.move(x, y)

        def _build_onboarding_panel(self) -> QWidget:
            panel = QFrame()
            panel.setObjectName("OnboardingCard")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(22, 22, 22, 22)
            layout.setSpacing(16)

            top = QHBoxLayout()
            top.setSpacing(14)
            top.addWidget(self._build_logo_label(72))
            copy = QVBoxLayout()
            copy.setSpacing(4)
            title = QLabel("Tu centro de mando está listo")
            title.setObjectName("OnboardingTitle")
            body = QLabel(
                "Empieza con un briefing, estudia un documento o deja que ARCHON "
                "te oriente con tus notas, correos y conocimiento local."
            )
            body.setWordWrap(True)
            body.setObjectName("OnboardingBody")
            copy.addWidget(title)
            copy.addWidget(body)
            top.addLayout(copy, 1)
            layout.addLayout(top)

            for card in onboarding_cards():
                card_frame = QFrame()
                card_frame.setObjectName("OnboardingPromptCard")
                card_layout = QVBoxLayout(card_frame)
                card_layout.setContentsMargins(14, 14, 14, 14)
                card_layout.setSpacing(8)
                card_title = QLabel(card.title)
                card_title.setObjectName("SectionTitle")
                card_body = QLabel(card.body)
                card_body.setObjectName("OnboardingBody")
                card_body.setWordWrap(True)
                button = QPushButton("Lanzar")
                button.setObjectName("QuickPromptButton")
                if not self.windowIcon().isNull():
                    button.setIcon(self.windowIcon())
                    button.setIconSize(QSize(16, 16))
                button.clicked.connect(
                    lambda _checked=False, prompt=card.prompt: self._run_onboarding_prompt(prompt)
                )
                card_layout.addWidget(card_title)
                card_layout.addWidget(card_body)
                card_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
                layout.addWidget(card_frame)

            layout.addStretch(1)
            return panel

        def _build_logo_label(self, size: int) -> QLabel:
            label = QLabel()
            label.setFixedSize(size, size)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if self._logo_pixmap is not None and not self._logo_pixmap.isNull():
                label.setPixmap(
                    self._logo_pixmap.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            return label

        def _section_label(self, text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("SectionTitle")
            return label

        def _run_onboarding_prompt(self, prompt: str) -> None:
            self._input.setPlainText(prompt)
            self._submit_prompt()

        def _decorate_button(self, button: QPushButton, *, role: str) -> None:
            role_names = {
                "primary": "PrimaryButton",
                "accent": "AccentButton",
                "ghost": "GhostButton",
                "secondary": "",
            }
            button.setObjectName(role_names.get(role, ""))
            if self.windowIcon().isNull():
                return
            button.setIcon(self.windowIcon())
            button.setIconSize(QSize(18, 18))

        def _load_header_state(self) -> None:
            self._mode_combo.setCurrentText(self._selected_mode)
            self._profile_combo.setCurrentText(self._selected_profile)
            self._handle_busy_state_changed(self._busy_state)

        def _play_intro_animation(self) -> None:
            widgets = [
                self._hero_card,
                self._transcript_card,
                self._attachments_card,
                self._composer_card,
                self._command_card,
                self._context_card,
                self._sources_card,
                self._history_card,
                self._recent_attachments_card,
            ]
            self._staged_widgets = widgets
            for widget in widgets:
                widget.setVisible(False)
            for index, widget in enumerate(widgets):
                QTimer.singleShot(45 * index, lambda w=widget: self._reveal_widget(w))

        def _reveal_widget(self, widget: QWidget) -> None:
            widget.setVisible(True)
            widget.update()

        def _show_onboarding(self) -> None:
            self._conversation_stack.setCurrentIndex(0)

        def _show_transcript(self) -> None:
            if self._conversation_stack.currentIndex() == 1:
                return
            self._conversation_stack.setCurrentIndex(1)
            self._transcript.update()

        def _change_mode(self, mode: str) -> None:
            self._selected_mode = mode
            self._mode_combo.setCurrentText(mode)
            self.mode_requested.emit(mode)
            self._refresh_status(
                self._busy_state.status_text(
                    mode=self._selected_mode,
                    profile=self._selected_profile,
                )
            )

        def _change_profile(self, profile: str) -> None:
            resolved = self._profile_manager.resolve(profile)
            self._selected_profile = resolved
            self._profile_combo.setCurrentText(resolved)
            self.profile_requested.emit(resolved)
            self._refresh_status(
                self._busy_state.status_text(
                    mode=self._selected_mode,
                    profile=self._selected_profile,
                )
            )

        def _refresh_status(self, message: str) -> None:
            self._status_label.setText(message)

        def _animate_progress(self, value: int) -> None:
            current = self._progress_bar.value()
            animation = QPropertyAnimation(self._progress_bar, b"value", self)
            animation.setDuration(220)
            animation.setStartValue(current)
            animation.setEndValue(value)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start()
            self._progress_animation = animation

        def _handle_backend_ready(self, greeting: str) -> None:
            self._append_system(greeting)

        def _show_confirmation_dialog(self, question: str) -> None:
            answer = QMessageBox.question(
                self,
                "Confirmación de ADV ARCHON",
                question,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            self._confirm_bridge.resolve(answer == QMessageBox.StandardButton.Yes)

        def _pick_attachments(self) -> None:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Selecciona archivos para ADV ARCHON",
                str(Path.home()),
                "Todos los archivos (*)",
            )
            if files:
                self._add_attachments([Path(path) for path in files])

        def _add_attachments(self, paths: list[Path]) -> None:
            merged = normalize_attachment_paths([*self._attachments, *paths])
            self._attachments = merged
            self._render_attachments()
            self._append_system(
                "Adjuntos preparados: "
                + ", ".join(path.name or str(path) for path in normalize_attachment_paths(paths))
            )

        def _render_attachments(self) -> None:
            self._attachment_list.clear()
            for path in self._attachments:
                label = path.name if path.name else str(path)
                item = QListWidgetItem(f"{label}\n{path}")
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                self._attachment_list.addItem(item)
            self._handle_busy_state_changed(self._busy_state)

        def _selected_attachment_paths(self) -> list[Path]:
            paths: list[Path] = []
            for item in self._attachment_list.selectedItems():
                raw_path = item.data(Qt.ItemDataRole.UserRole)
                if raw_path:
                    paths.append(Path(str(raw_path)))
            return paths

        def _remove_selected_attachments(self) -> None:
            selected = {path for path in self._selected_attachment_paths()}
            if not selected:
                return
            self._attachments = [path for path in self._attachments if path not in selected]
            self._render_attachments()

        def _clear_attachments(self) -> None:
            self._attachments = []
            self._render_attachments()

        def _import_selected_attachments(self) -> None:
            paths = self._selected_attachment_paths() or list(self._attachments)
            if not paths:
                self._append_system("No hay adjuntos para añadir al conocimiento.")
                return
            self._append_system(
                "Añadiendo al conocimiento: "
                + ", ".join(path.name or str(path) for path in paths)
            )
            self._set_busy(True, task="knowledge_import")
            self.import_requested.emit([str(path) for path in paths])

        def _submit_prompt(self) -> None:
            prompt = self._input.toPlainText().strip()
            if not prompt:
                return
            attachments = list(self._attachments)
            self._show_transcript()
            self._input.clear()
            self._pending_prompt = prompt
            self._pending_attachments = attachments
            self._active_tool_names = []
            self._last_snapshot = None
            self._refresh_sources_view()
            self._append_user(prompt, attachments)
            self._append_assistant_prefix()
            self._current_chunked_reply = False
            self._set_busy(True, task="prompt")
            self.prompt_requested.emit(prompt, [str(path) for path in attachments])

        def _send_daily_prompt(self) -> None:
            self._input.setPlainText(
                "prepara mi daily brief con agenda, tareas, gmail, drive y notas"
            )
            self._submit_prompt()

        def _send_briefing_prompt(self) -> None:
            self._input.setPlainText(
                "dame un briefing ejecutivo del día con foco en prioridades, "
                "agenda, correos y próximos riesgos"
            )
            self._submit_prompt()

        def _send_triage_prompt(self) -> None:
            self._input.setPlainText(
                "hazme triage del gmail y dime qué responder hoy, con borradores si hace falta"
            )
            self._submit_prompt()

        def _send_study_prompt(self) -> None:
            if self._attachments:
                prompt = (
                    "actúa como study partner sobre estos adjuntos. "
                    "Dame ideas clave, preguntas y un mini plan de repaso."
                )
            else:
                prompt = (
                    "actúa como study partner sobre el último documento relevante que "
                    "hayamos leído y prepara un repaso breve."
                )
            self._input.setPlainText(prompt)
            self._submit_prompt()

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
            accepts_actions = state.accepts_user_actions
            can_dispatch = state.can_dispatch_requests
            allows_configuration = state.allows_configuration
            self._input.setEnabled(accepts_actions)
            self._send_button.setEnabled(can_dispatch)
            self._add_button.setEnabled(accepts_actions)
            self._remove_button.setEnabled(accepts_actions)
            self._import_button.setEnabled(can_dispatch and bool(self._attachments))
            self._clear_button.setEnabled(accepts_actions and bool(self._attachments))
            self._attachment_list.setEnabled(accepts_actions)
            self._mode_combo.setEnabled(allows_configuration)
            self._profile_combo.setEnabled(allows_configuration)
            self._daily_action.setEnabled(can_dispatch)
            self._daily_action_button.setEnabled(can_dispatch)
            self._briefing_action_button.setEnabled(can_dispatch)
            self._triage_action_button.setEnabled(can_dispatch)
            self._study_action_button.setEnabled(can_dispatch)
            self._cancel_button.setEnabled(state.cancellable)
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
            self._refresh_status(
                state.status_text(
                    mode=self._selected_mode,
                    profile=self._selected_profile,
                )
            )

        def _append_user(self, prompt: str, attachments: list[Path]) -> None:
            lines = [f"Tú > {prompt}"]
            if attachments:
                joined = ", ".join(path.name or str(path) for path in attachments)
                lines.append(f"Adjuntos > {joined}")
            self._append_block("\n".join(lines))

        def _append_assistant_prefix(self) -> None:
            self._transcript.moveCursor(QTextCursor.MoveOperation.End)
            self._transcript.insertPlainText("ADV ARCHON > ")
            self._transcript.ensureCursorVisible()

        def _append_assistant_chunk(self, chunk: str) -> None:
            self._current_chunked_reply = True
            self._transcript.moveCursor(QTextCursor.MoveOperation.End)
            self._transcript.insertPlainText(chunk)
            self._transcript.ensureCursorVisible()

        def _append_tool_event(self, name: str, arguments: object) -> None:
            self._active_tool_names = merge_recent_items(self._active_tool_names, [name], limit=8)
            self._refresh_sources_view()
            if not config.ui.show_tool_input:
                return
            self._append_context_line(f"[tool:{name}] {arguments}")

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
                self._refresh_sources_view()
                return
            self._context_view.setPlainText(str(snapshot))
            self._refresh_sources_view()

        def _handle_prompt_finished(self, text: str) -> None:
            if not self._current_chunked_reply and text:
                self._transcript.moveCursor(QTextCursor.MoveOperation.End)
                self._transcript.insertPlainText(text)
            self._transcript.moveCursor(QTextCursor.MoveOperation.End)
            self._transcript.insertPlainText("\n\n")
            self._transcript.ensureCursorVisible()
            self._remember_desktop_history(text)
            self._attachments = []
            self._render_attachments()
            self._set_busy(False)

        def _handle_import_finished(self, result: object) -> None:
            scanned = getattr(result, "scanned_files", 0)
            indexed = getattr(result, "indexed_files", 0)
            failed = getattr(result, "failed_files", 0)
            pending = getattr(result, "pending_files", 0)
            self._append_system(
                "Conocimiento actualizado. "
                f"Escaneados: {scanned} | indexados: {indexed} | fallidos: {failed} | "
                f"pendientes: {pending}"
            )
            self._set_busy(False)

        def _handle_worker_error(self, message: str) -> None:
            self._append_system(f"Error: {message}")
            self._transcript.moveCursor(QTextCursor.MoveOperation.End)
            self._transcript.insertPlainText("\n\n")
            self._set_busy(False)

        def _handle_worker_cancelled(self, message: str) -> None:
            self._append_system(message)
            self._transcript.moveCursor(QTextCursor.MoveOperation.End)
            self._transcript.insertPlainText("\n\n")
            self._set_busy(False)

        def _handle_shutdown_finished(self) -> None:
            self._append_context_line("Backend desktop detenido. Cerrando ventana…")

        def _handle_backend_thread_finished(self) -> None:
            self._backend_thread = None
            self._backend_worker = None
            if self._close_requested:
                self.close()

        def _append_system(self, message: str) -> None:
            self._append_block(f"Sistema > {message}")

        def _append_context_line(self, message: str) -> None:
            current = self._context_view.toPlainText().strip()
            merged = f"{current}\n{message}" if current else message
            self._context_view.setPlainText(merged)

        def _append_block(self, message: str) -> None:
            current = self._transcript.toPlainText().strip()
            merged = f"{current}\n\n{message}" if current else message
            self._transcript.setPlainText(merged)
            self._transcript.moveCursor(QTextCursor.MoveOperation.End)
            self._transcript.ensureCursorVisible()

        def _cancel_active_task(self) -> None:
            if not self._busy_state.cancellable:
                return
            self.cancel_requested.emit()

        def _refresh_sources_view(self) -> None:
            snapshot = self._last_snapshot
            memory_hits = snapshot.memory_hits if snapshot is not None else ()
            knowledge_hits = snapshot.knowledge_hits if snapshot is not None else ()
            self._sources_view.setPlainText(
                format_sources_summary(
                    tool_names=self._active_tool_names,
                    memory_hits=memory_hits,
                    knowledge_hits=knowledge_hits,
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
                    self._recent_history_entries,
                    [entry],
                    limit=12,
                )
                self._history_list.clear()
                self._history_list.addItems(self._recent_history_entries)
            if self._pending_attachments:
                labels = [path.name or str(path) for path in self._pending_attachments]
                self._recent_attachment_entries = merge_recent_items(
                    self._recent_attachment_entries,
                    labels,
                    limit=12,
                )
                self._recent_attachments_list.clear()
                self._recent_attachments_list.addItems(self._recent_attachment_entries)
            self._pending_prompt = ""
            self._pending_attachments = []

    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    resolved_logo = logo_path()
    if resolved_logo.exists():
        app.setWindowIcon(QIcon(str(resolved_logo)))
    window = DesktopWindow()
    window.show()
    return app.exec()
