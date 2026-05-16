from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class QAItem:
    clave: str
    nombre: str
    ok: bool
    detalle: str
    accion: str = ""


def run_qa_checks(config: Any) -> list[QAItem]:
    base_url = str(config.llm.ollama_base_url).rstrip("/")
    return [
        _check_microphone_input(),
        _check_ollama_health(base_url),
        _check_local_model(base_url, str(config.llm.ollama_model)),
        _check_vision_model(base_url, str(config.llm.vision_local_model)),
        _check_screen_capture_permission(),
    ]


def _check_microphone_input() -> QAItem:
    try:
        sd = importlib.import_module("sounddevice")
        device = sd.query_devices(kind="input")
    except Exception as exc:
        return QAItem(
            clave="microphone",
            nombre="Micrófono",
            ok=False,
            detalle=f"No disponible: {str(exc)[:120]}",
            accion=(
                "macOS: Ajustes del Sistema > Privacidad y seguridad > Micrófono > "
                "ADV ARCHON. Reabre la app después."
            ),
        )
    name = str(device.get("name") if isinstance(device, dict) else device)
    return QAItem(
        clave="microphone",
        nombre="Micrófono",
        ok=True,
        detalle=f"Entrada detectada: {name[:90]}",
    )


def _check_ollama_health(base_url: str) -> QAItem:
    try:
        _ollama_tags(base_url)
    except Exception as exc:
        return QAItem(
            clave="ollama",
            nombre="Ollama",
            ok=False,
            detalle=f"No responde: {str(exc)[:120]}",
            accion="Abre Ollama.app o ejecuta `ollama serve`.",
        )
    return QAItem(
        clave="ollama",
        nombre="Ollama",
        ok=True,
        detalle=f"Servidor activo en {base_url}",
    )


def _check_local_model(base_url: str, model: str) -> QAItem:
    return _check_model_in_tags(
        base_url,
        model,
        clave="local_model",
        nombre=f"Modelo local ({model})",
        accion=f"Ejecuta `ollama pull {model}`.",
    )


def _check_vision_model(base_url: str, model: str) -> QAItem:
    return _check_model_in_tags(
        base_url,
        model,
        clave="vision_model",
        nombre=f"Visión local ({model})",
        accion=f"Para visión: `ollama pull {model}` o `ollama pull qwen2.5vl:7b`.",
    )


def _check_model_in_tags(
    base_url: str,
    model: str,
    *,
    clave: str,
    nombre: str,
    accion: str,
) -> QAItem:
    try:
        tags = _ollama_tags(base_url)
    except Exception as exc:
        return QAItem(
            clave=clave,
            nombre=nombre,
            ok=False,
            detalle=f"No se pudo consultar Ollama: {str(exc)[:100]}",
            accion="Primero arranca Ollama.",
        )
    names = [str(item.get("name", "")) for item in tags.get("models", [])]
    base = model.split(":", 1)[0]
    matched = next((name for name in names if name == model or name.startswith(base)), "")
    if matched:
        return QAItem(clave=clave, nombre=nombre, ok=True, detalle=f"Instalado: {matched}")
    preview = ", ".join(names[:5]) or "ninguno"
    return QAItem(
        clave=clave,
        nombre=nombre,
        ok=False,
        detalle=f"No instalado. Modelos disponibles: {preview}",
        accion=accion,
    )


def _check_screen_capture_permission() -> QAItem:
    if sys.platform != "darwin":
        return QAItem(
            clave="screen_capture",
            nombre="Grabación de pantalla",
            ok=True,
            detalle="No aplica fuera de macOS.",
        )
    if shutil.which("screencapture") is None:
        return QAItem(
            clave="screen_capture",
            nombre="Grabación de pantalla",
            ok=False,
            detalle="No se encontró `screencapture`.",
        )
    target = Path(tempfile.gettempdir()) / "adv-archon-qa-screen.png"
    try:
        result = subprocess.run(
            ["screencapture", "-x", str(target)],
            capture_output=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and target.exists():
            target.unlink(missing_ok=True)
            return QAItem(
                clave="screen_capture",
                nombre="Grabación de pantalla",
                ok=True,
                detalle="Captura de pantalla permitida.",
            )
        detail = result.stderr.decode(errors="ignore").strip() or "sin detalle"
    except Exception as exc:
        detail = str(exc)
    return QAItem(
        clave="screen_capture",
        nombre="Grabación de pantalla",
        ok=False,
        detalle=f"Pendiente: {detail[:120]}",
        accion=(
            "macOS: Ajustes del Sistema > Privacidad y seguridad > "
            "Grabación de pantalla > ADV ARCHON."
        ),
    )


def _ollama_tags(base_url: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=3) as response:
        data = json.loads(response.read())
    return cast(dict[str, Any], data)
