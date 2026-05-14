"""Local-first visual tools for ADV ARCHON.

These tools add a small, bounded subset of computer-awareness features:
screen capture, region capture, webcam frame capture, and local image analysis.
The analysis path prefers an Ollama vision model and does not require a cloud API.
"""

from __future__ import annotations

import base64
import importlib
import io
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_VISION_SYSTEM = (
    "Eres el asistente visual local de ADV ARCHON. Describe imágenes con precisión, "
    "priorizando arquitectura, planos, UI, documentos técnicos y riesgos visibles. "
    "Si no puedes leer algo con certeza, dilo con claridad."
)
_DEFAULT_VISION_MODEL = "llava:latest"


@dataclass(slots=True)
class VisionTools:
    llm: Any

    def screenshot(self, save_path: str | None = None) -> dict[str, Any]:
        """Capture the full screen and return the saved local path."""
        try:
            _image_b64, tmp_path, _mime = self._capture_screen()
            if not save_path:
                return {
                    "ok": True,
                    "path": str(tmp_path),
                    "msg": f"Captura guardada en {tmp_path}",
                }
            destination = Path(save_path).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(tmp_path, destination)
            return {
                "ok": True,
                "path": str(destination),
                "msg": f"Captura guardada en {destination}",
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def screen_describe(self, question: str = "¿Qué ves en la pantalla?") -> dict[str, Any]:
        """Capture and describe the current screen using a local Ollama vision model."""
        try:
            image_b64, tmp_path, mime_type = self._capture_screen()
            description = self._ollama_vision(image_b64, question, mime_type=mime_type)
            return {
                "ok": True,
                "description": description,
                "screenshot_path": str(tmp_path),
                "provider": "ollama",
                "model": self._vision_model(),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def screen_region_describe(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        question: str = "¿Qué ves en esta región?",
    ) -> dict[str, Any]:
        """Capture and describe a screen region with the local vision model."""
        try:
            image_b64, tmp_path, mime_type = self._capture_region(x, y, width, height)
            description = self._ollama_vision(image_b64, question, mime_type=mime_type)
            return {
                "ok": True,
                "description": description,
                "screenshot_path": str(tmp_path),
                "provider": "ollama",
                "model": self._vision_model(),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def webcam_describe(
        self,
        question: str = "¿Qué ves en la cámara?",
        camera_index: int = 0,
    ) -> dict[str, Any]:
        """Capture one webcam frame and describe it locally when OpenCV is available."""
        try:
            image_b64 = self._capture_webcam(camera_index)
            description = self._ollama_vision(image_b64, question, mime_type="image/jpeg")
            return {
                "ok": True,
                "description": description,
                "provider": "ollama",
                "model": self._vision_model(),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def analyze_image_file(
        self,
        path: str,
        question: str = "Describe esta imagen",
    ) -> dict[str, Any]:
        """Analyze a local image file with the local Ollama vision model."""
        image_path = Path(path).expanduser().resolve()
        if not image_path.exists() or not image_path.is_file():
            return {"ok": False, "error": f"Archivo no encontrado: {image_path}"}
        try:
            image_b64, mime_type = self._prepare_image(image_path)
            description = self._ollama_vision(image_b64, question, mime_type=mime_type)
            return {
                "ok": True,
                "description": description,
                "path": str(image_path),
                "provider": "ollama",
                "model": self._vision_model(),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _capture_screen(self) -> tuple[str, Path, str]:
        path = Path(tempfile.gettempdir()) / "adv-archon-screen.png"
        self._run_screencapture(["-x", str(path)])
        image_b64, mime_type = self._prepare_image(path)
        return image_b64, path.with_suffix(".jpg"), mime_type

    def _capture_region(self, x: int, y: int, width: int, height: int) -> tuple[str, Path, str]:
        if width <= 0 or height <= 0:
            raise ValueError("La región debe tener ancho y alto positivos.")
        path = Path(tempfile.gettempdir()) / "adv-archon-region.png"
        self._run_screencapture(["-x", f"-R{x},{y},{width},{height}", str(path)])
        image_b64, mime_type = self._prepare_image(path)
        return image_b64, path.with_suffix(".jpg"), mime_type

    @staticmethod
    def _run_screencapture(args: list[str]) -> None:
        if shutil.which("screencapture") is None:
            raise RuntimeError("La captura de pantalla solo está disponible en macOS.")
        result = subprocess.run(["screencapture", *args], capture_output=True, check=False)
        output_path = Path(args[-1])
        if result.returncode != 0 or not output_path.exists():
            detail = result.stderr.decode(errors="ignore").strip()
            raise RuntimeError(
                "No se pudo capturar la pantalla. Concede permiso de "
                "'Grabación de pantalla' a ADV ARCHON o al terminal que lo ejecuta."
                + (f" Detalle: {detail}" if detail else "")
            )

    @staticmethod
    def _capture_webcam(camera_index: int) -> str:
        try:
            cv2 = importlib.import_module("cv2")
        except ImportError as exc:
            raise RuntimeError(
                "La webcam requiere opencv-python como dependencia opcional."
            ) from exc
        cap = cv2.VideoCapture(camera_index)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError("No se pudo leer un frame de la webcam.")
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            raise RuntimeError("No se pudo codificar el frame de webcam.")
        return base64.b64encode(encoded.tobytes()).decode("ascii")

    @staticmethod
    def _prepare_image(path: Path) -> tuple[str, str]:
        try:
            image_module = importlib.import_module("PIL.Image")
        except ImportError as exc:
            raise RuntimeError("La visión requiere Pillow instalado.") from exc

        with image_module.open(path) as image:
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            max_width = 1280
            if image.width > max_width:
                ratio = max_width / image.width
                resampling = getattr(image_module, "Resampling", image_module)
                image = image.resize(
                    (max_width, int(image.height * ratio)),
                    resampling.LANCZOS,
                )
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=78)
        jpg_path = path.with_suffix(".jpg")
        jpg_path.write_bytes(buffer.getvalue())
        return base64.b64encode(buffer.getvalue()).decode("ascii"), "image/jpeg"

    def _ollama_vision(
        self,
        image_b64: str,
        question: str,
        *,
        mime_type: str,
    ) -> str:
        import httpx

        base_url = self._ollama_base_url()
        model = self._vision_model()
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _VISION_SYSTEM},
                {
                    "role": "user",
                    "content": question,
                    "images": [image_b64],
                },
            ],
            "stream": False,
            "keep_alive": self._ollama_keep_alive(),
            "options": {
                "temperature": 0.2,
                "num_ctx": self._ollama_num_ctx(),
                "num_predict": 512,
            },
        }
        try:
            with httpx.Client(timeout=self._ollama_timeout()) as client:
                response = client.post(f"{base_url}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama rechazó la petición de visión con el modelo '{model}'. "
                "Instala o selecciona un modelo multimodal local, por ejemplo "
                "`ollama pull llava` o `ollama pull qwen2.5vl:7b`."
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                "Ollama no responde. Abre Ollama y verifica el modelo de visión local."
            ) from exc
        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        text = str(content).strip()
        if not text:
            raise RuntimeError("Ollama no devolvió descripción visual.")
        return text

    def _vision_model(self) -> str:
        configured = os.getenv("ADV_ARCHON_VISION_MODEL", "").strip()
        if configured:
            return configured
        try:
            model = str(self.llm._config.vision_local_model).strip()
            if model:
                return model
        except Exception:
            pass
        try:
            model = str(self.llm._config.ollama_model).strip()
            if any(token in model.lower() for token in ("llava", "vision", "vl")):
                return model
        except Exception:
            pass
        return _DEFAULT_VISION_MODEL

    def _ollama_base_url(self) -> str:
        try:
            return str(self.llm._config.ollama_base_url).rstrip("/")
        except Exception:
            return "http://127.0.0.1:11434"

    def _ollama_timeout(self) -> float:
        try:
            return float(self.llm._config.ollama_timeout_seconds)
        except Exception:
            return 60.0

    def _ollama_num_ctx(self) -> int:
        try:
            return int(self.llm._config.ollama_num_ctx)
        except Exception:
            return 4096

    def _ollama_keep_alive(self) -> int | str:
        try:
            keep_alive = str(self.llm._config.ollama_keep_alive).strip()
        except Exception:
            keep_alive = "-1"
        return -1 if keep_alive == "-1" else keep_alive


def build_vision_tool_specs(tools: VisionTools) -> list[dict[str, Any]]:
    return [
        {
            "name": "screenshot",
            "description": (
                "Captura la pantalla completa y devuelve una ruta local. No analiza la imagen."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "save_path": {
                        "type": "string",
                        "description": "Ruta opcional donde guardar la captura.",
                    },
                },
                "required": [],
            },
            "fn": tools.screenshot,
        },
        {
            "name": "screen_describe",
            "description": (
                "Captura la pantalla y la describe con un modelo multimodal local de Ollama."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Pregunta sobre lo que se ve en pantalla.",
                    },
                },
                "required": [],
            },
            "fn": tools.screen_describe,
        },
        {
            "name": "screen_region_describe",
            "description": (
                "Captura una región de pantalla y la analiza con visión local de Ollama."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "question": {"type": "string"},
                },
                "required": ["x", "y", "width", "height"],
            },
            "fn": tools.screen_region_describe,
        },
        {
            "name": "webcam_describe",
            "description": (
                "Captura un frame de webcam y lo analiza localmente. OpenCV es opcional."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "camera_index": {"type": "integer"},
                },
                "required": [],
            },
            "fn": tools.webcam_describe,
        },
        {
            "name": "analyze_image_file",
            "description": (
                "Analiza una imagen local con un modelo multimodal local de Ollama."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta absoluta a la imagen."},
                    "question": {"type": "string"},
                },
                "required": ["path"],
            },
            "fn": tools.analyze_image_file,
        },
    ]
