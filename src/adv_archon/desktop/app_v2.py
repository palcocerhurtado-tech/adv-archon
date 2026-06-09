# mypy: ignore-errors
"""
app_v2.py — Glue layer between RedesignedMainWindow and DesktopRuntimeWorker.

Drop-in replacement for the DesktopWindow instantiation at the bottom of
launch_desktop_app.  The old DesktopWindow is left untouched.
"""
from __future__ import annotations

import os
import threading
from importlib.util import find_spec
from pathlib import Path

from adv_archon.core.config import AppConfig

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

if PYSIDE6_AVAILABLE:
    # ── Confirm bridge ─────────────────────────────────────────────────────────
    # Same pattern as ConfirmBridge in app.py but standalone.
    from PySide6.QtCore import QObject, Qt, QThread, Signal
    from PySide6.QtWidgets import QApplication, QMessageBox

    from adv_archon.desktop.redesigned_main_window import RedesignedMainWindow
    from adv_archon.desktop.workers import DesktopBusyState, DesktopRuntimeWorker

    class _ConfirmBridge(QObject):
        requested = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self._accepted = False
            self._waiting: threading.Event | None = None

        def ask(self, question: str) -> bool:
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

    # ── Main v2 window ─────────────────────────────────────────────────────────

    class DesktopWindowV2(RedesignedMainWindow):
        """
        RedesignedMainWindow wired to DesktopRuntimeWorker.

        Provides the same external API as DesktopWindow so launch_desktop_app
        can swap the class without changes to the rest of app.py:
          - _start_backend()
          - _stop_background_threads()
          - closeEvent()
        """

        # Cross-thread signals → worker slots
        # (queued automatically when worker lives in a different QThread)
        _worker_run_prompt  = Signal(str, object)   # (text, list[str])
        _worker_set_mode    = Signal(str)
        _worker_set_model   = Signal(str)
        _worker_cancel      = Signal()
        _worker_shutdown    = Signal()
        _worker_select_exp  = Signal(object)        # Expediente dataclass

        def __init__(
            self,
            *,
            config: AppConfig,
            project_root: Path,
            system_prompt: str,
            incognito: bool = False,
        ) -> None:
            super().__init__()
            self._config = config
            self._close_requested = False

            # ── Confirm bridge ─────────────────────────────────────────────────
            self._confirm_bridge = _ConfirmBridge()
            self._confirm_bridge.requested.connect(self._show_confirm_dialog)

            # ── Worker + thread ────────────────────────────────────────────────
            self._backend_thread: QThread | None = QThread(self)
            self._backend_thread.setObjectName("adv-archon-v2-backend")
            self._backend_worker: DesktopRuntimeWorker | None = DesktopRuntimeWorker(
                config=config,
                project_root=project_root,
                system_prompt=system_prompt,
                confirm=self._confirm_bridge.ask,
                incognito=incognito,
                initial_mode=config.llm.mode,
                initial_profile="general",
            )
            self._backend_worker.moveToThread(self._backend_thread)

            # UI → Worker (queued across thread boundary)
            self._worker_run_prompt.connect(self._backend_worker.run_prompt)
            self._worker_set_mode.connect(self._backend_worker.set_mode)
            self._worker_set_model.connect(self._backend_worker.set_ollama_model)
            self._worker_cancel.connect(
                self._backend_worker.cancel_prompt,
                Qt.ConnectionType.DirectConnection,
            )
            self._worker_shutdown.connect(self._backend_worker.shutdown)
            self._worker_select_exp.connect(self._backend_worker.on_expediente_selected)

            # Worker → UI
            self._backend_worker.chunk.connect(self.receive_chunk)
            self._backend_worker.tool.connect(
                lambda name, _args: self.receive_tool_call(name)
            )
            self._backend_worker.prompt_finished.connect(
                lambda _text: self.receive_final()
            )
            self._backend_worker.ready.connect(self._on_backend_ready)
            self._backend_worker.failed.connect(self._on_worker_failed)
            self._backend_worker.cancelled.connect(self._on_worker_cancelled)
            self._backend_worker.busy_state_changed.connect(self._on_busy_state_changed)
            self._backend_worker.shutdown_finished.connect(self._on_shutdown_finished)

            # Thread lifecycle
            self._backend_thread.started.connect(self._backend_worker.initialize)
            self._backend_thread.finished.connect(self._backend_worker.deleteLater)
            self._backend_thread.finished.connect(self._backend_thread.deleteLater)
            self._backend_thread.finished.connect(self._on_thread_finished)

            # Window → Worker (application-level)
            self.prompt_submitted.connect(self._forward_prompt)
            self.command_triggered.connect(self._forward_command)

            # Initial UI state
            self.set_mode(config.llm.mode)
            self.set_model(config.llm.ollama_model or "ollama")
            self._composer.set_enabled_input(False)   # disabled until backend ready

            # Populate sidebar from DB (best-effort)
            self._try_load_expedientes()

        # ── Worker event handlers ──────────────────────────────────────────────

        def _on_backend_ready(self, greeting: str) -> None:
            """Backend initialised — enable input and optionally show greeting."""
            self._composer.set_enabled_input(True)
            if greeting:
                self._chat.add_message("agent", greeting)
            # Refresh expediente list in case new ones arrived during init
            self._try_load_expedientes()

        def _on_worker_failed(self, error: str) -> None:
            self._chat.finish_stream()
            self._chat.add_message("agent", f"⚠ Error al inicializar: {error}")
            self._composer.set_enabled_input(True)

        def _on_worker_cancelled(self, _msg: str) -> None:
            self._chat.finish_stream()
            self._composer.set_enabled_input(True)

        def _on_busy_state_changed(self, state: DesktopBusyState) -> None:
            if state.detail:
                self._composer.set_status(state.detail)
            elif state.task == "initializing":
                self._composer.set_status("Preparando motor local…")
            elif not state.backend_ready:
                self._composer.set_status("Iniciando…")
            else:
                self._composer.set_status("")

        def _on_shutdown_finished(self) -> None:
            if self._backend_thread is not None:
                self._backend_thread.quit()

        def _on_thread_finished(self) -> None:
            self._backend_thread = None
            self._backend_worker = None
            self.close()

        # ── UI → Worker forwarding ─────────────────────────────────────────────

        def _forward_prompt(self, text: str, attachments: list[Path]) -> None:
            self._worker_run_prompt.emit(text, [str(p) for p in attachments])

        def _forward_command(self, cmd_id: str) -> None:
            if cmd_id == "mode_local":
                self._worker_set_mode.emit("local")
            elif cmd_id == "mode_cloud":
                self._worker_set_mode.emit("cloud")
            elif cmd_id.startswith("exp_open:"):
                self._activate_expediente(cmd_id.split(":", 1)[1])

        # ── Expediente handling ────────────────────────────────────────────────

        def _activate_expediente(self, exp_id: str) -> None:
            """Look up full expediente, update UI + notify worker."""
            try:
                from adv_archon.core.expediente import ExpedienteStore
                store = ExpedienteStore(self._data_dir() / "expedientes.db")
                exp = store.get(exp_id)
                if exp is None:
                    return
                self._worker_select_exp.emit(exp)
                self.set_expediente({
                    "id": exp.id,
                    "title": exp.title,
                    "municipality": exp.municipality,
                    "address": exp.address,
                    "province": exp.province,
                    "case_type": exp.case_type,
                    "status": exp.status,
                    "extracted_params": exp.extracted_params,
                    "site_context": exp.site_context,
                })
            except Exception:
                pass

        def _try_load_expedientes(self) -> None:
            """Populate the left-panel list from the local DB (best-effort)."""
            try:
                from adv_archon.core.expediente import ExpedienteStore
                db_path = self._data_dir() / "expedientes.db"
                if not db_path.exists():
                    return
                store = ExpedienteStore(db_path)
                exps = store.list_all()
                self.set_expediente_list([
                    {
                        "id": e.id,
                        "title": e.title,
                        "municipality": e.municipality,
                        "address": e.address,
                        "province": e.province,
                        "case_type": e.case_type,
                        "status": e.status,
                        "extracted_params": e.extracted_params,
                        "site_context": e.site_context,
                    }
                    for e in exps
                ])
            except Exception:
                pass

        @staticmethod
        def _data_dir() -> Path:
            return Path(os.getenv("ADV_ARCHON_HOME", str(Path.home() / ".adv-archon")))

        # ── Dialog helpers ─────────────────────────────────────────────────────

        def _show_confirm_dialog(self, question: str) -> None:
            mb = QMessageBox(self)
            mb.setWindowTitle("ADV ARCHON")
            mb.setText(question)
            mb.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            accepted = mb.exec() == QMessageBox.StandardButton.Yes
            self._confirm_bridge.resolve(accepted)

        # ── Public API expected by launch_desktop_app ──────────────────────────

        def _start_backend(self) -> None:
            if self._backend_thread is not None and not self._backend_thread.isRunning():
                self._backend_thread.start()

        def _stop_background_threads(self) -> None:
            self._worker_cancel.emit()
            self._worker_shutdown.emit()

        def closeEvent(self, ev) -> None:  # type: ignore[override]
            if self._backend_thread is None or not self._backend_thread.isRunning():
                ev.accept()
                return
            if self._close_requested:
                QApplication.quit()
                ev.accept()
                return
            self._close_requested = True
            ev.ignore()
            self._stop_background_threads()
