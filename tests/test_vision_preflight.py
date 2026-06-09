from __future__ import annotations

from pathlib import Path

from adv_archon.core.vision_preflight import (
    AttachmentVisionHint,
    VisionReadiness,
    build_attachment_vision_hints,
    build_multimodal_prompt,
    summarize_vision_readiness,
)


def test_image_attachment_hint_needs_local_vision() -> None:
    hint = build_attachment_vision_hints(["/tmp/fachada.JPG"])[0]

    assert hint.path == Path("/tmp/fachada.JPG")
    assert hint.kind == "image"
    assert hint.can_preview is True
    assert hint.needs_vision is True
    assert "imagen local" in hint.prompt_hint


def test_pdf_attachment_hint_recommends_ocr_for_scanned_plans() -> None:
    hint = build_attachment_vision_hints(["/tmp/proyecto_basico.pdf"])[0]

    assert hint.kind == "pdf"
    assert hint.can_preview is True
    assert hint.needs_vision is True
    assert "OCR" in hint.prompt_hint
    assert "planos" in hint.prompt_hint


def test_dwg_attachment_hint_recommends_export_before_visual_analysis() -> None:
    hint = build_attachment_vision_hints(["/tmp/levantamiento.dwg"])[0]

    assert hint.kind == "cad"
    assert hint.can_preview is False
    assert hint.needs_vision is True
    assert "exportarlo a PDF/imagen" in hint.prompt_hint


def test_summarize_vision_readiness_reports_missing_model() -> None:
    readiness = summarize_vision_readiness(["qwen2.5:7b"], configured_model="llava:latest")

    assert readiness.status == "missing_model"
    assert readiness.label == "Visión local no activa"
    assert readiness.can_analyze_images is False
    assert "ollama pull llava:latest" in readiness.recommended_action


def test_summarize_vision_readiness_accepts_installed_model_dicts() -> None:
    readiness = summarize_vision_readiness(
        [{"name": "llava:13b"}],
        configured_model="llava:latest",
    )

    assert readiness.status == "ready"
    assert readiness.label == "Visión local activa"
    assert readiness.can_analyze_images is True
    assert "llava:latest" in readiness.detail


def test_build_multimodal_prompt_degrades_without_local_vision() -> None:
    readiness = VisionReadiness(
        status="missing_model",
        label="Visión local no activa",
        detail="Modelo no instalado.",
        can_analyze_images=False,
        recommended_action="Usa OCR local o texto extraído.",
    )
    prompt = build_multimodal_prompt(
        "Prepara un informe",
        [
            AttachmentVisionHint(
                path=Path("/tmp/plano.pdf"),
                kind="pdf",
                can_preview=True,
                needs_vision=True,
                prompt_hint="conviene OCR.",
            )
        ],
        readiness,
    )

    assert prompt.startswith("Prepara un informe")
    assert "/tmp/plano.pdf (pdf): conviene OCR." in prompt
    assert "no falles ni bloquees" in prompt
    assert "OCR" in prompt
