from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adv_archon.core.attachments import normalize_attachment_paths

_IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
_PDF_EXTENSIONS = {".pdf"}
_CAD_EXTENSIONS = {".dwg", ".dxf"}
_SPREADSHEET_EXTENSIONS = {".csv", ".ods", ".xls", ".xlsm", ".xlsx"}
_DOCUMENT_EXTENSIONS = {".doc", ".docx", ".md", ".rtf", ".txt"}


@dataclass(frozen=True, slots=True)
class VisionReadiness:
    status: str
    label: str
    detail: str
    can_analyze_images: bool
    recommended_action: str


@dataclass(frozen=True, slots=True)
class AttachmentVisionHint:
    path: Path
    kind: str
    can_preview: bool
    needs_vision: bool
    prompt_hint: str


def build_attachment_vision_hints(paths: Sequence[Path | str]) -> list[AttachmentVisionHint]:
    return [_build_attachment_hint(path) for path in normalize_attachment_paths(paths)]


def summarize_vision_readiness(
    installed_models: Iterable[str | Mapping[str, Any]],
    configured_model: str = "llava:latest",
) -> VisionReadiness:
    model = configured_model.strip() or "llava:latest"
    if _model_is_installed(installed_models, model):
        return VisionReadiness(
            status="ready",
            label="Visión local activa",
            detail=f"Modelo multimodal disponible: {model}.",
            can_analyze_images=True,
            recommended_action=(
                "Analizar imágenes y previsualizaciones localmente cuando aporten contexto."
            ),
        )
    return VisionReadiness(
        status="missing_model",
        label="Visión local no activa",
        detail=(
            "ADV ARCHON puede seguir trabajando con los adjuntos, pero no analizará "
            f"imágenes directamente hasta instalar el modelo local {model}."
        ),
        can_analyze_images=False,
        recommended_action=(
            f"Instala el modelo con `ollama pull {model}` o usa lectura de texto/OCR/exportación "
            "a imagen como alternativa."
        ),
    )


def build_multimodal_prompt(
    user_text: str,
    attachments: Sequence[AttachmentVisionHint | Path | str],
    readiness: VisionReadiness,
) -> str:
    hints = _coerce_hints(attachments)
    blocks = [user_text.strip() or "Analiza los adjuntos disponibles."]
    if hints:
        attachment_lines = [
            f"- {hint.path} ({hint.kind}): {hint.prompt_hint}" for hint in hints
        ]
        blocks.append(
            "Adjuntos para usar en el informe, Excel o análisis:\n"
            + "\n".join(attachment_lines)
        )

    if readiness.can_analyze_images:
        blocks.append(
            f"{readiness.label}: usa visión local para imágenes, capturas o planos exportados "
            "cuando ayude a interpretar geometría, tablas, sellos, notas o medidas visibles."
        )
    else:
        blocks.append(
            f"{readiness.label}: no falles ni bloquees la respuesta. Si un adjunto requiere "
            "visión, pide o usa una alternativa local: texto extraído, OCR, conversión de PDF/DWG "
            "a imagen, o una descripción manual del contenido."
        )
    blocks.append(f"Acción recomendada: {readiness.recommended_action}")
    return "\n\n".join(blocks)


def _build_attachment_hint(path: Path) -> AttachmentVisionHint:
    suffix = path.suffix.lower()
    if suffix in _IMAGE_EXTENSIONS:
        return AttachmentVisionHint(
            path=path,
            kind="image",
            can_preview=True,
            needs_vision=True,
            prompt_hint=(
                "trátalo como imagen local; útil para inspección visual, OCR puntual, croquis, "
                "fotografías o capturas."
            ),
        )
    if suffix in _PDF_EXTENSIONS:
        return AttachmentVisionHint(
            path=path,
            kind="pdf",
            can_preview=True,
            needs_vision=True,
            prompt_hint=(
                "extrae texto si es posible; si contiene planos escaneados o tablas, conviene OCR "
                "o previsualización con visión local."
            ),
        )
    if suffix in _CAD_EXTENSIONS:
        return AttachmentVisionHint(
            path=path,
            kind="cad",
            can_preview=False,
            needs_vision=True,
            prompt_hint=(
                "probable plano CAD; conviene exportarlo a PDF/imagen antes de análisis "
                "visual u OCR."
            ),
        )
    if suffix in _SPREADSHEET_EXTENSIONS:
        return AttachmentVisionHint(
            path=path,
            kind="spreadsheet",
            can_preview=False,
            needs_vision=False,
            prompt_hint=(
                "úsalo como fuente tabular para informe, Excel, mediciones o comprobaciones."
            ),
        )
    if suffix in _DOCUMENT_EXTENSIONS:
        return AttachmentVisionHint(
            path=path,
            kind="document",
            can_preview=False,
            needs_vision=False,
            prompt_hint="léelo como documento de texto antes de recurrir a OCR o visión.",
        )
    return AttachmentVisionHint(
        path=path,
        kind="unknown",
        can_preview=False,
        needs_vision=False,
        prompt_hint="revisa el tipo de archivo y úsalo solo si aporta contexto verificable.",
    )


def _coerce_hints(
    attachments: Sequence[AttachmentVisionHint | Path | str],
) -> list[AttachmentVisionHint]:
    if not attachments:
        return []
    hints: list[AttachmentVisionHint] = []
    raw_paths: list[Path | str] = []
    for item in attachments:
        if isinstance(item, AttachmentVisionHint):
            hints.append(item)
        else:
            raw_paths.append(item)
    return [*hints, *build_attachment_vision_hints(raw_paths)]


def _model_is_installed(
    installed_models: Iterable[str | Mapping[str, Any]],
    configured_model: str,
) -> bool:
    expected = configured_model.strip()
    expected_base = expected.split(":", 1)[0]
    for raw_model in installed_models:
        name = _model_name(raw_model)
        if not name:
            continue
        if name == expected or name.startswith(expected_base + ":"):
            return True
    return False


def _model_name(raw_model: str | Mapping[str, Any]) -> str:
    if isinstance(raw_model, str):
        return raw_model.strip()
    for key in ("name", "model"):
        value = raw_model.get(key)
        if value:
            return str(value).strip()
    return ""
