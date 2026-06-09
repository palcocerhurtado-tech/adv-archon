from __future__ import annotations

from adv_archon.core.document_draft import DocumentDraft
from adv_archon.core.document_intelligence import (
    analyze_document_intelligence,
    classify_deliverable_intent,
    detect_formulas,
    detect_magnitudes,
    extract_tabular_data,
    propose_dispatch_next_steps,
)


def test_classify_deliverable_intent_uses_text_and_attachment_hints() -> None:
    intent = classify_deliverable_intent(
        "Prepara una hoja de calculo auditable con formulas para el presupuesto.",
        attachment_names=("mediciones.xlsx",),
    )

    assert intent.kind == "xlsx"
    assert intent.confidence > 0.4
    assert "xlsx:.xlsx" in intent.signals


def test_extract_tabular_data_from_csv_and_markdown_table() -> None:
    text = """
Partida,Unidad,Cantidad
Demolicion,m2,24
Pintura,m2,80

| Zona | Superficie |
| --- | ---: |
| Planta baja | 120 m2 |
| Atico | 35 m2 |
"""

    tables = extract_tabular_data(text)

    assert len(tables) == 2
    assert tables[0].columns == ("Partida", "Unidad", "Cantidad")
    assert tables[0].rows[1] == ("Pintura", "m2", "80")
    assert tables[1].columns == ("Zona", "Superficie")
    assert tables[1].rows[0] == ("Planta baja", "120 m2")


def test_detect_formulas_and_magnitudes() -> None:
    text = "Superficie construida 120 m2. PEM = superficie * 950 EUR/m2. IVA = PEM*0.21"

    formulas = detect_formulas(text)
    magnitudes = detect_magnitudes(text)

    assert ("PEM", "superficie * 950 EUR/m2") in {
        (formula.label, formula.expression) for formula in formulas
    }
    assert ("IVA", "PEM*0.21") in {
        (formula.label, formula.expression) for formula in formulas
    }
    assert any(item.value == 120 and item.unit == "m2" for item in magnitudes)
    assert any(item.unit == "EUR" for item in magnitudes)


def test_analyze_document_intelligence_builds_reusable_draft() -> None:
    result = analyze_document_intelligence(
        """
Necesito una tabla para exportar.
Concepto\tValor\tUnidad
Superficie\t120\tm2
Coste unitario\t950\tEUR/m2
Total = 120*950
""",
        title="Presupuesto preliminar",
    )

    draft = result.draft

    assert isinstance(draft, DocumentDraft)
    assert draft.title == "Presupuesto preliminar"
    assert result.intent.kind in {"table", "xlsx"}
    assert draft.tables[0].columns == ("Concepto", "Valor", "Unidad")
    assert draft.metadata["table_count"] == 1
    assert draft.metadata["formula_count"] >= 1
    assert any(section.id == "formulas" for section in draft.sections)
    assert any("Validar 1 tabla" in step for step in result.next_steps)


def test_propose_dispatch_next_steps_warns_on_low_confidence() -> None:
    intent = classify_deliverable_intent("hazlo bonito")

    steps = propose_dispatch_next_steps(intent=intent)

    assert intent.kind == "report"
    assert any("intencion detectada es debil" in step for step in steps)
