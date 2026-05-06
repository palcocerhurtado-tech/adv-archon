"""Tests for generate_expediente_pdf — direct PDF generation from Expediente data."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from adv_archon.core.report_generator import generate_expediente_pdf


def _make_exp(**kwargs):
    """Minimal Expediente-like object for testing."""
    base = dict(
        id="test-id",
        title="Proyecto Vivienda Unifamiliar",
        address="Calle Mayor 10, Cádiz",
        municipality="Cádiz",
        province="Cádiz",
        latitude=36.5270,
        longitude=-6.2886,
        cadastral_ref="7284601TF5378S0001UR",
        status="analizado",
        plan_path="/tmp/plano.pdf",
        site_context="",
        analysis_result="",
        report_path="",
        created_at="2026-05-03T10:00:00+00:00",
        updated_at="2026-05-03T10:30:00+00:00",
        notes="",
    )
    base.update(kwargs)
    obj = MagicMock()
    for k, v in base.items():
        setattr(obj, k, v)
    return obj


def test_generate_expediente_pdf_no_analysis(tmp_path: Path) -> None:
    """PDF generates even without analysis_result."""
    exp = _make_exp(analysis_result="", site_context="")
    out = tmp_path / "test_no_analysis.pdf"
    result = generate_expediente_pdf(exp, output_path=out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 1000


def test_generate_expediente_pdf_with_analysis(tmp_path: Path) -> None:
    """PDF with full analysis_result includes summary and annotations."""
    analysis = {
        "summary": "El plano cumple la normativa de altura y superficie.",
        "annotations": [
            {"status": "ok", "description": "Altura máxima: 9m — cumple PGOU art. 45"},
            {"status": "warning", "description": "Retranqueo lateral: pendiente verificar"},
            {"status": "violation", "description": "Ocupación supera el 60% permitido"},
        ],
        "full_analysis": "Análisis completo del plano.\n1. Cumple altura.\n2. Retranqueo revisar.",
    }
    exp = _make_exp(analysis_result=json.dumps(analysis))
    out = tmp_path / "test_with_analysis.pdf"
    result = generate_expediente_pdf(exp, output_path=out)
    assert result.exists()
    assert result.stat().st_size > 2000


def test_generate_expediente_pdf_with_site_context(tmp_path: Path) -> None:
    """PDF with site_context shows parcel data and legal checks."""
    site_ctx = {
        "cadastral_ref": "7284601TF5378S0001UR",
        "parcel_detail": {
            "surface_m2": 180,
            "construction_year": 1985,
            "floors_above": 2,
            "floors_below": 0,
            "use_detail": "Residencial",
        },
        "legal_checks": [
            {"name": "Identificación catastral", "status": "ready", "detail": "Ref. verificada"},
            {"name": "PGOU municipal", "status": "ready", "detail": "PGOU indexado"},
            {
                "name": "Dominio hidráulico",
                "status": "conditional",
                "detail": "T500 zona inundable",
            },
            {"name": "Costas", "status": "not_applicable", "detail": "Interior"},
        ],
    }
    exp = _make_exp(site_context=json.dumps(site_ctx))
    out = tmp_path / "test_site_context.pdf"
    result = generate_expediente_pdf(exp, output_path=out)
    assert result.exists()
    assert result.stat().st_size > 2000


def test_generate_expediente_pdf_default_output_path(tmp_path: Path, monkeypatch) -> None:
    """Without explicit output_path, PDF is written to Desktop."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    exp = _make_exp(municipality="Sevilla", plan_path="/tmp/vivienda.pdf")
    result = generate_expediente_pdf(exp)
    assert result.exists()
    assert "sevilla" in result.name


def test_generate_expediente_pdf_no_municipality(tmp_path: Path) -> None:
    """Falls back gracefully when municipality is empty."""
    exp = _make_exp(municipality="", plan_path="")
    out = tmp_path / "test_no_muni.pdf"
    result = generate_expediente_pdf(exp, output_path=out)
    assert result.exists()


def test_generate_expediente_pdf_invalid_analysis_json(tmp_path: Path) -> None:
    """Corrupted analysis_result JSON is handled gracefully."""
    exp = _make_exp(analysis_result="{invalid json}")
    out = tmp_path / "test_bad_json.pdf"
    result = generate_expediente_pdf(exp, output_path=out)
    assert result.exists()


def test_generate_expediente_pdf_plain_text_analysis(tmp_path: Path) -> None:
    """Plain text in analysis_result (not JSON) is handled as raw text."""
    exp = _make_exp(analysis_result="El plano cumple la normativa según el PGOU vigente.")
    out = tmp_path / "test_plain_text.pdf"
    result = generate_expediente_pdf(exp, output_path=out)
    assert result.exists()
