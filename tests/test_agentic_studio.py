from __future__ import annotations

from adv_archon.core.agentic_studio import (
    AgenticMode,
    build_agentic_studio_section,
    classify_agentic_request,
)


def test_agentic_router_classifies_deliverable_modes() -> None:
    assert (
        classify_agentic_request("investiga en internet y cita fuentes").mode
        == AgenticMode.DEEP_RESEARCH
    )
    assert (
        classify_agentic_request("crea una presentación para cliente").mode
        == AgenticMode.PRESENTATION
    )
    assert (
        classify_agentic_request("hazme un Excel con fórmulas de presupuesto").mode
        == AgenticMode.SPREADSHEET
    )
    assert (
        classify_agentic_request("prepara el expediente urbanístico con PGOU").mode
        == AgenticMode.EXPEDIENTE
    )


def test_agentic_studio_section_names_tools_and_verification() -> None:
    section = build_agentic_studio_section()

    assert "Agentic Studio" in section
    assert "Investigacion profunda" in section
    assert "Hoja de calculo" in section
    assert "python_exec" in section
    assert "fuentes citadas" in section
    assert "formulas visibles" in section
