from __future__ import annotations

from pathlib import Path
from typing import Any

from adv_archon.core.spreadsheet_brain import (
    SpreadsheetFormula,
    SpreadsheetInput,
    create_auditable_workbook,
)


def tool_crear_excel_auditable(
    title: str,
    inputs: list[dict[str, Any]] | None = None,
    formulas: list[dict[str, Any]] | None = None,
    assumptions: list[str] | None = None,
    output_path: str = "",
) -> dict[str, Any]:
    clean_title = title.strip() or "ADV ARCHON - Excel auditable"
    target = (
        Path(output_path).expanduser()
        if output_path.strip()
        else Path.home() / "Desktop" / "adv_archon_excel_auditable.xlsx"
    )
    parsed_inputs = [
        SpreadsheetInput(
            name=str(item.get("name") or item.get("variable") or "Entrada"),
            value=item.get("value", ""),
            unit=str(item.get("unit") or ""),
            note=str(item.get("note") or ""),
        )
        for item in inputs or []
        if isinstance(item, dict)
    ]
    parsed_formulas = [
        SpreadsheetFormula(
            label=str(item.get("label") or item.get("name") or "Resultado"),
            excel_formula=str(item.get("excel_formula") or item.get("formula") or ""),
            unit=str(item.get("unit") or ""),
            note=str(item.get("note") or ""),
        )
        for item in formulas or []
        if isinstance(item, dict)
    ]
    result = create_auditable_workbook(
        title=clean_title,
        inputs=parsed_inputs,
        formulas=parsed_formulas,
        assumptions=tuple(assumptions or ()),
        output_path=target,
    )
    return {
        "ok": True,
        "output_path": str(result.output_path),
        "inputs": [item.as_payload() for item in result.inputs],
        "formulas": [item.as_payload() for item in result.formulas],
        "audit_notes": list(result.audit_notes),
    }


def build_spreadsheet_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "crear_excel_auditable",
            "description": (
                "Create a professional XLSX workbook with visible formulas, inputs, "
                "assumptions and audit notes. Use for budgets, class exercises, "
                "formula solving, tables, comparisons and calculations that should be "
                "reviewable like an expert Excel model."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "inputs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {},
                                "unit": {"type": "string"},
                                "note": {"type": "string"},
                            },
                        },
                    },
                    "formulas": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "excel_formula": {"type": "string"},
                                "unit": {"type": "string"},
                                "note": {"type": "string"},
                            },
                        },
                    },
                    "assumptions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "output_path": {"type": "string"},
                },
                "required": ["title"],
            },
            "fn": tool_crear_excel_auditable,
        }
    ]


__all__ = ["build_spreadsheet_tool_specs", "tool_crear_excel_auditable"]
