from __future__ import annotations

from pathlib import Path

from adv_archon.core.spreadsheet_brain import inspect_workbook_formulas
from adv_archon.tools.spreadsheet import build_spreadsheet_tool_specs, tool_crear_excel_auditable


def test_spreadsheet_tool_creates_reviewable_xlsx(tmp_path: Path) -> None:
    output_path = tmp_path / "modelo.xlsx"

    payload = tool_crear_excel_auditable(
        title="Modelo financiero",
        inputs=[
            {"name": "Ingresos", "value": 1000, "unit": "EUR"},
            {"name": "Costes", "value": 350, "unit": "EUR"},
        ],
        formulas=[
            {
                "label": "Margen",
                "excel_formula": "=Entradas!B4-Entradas!B5",
                "unit": "EUR",
            }
        ],
        assumptions=["Ejemplo local sin datos personales."],
        output_path=str(output_path),
    )

    assert payload["ok"] is True
    assert Path(payload["output_path"]).exists()
    assert inspect_workbook_formulas(output_path) == ("Calculos!B4: =Entradas!B4-Entradas!B5",)
    assert payload["audit_notes"][0] == "Entradas declaradas: 2."


def test_spreadsheet_tool_spec_exposes_excel_capability() -> None:
    spec = build_spreadsheet_tool_specs()[0]

    assert spec["name"] == "crear_excel_auditable"
    assert "XLSX" in spec["description"]
    assert spec["schema"]["required"] == ["title"]
