from __future__ import annotations

from pathlib import Path

from adv_archon.core.spreadsheet_brain import (
    SpreadsheetFormula,
    SpreadsheetInput,
    build_workbook_audit_notes,
    create_auditable_workbook,
    inspect_workbook_formulas,
)


def test_create_auditable_workbook_keeps_formulas_visible(tmp_path: Path) -> None:
    result = create_auditable_workbook(
        title="Presupuesto preliminar",
        inputs=[
            SpreadsheetInput("Superficie", 120, "m2", "Dato de proyecto"),
            SpreadsheetInput("Coste unitario", 950, "EUR/m2", "Estimacion"),
        ],
        formulas=[
            SpreadsheetFormula(
                "PEM estimado",
                "=Entradas!B4*Entradas!B5",
                "EUR",
                "Calculo preliminar",
            )
        ],
        assumptions=["Precios sin IVA."],
        output_path=tmp_path / "presupuesto.xlsx",
    )

    formulas = inspect_workbook_formulas(result.output_path)

    assert result.output_path.exists()
    assert "Entradas declaradas: 2." in result.audit_notes
    assert formulas == ("Calculos!B4: =Entradas!B4*Entradas!B5",)


def test_formula_without_equal_is_normalized_and_audited(tmp_path: Path) -> None:
    result = create_auditable_workbook(
        title="Modelo de horas",
        inputs=[SpreadsheetInput("Horas", 8)],
        formulas=[SpreadsheetFormula("Total", "Entradas!B4*50")],
        output_path=tmp_path / "horas.xlsx",
    )

    formulas = inspect_workbook_formulas(result.output_path)

    assert formulas == ("Calculos!B4: =Entradas!B4*50",)
    assert any("se normalizara" in note for note in result.audit_notes)


def test_build_workbook_audit_notes_warns_empty_model() -> None:
    notes = build_workbook_audit_notes(inputs=[], formulas=[])

    assert "Aviso: no hay entradas; el libro puede no ser auditable." in notes
    assert "Aviso: no hay formulas; el libro funciona como tabla de datos." in notes
