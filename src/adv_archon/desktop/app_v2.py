# mypy: ignore-errors
"""
app_v2.py — Glue layer between RedesignedMainWindow and DesktopRuntimeWorker.

Drop-in replacement for the DesktopWindow instantiation at the bottom of
launch_desktop_app.  The old DesktopWindow is left untouched.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import threading
from contextlib import suppress
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from adv_archon.core.config import AppConfig

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

if PYSIDE6_AVAILABLE:
    # ── Confirm bridge ─────────────────────────────────────────────────────────
    # Same pattern as ConfirmBridge in app.py but standalone.
    from PySide6.QtCore import QObject, Qt, QThread, QTimer, QUrl, Signal
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

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

    def _build_expediente_analysis(exp: Any) -> dict[str, Any]:
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
                "Falta contexto legal completo. Debe resolverse parcela, PGOU y fuentes "
                "sectoriales antes de emitir criterio profesional."
            )
        elif {"pending_review", "missing"} & statuses:
            verdict = "revisar"
            verdict_label = "REVISAR"
            summary = (
                "Hay comprobaciones pendientes o datos insuficientes. Requiere revisión "
                "técnica antes de cerrar el informe."
            )
        elif "conditional" in statuses:
            verdict = "condicionado"
            verdict_label = "CONDICIONADO"
            summary = (
                "Se detectan condiciones o afecciones que deben contrastarse con el "
                "expediente y la administración competente."
            )
        else:
            verdict = "viable"
            verdict_label = "VIABLE"
            summary = (
                "No se detectan alertas sectoriales relevantes en el cribado preliminar. "
                "Confirmar siempre ordenanza y plano de proyecto."
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
        if getattr(exp, "plan_path", ""):
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

    class _ExportWorker(QObject):
        exported = Signal(str)
        failed = Signal(str)
        finished = Signal()

        def __init__(self, exp: Any, output_path: Path) -> None:
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

    class _AutopilotWorker(QObject):
        progress = Signal(object, str)
        completed = Signal(object)
        failed = Signal(object, str)
        finished = Signal()

        def __init__(self, exp: Any, data_root: Path) -> None:
            super().__init__()
            self._exp = exp
            self._data_root = data_root
            self._run_id = datetime.now().strftime("%Y%m%d%H%M%S")

        def run(self) -> None:
            try:
                from adv_archon.core.agent_plan import (
                    append_agent_event,
                    build_expediente_agent_plan,
                )
                from adv_archon.core.expediente_autopilot import (
                    AutopilotStore,
                    append_autopilot_checkpoint,
                    build_expediente_autopilot,
                )

                plan = build_expediente_autopilot(self._exp)
                AutopilotStore(self._data_root / "autopilot.db").save_run(
                    plan,
                    run_id=self._run_id,
                )
                exp = dataclasses.replace(
                    self._exp,
                    status="autopilot_en_curso",
                    agent_history=append_autopilot_checkpoint(
                        getattr(self._exp, "agent_history", ""),
                        plan,
                        run_id=self._run_id,
                    ),
                )
                self.progress.emit(exp, plan.current_step or plan.summary)

                events = [
                    ("resolve-location", "Resolver ubicación y parcela"),
                    ("query-catastro", "Consultar Catastro"),
                    ("sectorial-sources", "Comprobar fuentes sectoriales"),
                    ("pgou-normativa", "Buscar normativa PGOU"),
                    ("preliminary-dictamen", "Generar dictamen preliminar"),
                    ("architect-review", "Preparar revisión de arquitecto"),
                ]
                history = exp.agent_history
                for code, title in events:
                    status = "completed"
                    message = f"{title}: paso procesado por ADV ARCHON Autopilot."
                    if code == "plan-document" and not getattr(exp, "plan_path", ""):
                        status = "needs_review"
                    history = append_agent_event(
                        history,
                        step_code=code,
                        title=title,
                        status=status,
                        message=message,
                        run_id=self._run_id,
                    )
                    exp = dataclasses.replace(exp, agent_history=history)
                    self.progress.emit(exp, message)

                if not str(getattr(exp, "analysis_result", "") or "").strip():
                    analysis = _build_expediente_analysis(exp)
                    exp = dataclasses.replace(
                        exp,
                        analysis_result=json.dumps(analysis, ensure_ascii=False),
                    )

                final_plan = build_expediente_agent_plan(exp, include_history=False)
                final_status = (
                    "requiere_revision"
                    if final_plan.verdict in {"blocked", "review"}
                    else "analizado"
                )
                exp = dataclasses.replace(exp, status=final_status)
                self.completed.emit(exp)
            except Exception as exc:
                exp = dataclasses.replace(self._exp, status="autopilot_bloqueado")
                self.failed.emit(exp, str(exc))
            finally:
                self.finished.emit()

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
        _worker_run_prompt   = Signal(str, object)   # (text, list[str])
        _worker_set_mode     = Signal(str)
        _worker_set_model    = Signal(str)
        _worker_set_profile  = Signal(str)
        _worker_cancel       = Signal()
        _worker_shutdown     = Signal()
        _worker_select_exp   = Signal(object)        # Expediente dataclass

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
            self._project_root = project_root
            self._close_requested = False
            self._active_threads: list[tuple[QThread, QObject]] = []
            self._expediente_workspace: dict[str, Any] = {}
            self._research_workspace: dict[str, Any] = {}

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
            self._worker_set_profile.connect(self._backend_worker.set_profile)
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
            self._backend_worker.prompt_finished.connect(self._on_prompt_finished)
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

            # Profile list → sidebar
            profile_names = list(config.profiles.definitions.keys()) or ["general"]
            active_profile = config.profiles.default_profile or "general"
            self._left.set_profiles(profile_names, active_profile)
            self._left.profile_changed.connect(self._on_profile_changed)

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

        def _on_prompt_finished(self, _text: str) -> None:
            self.receive_final()
            self._try_load_expedientes()
            self._refresh_active_expediente()

        def _on_busy_state_changed(self, state: DesktopBusyState) -> None:
            if state.detail:
                self._composer.set_status(state.detail)
                if state.task == "prompt":
                    self._chat.update_stream_status(state.detail)
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

        def _on_profile_changed(self, profile: str) -> None:
            self._worker_set_profile.emit(profile)
            self._left.set_active_profile(profile)

        # ── UI → Worker forwarding ─────────────────────────────────────────────

        def _forward_prompt(self, text: str, attachments: list[Path]) -> None:
            self._worker_run_prompt.emit(text, [str(p) for p in attachments])

        def _forward_command(self, cmd_id: str) -> None:  # noqa: C901
            if cmd_id == "theme_toggle":
                self._toggle_theme()
                return
            # Mode changes — update worker AND redraw UI
            if cmd_id in ("mode_local", "mode_cloud"):
                new_mode = cmd_id.split("_", 1)[1]
                self._worker_set_mode.emit(new_mode)
                self.set_mode(new_mode)
                return
            # Expediente activation
            if cmd_id.startswith("exp_open:"):
                self._activate_expediente(cmd_id.split(":", 1)[1])
                self._open_expediente_workspace(selected_id=cmd_id.split(":", 1)[1])
                return
            if cmd_id == "exp_open":
                self._open_expediente_workspace()
                return
            if cmd_id == "exp_list":
                self._try_load_expedientes()
                self._open_expediente_workspace()
                return
            # New expediente
            if cmd_id == "exp_new":
                self._open_expediente_workspace(open_new=True)
                return
            # Shortcuts reference
            if cmd_id == "shortcuts":
                self._chat.add_message(
                    "agent",
                    "**Atajos de teclado**\n\n"
                    "| Atajo | Acción |\n|---|---|\n"
                    "| ⌘K | Paleta de comandos |\n"
                    "| ⌘⇧L | Panel izquierdo |\n"
                    "| ⌘⇧R | Panel derecho |\n"
                    "| ⌘N | Nuevo expediente |\n"
                    "| ⌘O | Abrir expediente |\n"
                    "| ⌘E | Exportar PDF |\n"
                    "| ↩ | Enviar mensaje |\n"
                    "| ⇧↩ | Nueva línea |",
                )
                return
            # Commands that forward to agent as a prompt
            _as_prompt = {
                "pgou_analyze":    "Analiza el expediente activo con el PGOU.",
                "pgou_params":     "Extrae los parámetros urbanísticos del expediente activo.",
                "review_pro":      "Realiza una revisión pro del expediente activo.",
                "edificabilidad":  "Calcula la edificabilidad del expediente activo.",
                "doc_pdf":         "Genera un informe PDF del expediente activo.",
                "doc_docx":        "Genera un informe DOCX del expediente activo.",
                "doc_xlsx":        "Genera un libro XLSX auditable del expediente activo.",
                "doc_informe":     "Genera el informe integrado del expediente activo.",
                "doc_memoria":     "Redacta la Memoria Descriptiva del expediente activo.",
                "boe_search":      "Busca en el BOE la normativa relevante para el expediente activo.",  # noqa: E501
            }
            if cmd_id in _as_prompt and self._backend_worker and self._backend_worker._backend_ready:  # noqa: E501
                prompt = _as_prompt[cmd_id]
                self._chat.add_message("user", prompt)
                self._chat.start_stream()
                self._composer.set_enabled_input(False)
                self._worker_run_prompt.emit(prompt, [])
                return
            real_workspaces = {
                "research": self._open_research_workspace,
                "training": self._open_training_workspace,
                "studio_demo": self._open_studio_demo_workspace,
                "qa_system": self._open_system_status_workspace,
                "system_status": self._open_system_status_workspace,
                "beta_guide": self._open_beta_guide_workspace,
                "settings": self._open_settings_workspace,
            }
            if cmd_id in real_workspaces:
                real_workspaces[cmd_id]()
                return
            # Status commands
            if cmd_id == "pgou_status":
                self._chat.add_message(
                    "agent", "¿Sobre qué municipio quieres consultar el estado del PGOU?"
                )
                return
            # Settings stub
            if cmd_id in ("settings", "mode_local", "mode_cloud", "model_select"):
                self._composer.set_status(f"Comando: {cmd_id}")
                return
            # Everything else → just update the status bar so the user sees it fired
            self._composer.set_status(f"⌘ {cmd_id}")

        # ── Real v2 workspaces ────────────────────────────────────────────────

        def _open_expediente_workspace(
            self,
            selected_id: str | None = None,
            *,
            open_new: bool = False,
        ) -> None:
            from adv_archon.core.document_store import DocumentStore
            from adv_archon.core.expediente import ExpedienteStore
            from adv_archon.desktop.expediente_panel import (
                ExpedienteDetailPanel,
                ExpedienteListPanel,
                NewExpedienteDialog,
            )

            data_dir = self._data_dir()
            store = ExpedienteStore(data_dir / "expedientes.db")
            document_store = DocumentStore(data_dir / "documents.db")

            page = QWidget()
            page.setObjectName("expedienteWorkspace")
            layout = QHBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            def refresh_list(select_id: str | None = None) -> None:
                exps = store.list_all()
                list_panel.populate(exps)
                self._try_load_expedientes()
                if select_id:
                    for row, exp in enumerate(exps):
                        if exp.id == select_id:
                            list_panel._list.setCurrentRow(row)
                            detail_panel.load_expediente(exp)
                            self._activate_expediente(exp.id)
                            break

            def load_exp(eid: str) -> Any | None:
                exp = store.get(eid)
                if exp is not None:
                    detail_panel.load_expediente(exp)
                    self._activate_expediente(exp.id)
                return exp

            def new_exp() -> None:
                dialog = NewExpedienteDialog(self)
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                exp = store.create(
                    title=dialog.title_text(),
                    address=dialog.address_text(),
                    notes=dialog.notes_text(),
                    case_type=dialog.case_type(),
                )
                refresh_list(exp.id)
                self._composer.set_status(f"Expediente creado: {exp.title}")

            def delete_exp(eid: str) -> None:
                exp = store.get(eid)
                if exp is None:
                    return
                reply = QMessageBox.question(
                    self,
                    "Eliminar expediente",
                    f"¿Eliminar «{exp.title}»?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    store.delete(eid)
                    detail_panel.clear()
                    refresh_list()

            def attach_plan(eid: str) -> None:
                path, _filter = QFileDialog.getOpenFileName(
                    self,
                    "Adjuntar plano arquitectónico",
                    str(Path.home()),
                    "Planos (*.pdf *.dwg *.dxf *.png *.jpg *.jpeg);;Todos (*)",
                )
                if not path:
                    return
                exp = store.get(eid)
                if exp is None:
                    return
                updated = dataclasses.replace(exp, plan_path=path)
                store.update(updated)
                detail_panel.load_expediente(updated)
                self._activate_expediente(updated.id)
                self._right.add_attachment(Path(path))
                self._composer.set_status(f"Plano adjuntado: {Path(path).name}")

            def analyze_exp(eid: str) -> None:
                exp = store.get(eid)
                if exp is None:
                    return
                analysis = _build_expediente_analysis(exp)
                updated = dataclasses.replace(
                    exp,
                    analysis_result=json.dumps(analysis, ensure_ascii=False),
                    status="analizado",
                )
                store.update(updated)
                detail_panel.load_expediente(updated)
                self._activate_expediente(updated.id)
                self._composer.set_status(
                    f"Dictamen preliminar: {analysis['verdict_label']}"
                )

            def export_pdf(eid: str) -> None:
                exp = store.get(eid)
                if exp is None:
                    return
                if not exp.analysis_result:
                    analysis = _build_expediente_analysis(exp)
                    exp = dataclasses.replace(
                        exp,
                        analysis_result=json.dumps(analysis, ensure_ascii=False),
                        status="analizado",
                    )
                    store.update(exp)
                safe_title = re.sub(
                    r"[^a-zA-Z0-9_-]+",
                    "_",
                    exp.title,
                ).strip("_").lower()
                stamp = datetime.now().strftime("%Y%m%d_%H%M")
                output = Path.home() / "Desktop" / f"informe_adv_archon_{safe_title}_{stamp}.pdf"
                detail_panel.set_operation_busy(True, "Generando informe PDF profesional…")
                thread = QThread(self)
                worker = _ExportWorker(exp, output)
                worker.moveToThread(thread)
                thread.started.connect(worker.run)

                def on_exported(path_text: str) -> None:
                    path = Path(path_text)
                    updated = dataclasses.replace(
                        exp,
                        report_path=str(path),
                        status="informe_listo",
                    )
                    store.update(updated)
                    detail_panel.load_expediente(updated)
                    self._activate_expediente(updated.id)
                    detail_panel.set_operation_busy(False)
                    self._composer.set_status(f"Informe exportado: {path.name}")
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

                def on_failed(message: str) -> None:
                    detail_panel.set_operation_busy(False)
                    QMessageBox.warning(self, "Exportar PDF", message)

                def cleanup() -> None:
                    with suppress(ValueError):
                        self._active_threads.remove((thread, worker))

                worker.exported.connect(on_exported)
                worker.failed.connect(on_failed)
                worker.finished.connect(worker.deleteLater)
                worker.finished.connect(thread.quit)
                thread.finished.connect(cleanup)
                thread.finished.connect(thread.deleteLater)
                self._active_threads.append((thread, worker))
                thread.start()

            def run_agent(eid: str) -> None:
                exp = store.get(eid)
                if exp is None:
                    return
                detail_panel.set_operation_busy(
                    True,
                    "ARCHON ejecutando Autopilot del expediente…",
                )
                thread = QThread(self)
                worker = _AutopilotWorker(exp, data_dir)
                worker.moveToThread(thread)
                thread.started.connect(worker.run)

                def on_progress(updated: Any, message: str) -> None:
                    store.update(updated)
                    refresh_list(updated.id)
                    detail_panel.load_expediente(updated)
                    self._composer.set_status(message)

                def on_completed(updated: Any) -> None:
                    store.update(updated)
                    refresh_list(updated.id)
                    detail_panel.load_expediente(updated)
                    detail_panel.set_operation_busy(False)
                    self._activate_expediente(updated.id)
                    self._composer.set_status("Expediente Autopilot completado.")

                def on_failed(updated: Any, message: str) -> None:
                    store.update(updated)
                    refresh_list(updated.id)
                    detail_panel.load_expediente(updated)
                    detail_panel.set_operation_busy(False)
                    QMessageBox.warning(self, "Autopilot", message)

                def cleanup() -> None:
                    with suppress(ValueError):
                        self._active_threads.remove((thread, worker))

                worker.progress.connect(on_progress)
                worker.completed.connect(on_completed)
                worker.failed.connect(on_failed)
                worker.finished.connect(worker.deleteLater)
                worker.finished.connect(thread.quit)
                thread.finished.connect(cleanup)
                thread.finished.connect(thread.deleteLater)
                self._active_threads.append((thread, worker))
                thread.start()

            def talk_exp(eid: str) -> None:
                exp = store.get(eid)
                if exp is None:
                    return
                self._activate_expediente(exp.id)
                self.show_chat_workspace()
                self._chat.add_message(
                    "agent",
                    f"Contexto activo: **{exp.title}**. Pregúntame por riesgos, "
                    "PGOU, fuentes o próximos pasos.",
                )

            def review_exp(eid: str, action: str) -> None:
                exp = store.get(eid)
                if exp is None:
                    return
                from adv_archon.core.expediente_quality import review_state_json

                note: str | None = None
                resolved_action: str | None = action
                if action == "note":
                    note, ok = QInputDialog.getMultiLineText(
                        self,
                        "Nota de revisión",
                        "Añade una nota del arquitecto:",
                        "",
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
                refresh_list(updated.id)

            def step_action(eid: str, step_code: str, action: str) -> None:
                exp = store.get(eid)
                if exp is None:
                    return
                from adv_archon.core.agent_plan import (
                    append_agent_event,
                    update_agent_step_review,
                )

                messages = {
                    "validate": "Paso validado por arquitecto.",
                    "accept-warning": "Advertencia aceptada por arquitecto.",
                    "repeat": "Repetición solicitada por arquitecto.",
                    "include": "Paso incluido en informe.",
                    "exclude": "Paso excluido del informe.",
                }
                message = messages.get(action, "Decisión de arquitecto registrada.")
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
                        status="pending" if action == "repeat" else "completed",
                        message=message,
                    ),
                )
                store.update(updated)
                detail_panel.load_expediente(updated)
                refresh_list(updated.id)
                if action == "repeat":
                    QTimer.singleShot(80, lambda: run_agent(eid))

            def prepare_draft(eid: str) -> dict[str, Any]:
                exp = store.get(eid)
                if exp is None:
                    return {}
                from adv_archon.core.expediente_documents import ensure_expediente_draft

                return ensure_expediente_draft(document_store, exp).to_dict()

            def save_draft(eid: str, payload: dict[str, Any]) -> dict[str, Any]:
                from adv_archon.core.expediente_documents import (
                    save_edited_expediente_draft,
                )

                payload = dict(payload)
                payload["expediente_id"] = eid
                payload["kind"] = payload.get("kind") or "expediente"
                draft = save_edited_expediente_draft(document_store, payload)
                self._composer.set_status("Borrador de entrega guardado.")
                return draft.to_dict()

            def export_draft(eid: str, kind: str, payload: dict[str, Any]) -> str:
                del eid
                from adv_archon.core.expediente_documents import (
                    export_expediente_draft,
                    save_edited_expediente_draft,
                )
                from adv_archon.desktop.branding import logo_path

                draft = save_edited_expediente_draft(document_store, payload)
                output = export_expediente_draft(
                    draft,
                    kind,
                    Path.home() / "Desktop",
                    archon_logo_path=logo_path(),
                )
                document_store.mark_exported(draft.id, kind, output)
                self._composer.set_status(f"Documento exportado: {output.name}")
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))
                return str(output)

            detail_panel = ExpedienteDetailPanel(
                on_attach_plan=attach_plan,
                on_analyze=analyze_exp,
                on_export=export_pdf,
                on_talk=talk_exp,
                on_review=review_exp,
                on_run_agent=run_agent,
                on_agent_step_action=step_action,
                on_prepare_document=prepare_draft,
                on_save_document=save_draft,
                on_export_document=export_draft,
            )
            list_panel = ExpedienteListPanel(
                on_select=lambda eid: load_exp(eid),
                on_new=new_exp,
                on_delete=delete_exp,
            )
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            layout.addWidget(list_panel)
            layout.addWidget(sep)
            layout.addWidget(detail_panel, 1)
            self._expediente_workspace = {
                "store": store,
                "document_store": document_store,
                "list": list_panel,
                "detail": detail_panel,
            }

            self.show_workspace(
                "Expedientes",
                page,
                subtitle=(
                    "Nuevo expediente, plano, Autopilot, revisión profesional y "
                    "documento de entrega editable."
                ),
            )
            exps = store.list_all()
            list_panel.populate(exps)
            target_id = selected_id or (
                str((getattr(self, "_active_exp", {}) or {}).get("id") or "")
            )
            if exps:
                selected_row = 0
                if target_id:
                    for idx, exp in enumerate(exps):
                        if exp.id == target_id:
                            selected_row = idx
                            break
                list_panel._list.setCurrentRow(selected_row)
                detail_panel.load_expediente(exps[selected_row])
                self._activate_expediente(exps[selected_row].id)
            if open_new:
                QTimer.singleShot(80, new_exp)

        def _open_research_workspace(self) -> None:
            from adv_archon.desktop.document_intelligence_panel import (
                DocumentIntelligencePanel,
            )
            from adv_archon.desktop.draft_editor import DraftEditorWidget

            page = QWidget()
            layout = QHBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)

            left = QFrame()
            left.setObjectName("Panel")
            left_lay = QVBoxLayout(left)
            left_lay.setContentsMargins(14, 14, 14, 14)
            left_lay.setSpacing(10)
            question = QPlainTextEdit()
            question.setPlaceholderText(
                "Ej.: investiga este trabajo, extrae fórmulas y prepara DOCX/XLSX/PDF..."
            )
            question.setMinimumHeight(130)
            attachments_label = QLabel("Adjuntos: ninguno")
            attachments_label.setWordWrap(True)
            attach_btn = QPushButton("Adjuntar material")
            attach_btn.setObjectName("Ghost")
            run_btn = QPushButton("Ejecutar investigación")
            run_btn.setObjectName("Primary")
            left_lay.addWidget(QLabel("Brief de investigación"))
            left_lay.addWidget(question)
            left_lay.addWidget(attachments_label)
            row = QHBoxLayout()
            row.addWidget(attach_btn)
            row.addWidget(run_btn)
            left_lay.addLayout(row)
            result_view = QTextEdit()
            result_view.setReadOnly(True)
            result_view.setPlainText(
                "Research Workbench listo. Adjunta documentos o escribe un brief."
            )
            left_lay.addWidget(result_view, 1)
            layout.addWidget(left, 2)

            draft_editor = DraftEditorWidget()
            intelligence_panel = DocumentIntelligencePanel()
            right = QWidget()
            right_lay = QVBoxLayout(right)
            right_lay.setContentsMargins(0, 0, 0, 0)
            right_lay.setSpacing(10)
            right_lay.addWidget(draft_editor, 2)
            right_lay.addWidget(intelligence_panel, 1)
            export_row = QHBoxLayout()
            export_docx = QPushButton("DOCX")
            export_pdf = QPushButton("PDF")
            export_xlsx = QPushButton("XLSX")
            for btn in (export_docx, export_pdf, export_xlsx):
                btn.setObjectName("Ghost")
                btn.setEnabled(False)
                export_row.addWidget(btn)
            right_lay.addLayout(export_row)
            layout.addWidget(right, 1)

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
                for path in state["attachments"]:
                    self._right.add_attachment(Path(path))

            def choose_attachments() -> None:
                paths, _filter = QFileDialog.getOpenFileNames(
                    self,
                    "Adjuntar material de investigación",
                    str(Path.home()),
                    "Documentos (*.pdf *.docx *.pptx *.xlsx *.txt *.md *.png *.jpg);;Todos (*)",
                )
                if paths:
                    state["attachments"] = list(
                        dict.fromkeys([*state["attachments"], *paths])
                    )
                    render_attachments()
                    intelligence_panel.set_empty(
                        "Adjuntos listos. Ejecuta la investigación para detectar tablas, "
                        "fórmulas, magnitudes y borradores."
                    )

            def set_export_enabled(enabled: bool) -> None:
                for btn in (export_docx, export_pdf, export_xlsx):
                    btn.setEnabled(enabled)

            class _ResearchWorker(QObject):
                completed = Signal(object)
                failed = Signal(str)
                finished = Signal()

                def __init__(self, brief: str, attachments: list[str]) -> None:
                    super().__init__()
                    self._brief = brief
                    self._attachments = attachments

                def run(self) -> None:
                    try:
                        from adv_archon.core.research_workbench import (
                            run_research_workbench,
                        )

                        self.completed.emit(
                            run_research_workbench(
                                self._brief,
                                attachment_paths=self._attachments,
                                search_results_per_query=4,
                                fetch_top_results=2,
                            )
                        )
                    except Exception as exc:
                        self.failed.emit(str(exc))
                    finally:
                        self.finished.emit()

            def render_result(result: Any) -> str:
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
                brief = question.toPlainText().strip()
                if not brief:
                    self._composer.set_status("Escribe primero el brief.")
                    return
                if state["thread"] is not None:
                    return
                set_export_enabled(False)
                run_btn.setEnabled(False)
                result_view.setPlainText("Investigando fuentes y leyendo adjuntos…")
                thread = QThread(self)
                worker = _ResearchWorker(brief, list(state["attachments"]))
                worker.moveToThread(thread)
                thread.started.connect(worker.run)

                def done(result: Any) -> None:
                    state["result"] = result
                    result_view.setPlainText(render_result(result))
                    from adv_archon.core.document_draft import build_research_draft

                    draft = build_research_draft(result).to_dict()
                    draft_editor.load_draft(draft)
                    intelligence_panel.analyze_draft(
                        draft,
                        attachment_names=[
                            Path(path).name for path in state["attachments"]
                        ],
                    )
                    set_export_enabled(True)
                    self._composer.set_status(
                        f"Investigación lista: {getattr(result, 'evidence_count', 0)} evidencias."
                    )

                def failed(message: str) -> None:
                    result_view.setPlainText(
                        f"No se pudo completar la investigación:\n{message}"
                    )

                def cleanup() -> None:
                    state["thread"] = None
                    state["worker"] = None
                    run_btn.setEnabled(True)
                    with suppress(ValueError):
                        self._active_threads.remove((thread, worker))

                worker.completed.connect(done)
                worker.failed.connect(failed)
                worker.finished.connect(worker.deleteLater)
                worker.finished.connect(thread.quit)
                thread.finished.connect(cleanup)
                thread.finished.connect(thread.deleteLater)
                state["thread"] = thread
                state["worker"] = worker
                self._active_threads.append((thread, worker))
                thread.start()

            def export(kind: str) -> None:
                if state["result"] is None:
                    return
                from adv_archon.core.document_draft import DocumentDraft

                draft = DocumentDraft.from_dict(draft_editor.current_draft())
                output = Path.home() / "Desktop" / f"adv_archon_research_workbench.{kind}"
                if kind == "docx":
                    from adv_archon.core.docx_generator import generate_research_docx

                    generate_research_docx(draft, output)
                elif kind == "xlsx":
                    from adv_archon.core.xlsx_generator import generate_research_xlsx

                    generate_research_xlsx(draft, output)
                else:
                    from adv_archon.core.pdf_generator_v2 import generate_draft_pdf
                    from adv_archon.desktop.branding import logo_path

                    generate_draft_pdf(draft, output, archon_logo_path=logo_path())
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

            attach_btn.clicked.connect(choose_attachments)
            run_btn.clicked.connect(run_research)
            export_docx.clicked.connect(lambda: export("docx"))
            export_pdf.clicked.connect(lambda: export("pdf"))
            export_xlsx.clicked.connect(lambda: export("xlsx"))
            draft_editor.export_requested.connect(lambda kind: export(str(kind)))
            intelligence_panel.export_requested.connect(lambda kind: export(str(kind)))

            self._research_workspace = state
            self.show_workspace(
                "Research Workbench",
                page,
                subtitle=(
                    "Investiga en profundidad, lee adjuntos, detecta fórmulas/tablas "
                    "y prepara entregables DOCX, XLSX o PDF."
                ),
            )

        def _open_training_workspace(self) -> None:
            from adv_archon.core.training_lab import (
                build_training_lab_status,
                default_export_path,
                default_synthetic_dataset_path,
                default_templates_path,
                export_feedback_dataset,
                render_training_lab_status,
            )

            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            view = QTextEdit()
            view.setReadOnly(True)
            data_dir = self._data_dir()

            def status_text() -> str:
                status = build_training_lab_status(
                    feedback_db=data_dir / "feedback.db",
                    templates_path=default_templates_path(self._project_root),
                    synthetic_dataset_path=default_synthetic_dataset_path(data_dir),
                )
                return render_training_lab_status(status)

            view.setPlainText(status_text())
            buttons = QHBoxLayout()
            refresh = QPushButton("Actualizar")
            export_btn = QPushButton("Exportar dataset real")
            for btn in (refresh, export_btn):
                btn.setObjectName("Ghost")
                buttons.addWidget(btn)
            buttons.addStretch(1)
            layout.addWidget(view, 1)
            layout.addLayout(buttons)

            def export_dataset() -> None:
                output = default_export_path()
                result = export_feedback_dataset(
                    feedback_db=data_dir / "feedback.db",
                    output_path=output,
                )
                view.setPlainText(status_text() + f"\n\nExportado: {result.output_path}")
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(output.parent)))

            refresh.clicked.connect(lambda: view.setPlainText(status_text()))
            export_btn.clicked.connect(export_dataset)
            self.show_workspace(
                "Training Lab",
                page,
                subtitle="Dataset real, ejemplos aprobados y preparación local para fine-tuning.",
            )

        def _open_system_status_workspace(self) -> None:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            view = QTextEdit()
            view.setReadOnly(True)
            view.setPlainText("Pulsa “Diagnóstico rápido” para medir la arquitectura local.")
            buttons = QHBoxLayout()
            quick = QPushButton("Diagnóstico rápido")
            quick.setObjectName("Primary")
            buttons.addWidget(quick)
            buttons.addStretch(1)
            layout.addWidget(view, 1)
            layout.addLayout(buttons)

            def run_profile() -> None:
                view.setPlainText("Midiendo Ollama, SQLite, workers y PDF…")
                try:
                    from adv_archon.core.performance_profiler import PerformanceProfiler

                    report = PerformanceProfiler(
                        self._config,
                        project_root=self._project_root,
                    ).run(include_official_sources=False)
                    view.setPlainText(report.render_markdown())
                except Exception as exc:
                    view.setPlainText(f"No se pudo ejecutar el profiler:\n{exc}")

            quick.clicked.connect(run_profile)
            self.show_workspace(
                "Estado del sistema",
                page,
                subtitle="Profiler local de Ollama, workers PySide6, SQLite y generación PDF.",
            )

        def _open_studio_demo_workspace(self) -> None:
            from adv_archon.core.demo import create_studio_demo_expedientes
            from adv_archon.core.expediente import ExpedienteStore

            data_dir = self._data_dir()
            store = ExpedienteStore(data_dir / "expedientes.db")
            demos = create_studio_demo_expedientes(store, data_dir=data_dir)
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            view = QTextEdit()
            view.setReadOnly(True)
            lines = [
                "ADV ARCHON Studio Demo",
                "",
                "Casos disponibles:",
            ]
            for idx, exp in enumerate(demos, start=1):
                lines.append(f"{idx}. {exp.title} · {exp.municipality} · {exp.status}")
            view.setPlainText("\n".join(lines))
            buttons = QHBoxLayout()
            open_exps = QPushButton("Abrir expedientes demo")
            open_exps.setObjectName("Primary")
            buttons.addWidget(open_exps)
            buttons.addStretch(1)
            layout.addWidget(view, 1)
            layout.addLayout(buttons)
            open_exps.clicked.connect(
                lambda: self._open_expediente_workspace(
                    selected_id=demos[0].id if demos else None
                )
            )
            self._try_load_expedientes()
            self.show_workspace(
                "Studio Demo",
                page,
                subtitle="Tres casos guiados con semáforo, riesgos, fuentes e informe.",
            )

        def _open_beta_guide_workspace(self) -> None:
            page = QTextEdit()
            page.setReadOnly(True)
            page.setPlainText(
                "Flujo beta recomendado:\n\n"
                "1. Crea un expediente.\n"
                "2. Adjunta plano o documentación.\n"
                "3. Ejecuta Autopilot.\n"
                "4. Revisa la bandeja profesional.\n"
                "5. Edita el documento de entrega.\n"
                "6. Exporta PDF, DOCX o XLSX."
            )
            self.show_workspace("Guía beta", page)

        def _open_settings_workspace(self) -> None:
            page = QTextEdit()
            page.setReadOnly(True)
            page.setPlainText(
                "Ajustes rápidos disponibles en la barra lateral:\n\n"
                f"- Modo actual: {self._mode}\n"
                f"- Modelo actual: {self._model_name}\n"
                "- Selector de perfil: panel izquierdo.\n"
                "- QA permisos: Estado del sistema.\n\n"
                "La pantalla de ajustes avanzada queda preparada para el siguiente sprint."
            )
            self.show_workspace("Ajustes", page)

        # ── Expediente handling ────────────────────────────────────────────────

        def _create_expediente(self) -> None:
            try:
                from adv_archon.core.expediente import ExpedienteStore
                from adv_archon.desktop.expediente_panel import NewExpedienteDialog
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Nuevo expediente",
                    f"No se pudo abrir el formulario de expediente: {exc}",
                )
                return

            dialog = NewExpedienteDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            try:
                store = ExpedienteStore(self._data_dir() / "expedientes.db")
                expediente = store.create(
                    title=dialog.title_text(),
                    address=dialog.address_text(),
                    notes=dialog.notes_text(),
                    case_type=dialog.case_type(),
                )
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Nuevo expediente",
                    f"No se pudo crear el expediente: {exc}",
                )
                return

            self._try_load_expedientes()
            self._activate_expediente(expediente.id)
            self._chat.add_message(
                "agent",
                f"Expediente **{expediente.title}** creado. "
                "Adjunta un plano o pide ejecutar Autopilot para continuar.",
            )

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

        def _refresh_active_expediente(self) -> None:
            active = getattr(self, "_active_exp", None)
            if not isinstance(active, dict):
                return
            exp_id = str(active.get("id") or "")
            if exp_id:
                self._activate_expediente(exp_id)

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
