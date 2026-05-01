# mypy: ignore-errors
"""
OllamaWarmupAgent — autonomous background agent that pre-loads the local model.

Pipeline (each step is a discrete agent action):
  1. health_check  — verify Ollama is reachable at all
  2. model_query   — confirm the configured model exists in /api/tags
  3. warmup_prompt — send a trivial prompt to force model weights into RAM
  4. report_ready  — emit timing metrics and signal completion

The agent runs in its own QThread so the desktop window stays responsive
during model loading, which can take 30-120 s for large models.
"""
from __future__ import annotations

import time
from importlib.util import find_spec
from typing import Any

PYSIDE6_AVAILABLE = find_spec("PySide6") is not None

QObject: Any = None
QThread: Any = None
Signal: Any = None

if PYSIDE6_AVAILABLE:
    from PySide6.QtCore import QObject, QThread, Signal


# ── Agent steps (each is a named action in the pipeline) ─────────────────────

_STEP_HEALTH  = "health_check"
_STEP_MODEL   = "model_query"
_STEP_WARMUP  = "warmup_prompt"
_STEP_DONE    = "report_ready"


if PYSIDE6_AVAILABLE:

    class OllamaWarmupAgent(QObject):  # type: ignore[misc]
        """
        Self-contained agent that orchestrates Ollama model pre-loading.

        Signals
        -------
        step_started(step_name)   — a pipeline step began
        progress(message)         — human-readable status update
        model_found(model_name)   — model confirmed in Ollama
        ready(elapsed_seconds)    — warmup complete, model is hot
        failed(error_message)     — unrecoverable error, model not loaded
        """
        step_started = Signal(str)
        progress     = Signal(str)
        model_found  = Signal(str)
        ready        = Signal(float)
        failed       = Signal(str)

        def __init__(
            self,
            *,
            base_url: str,
            model: str,
            timeout: float = 30.0,
            warmup_retries: int = 2,
        ) -> None:
            super().__init__()
            self._base_url      = base_url.rstrip("/")
            self._model         = model
            self._timeout       = timeout
            self._warmup_retries = warmup_retries

        # ── Entry point ───────────────────────────────────────────────────────
        def run(self) -> None:
            """Called by QThread.started signal — runs the full agent pipeline."""
            t0 = time.perf_counter()

            # Step 1 — health check
            if not self._step_health_check():
                return

            # Step 2 — confirm model exists
            if not self._step_model_query():
                return

            # Step 3 — warmup prompt
            if not self._step_warmup_prompt():
                return

            # Step 4 — report ready
            elapsed = time.perf_counter() - t0
            self.step_started.emit(_STEP_DONE)
            self.progress.emit(
                f"Modelo '{self._model}' listo en {elapsed:.1f}s"
            )
            self.ready.emit(elapsed)
            QThread.currentThread().quit()

        # ── Step 1: health check ──────────────────────────────────────────────
        def _step_health_check(self) -> bool:
            self.step_started.emit(_STEP_HEALTH)
            self.progress.emit("Verificando conexión con Ollama…")
            try:
                import httpx
                with httpx.Client(timeout=8.0) as client:
                    r = client.get(f"{self._base_url}/api/tags")
                    r.raise_for_status()
                self.progress.emit("Ollama responde — conexión OK")
                return True
            except Exception as exc:
                self.failed.emit(
                    f"Ollama no responde en {self._base_url}: {exc}. "
                    "Asegúrate de que 'ollama serve' está en ejecución."
                )
                QThread.currentThread().quit()
                return False

        # ── Step 2: confirm model ─────────────────────────────────────────────
        def _step_model_query(self) -> bool:
            self.step_started.emit(_STEP_MODEL)
            self.progress.emit(f"Buscando modelo '{self._model}'…")
            try:
                import httpx
                with httpx.Client(timeout=8.0) as client:
                    r = client.get(f"{self._base_url}/api/tags")
                    r.raise_for_status()
                    data = r.json()

                models = data.get("models", [])
                names = [m.get("name", "") for m in models if isinstance(m, dict)]

                # Flexible match: exact OR prefix (e.g. "qwen2.5" matches "qwen2.5:7b")
                matched = next(
                    (n for n in names if n == self._model or n.startswith(self._model + ":")),
                    None,
                )
                if matched:
                    self.model_found.emit(matched)
                    self.progress.emit(f"Modelo encontrado: {matched}")
                    return True

                # Model not pulled yet — try to pull it (non-fatal if it fails)
                self.progress.emit(
                    f"Modelo '{self._model}' no encontrado localmente — "
                    f"disponibles: {', '.join(names[:4]) or 'ninguno'}. "
                    "Descargando puede tardar varios minutos."
                )
                return self._pull_model()

            except Exception as exc:
                self.failed.emit(f"Error consultando modelos de Ollama: {exc}")
                QThread.currentThread().quit()
                return False

        def _pull_model(self) -> bool:
            """Attempt to pull the model; non-fatal on failure."""
            try:
                import httpx
                self.progress.emit(f"Descargando '{self._model}' desde Ollama registry…")
                with httpx.Client(timeout=600.0) as client:
                    with client.stream(
                        "POST",
                        f"{self._base_url}/api/pull",
                        json={"name": self._model, "stream": True},
                    ) as r:
                        r.raise_for_status()
                        for line in r.iter_lines():
                            if not line:
                                continue
                            try:
                                import json
                                data = json.loads(line)
                                status = data.get("status", "")
                                if status:
                                    self.progress.emit(f"Pull: {status}")
                            except Exception:
                                pass
                self.model_found.emit(self._model)
                return True
            except Exception as exc:
                self.failed.emit(
                    f"No se pudo descargar '{self._model}': {exc}. "
                    "Descárgalo manualmente con: ollama pull <modelo>"
                )
                QThread.currentThread().quit()
                return False

        # ── Step 3: warmup prompt ─────────────────────────────────────────────
        def _step_warmup_prompt(self) -> bool:
            self.step_started.emit(_STEP_WARMUP)
            self.progress.emit(f"Precargando '{self._model}' en memoria…")

            for attempt in range(self._warmup_retries + 1):
                try:
                    import httpx
                    payload = {
                        "model": self._model,
                        "messages": [
                            {"role": "user", "content": "ok"}
                        ],
                        "stream": False,
                        "keep_alive": "-1",   # keep model hot indefinitely
                        "options": {"num_ctx": 512, "temperature": 0.0},
                    }
                    with httpx.Client(timeout=self._timeout) as client:
                        r = client.post(f"{self._base_url}/api/chat", json=payload)
                        r.raise_for_status()
                    self.progress.emit("Modelo precargado y listo en RAM")
                    return True
                except Exception as exc:
                    if attempt < self._warmup_retries:
                        wait = 3.0 * (attempt + 1)
                        self.progress.emit(
                            f"Warmup intento {attempt + 1} falló ({exc}) — "
                            f"reintentando en {wait:.0f}s…"
                        )
                        time.sleep(wait)
                    else:
                        self.failed.emit(
                            f"No se pudo precargar el modelo tras "
                            f"{self._warmup_retries + 1} intentos: {exc}"
                        )
                        QThread.currentThread().quit()
                        return False

            return False  # unreachable, satisfies mypy


    def start_warmup_agent(
        *,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        on_progress: Any = None,
        on_model_found: Any = None,
        on_ready: Any = None,
        on_failed: Any = None,
    ) -> tuple["OllamaWarmupAgent", Any]:
        """
        Convenience factory: create agent + thread, wire signals, and start.

        Returns (agent, thread) so the caller can keep references alive.
        The thread quits itself when the agent pipeline finishes.
        """
        thread = QThread()
        agent  = OllamaWarmupAgent(base_url=base_url, model=model, timeout=timeout)
        agent.moveToThread(thread)

        thread.started.connect(agent.run)
        thread.finished.connect(agent.deleteLater)
        thread.finished.connect(thread.deleteLater)

        if on_progress   is not None:
            agent.progress.connect(on_progress)
        if on_model_found is not None:
            agent.model_found.connect(on_model_found)
        if on_ready      is not None:
            agent.ready.connect(on_ready)
        if on_failed     is not None:
            agent.failed.connect(on_failed)

        thread.start()
        return agent, thread

else:

    class OllamaWarmupAgent:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PySide6 no está instalada.")

    def start_warmup_agent(*_args: Any, **_kwargs: Any) -> tuple[Any, Any]:  # type: ignore[misc]
        raise RuntimeError("PySide6 no está instalada.")
