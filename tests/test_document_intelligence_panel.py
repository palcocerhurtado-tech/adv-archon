from __future__ import annotations

from adv_archon.core.document_intelligence import analyze_document_intelligence
from adv_archon.desktop.document_intelligence_panel import (
    draft_to_intelligence_text,
    summarize_document_intelligence,
)


def test_summarize_document_intelligence_from_core_result() -> None:
    result = analyze_document_intelligence(
        """
Concepto,Importe
PEM,120000 EUR
IVA = PEM*0.21
Superficie construida 140 m2
""",
        attachment_names=["presupuesto.xlsx"],
        title="Presupuesto preliminar",
    )

    summary = summarize_document_intelligence(result)

    assert summary.intent in {"xlsx", "table"}
    assert summary.table_count == 1
    assert summary.formula_count >= 1
    assert summary.magnitude_count >= 1
    assert summary.draft_title == "Presupuesto preliminar"
    assert any("IVA" in line for line in summary.formula_lines)


def test_summarize_document_intelligence_from_tool_payload() -> None:
    payload = {
        "intent": "xlsx",
        "confidence": 0.82,
        "signals": ["xlsx:.xlsx", "xlsx:formula"],
        "tables": [
            {
                "title": "Mediciones",
                "columns": ["Partida", "Cantidad"],
                "rows": [["Pintura", "80 m2"]],
            }
        ],
        "formulas": [{"label": "Total", "expression": "80*15"}],
        "magnitudes": [{"label": "Pintura", "raw": "80 m2"}],
        "draft": {"title": "Libro de mediciones"},
        "next_steps": ["Revisar unidades."],
    }

    summary = summarize_document_intelligence(payload)

    assert summary.intent == "xlsx"
    assert summary.confidence == 0.82
    assert summary.table_lines == ("Mediciones: 1 fila(s), columnas Partida, Cantidad",)
    assert summary.formula_lines == ("Total: 80*15",)
    assert summary.magnitude_lines == ("Pintura: 80 m2",)
    assert summary.next_steps == ("Revisar unidades.",)


def test_draft_to_intelligence_text_includes_sections_tables_and_metadata() -> None:
    text = draft_to_intelligence_text(
        {
            "title": "Documento de entrega",
            "executive_summary": "Resumen de viabilidad.",
            "sections": [
                {
                    "title": "Calculo",
                    "content": "Total = superficie * coste_unitario",
                }
            ],
            "tables": [
                {
                    "title": "Datos",
                    "columns": ["Parametro", "Valor"],
                    "rows": [["Superficie", "120 m2"]],
                }
            ],
            "metadata": {
                "formulas": [{"label": "IVA", "expression": "PEM*0.21"}],
                "magnitudes": [{"raw": "120 m2"}],
            },
        }
    )

    assert "Documento de entrega" in text
    assert "Parametro,Valor" in text
    assert "Superficie,120 m2" in text
    assert "IVA" in text
    assert "120 m2" in text
