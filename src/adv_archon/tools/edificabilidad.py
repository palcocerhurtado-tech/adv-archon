from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class EdificabilidadResult:
    # Inputs
    superficie_parcela: float
    coef_edificabilidad: float
    ocupacion_max_pct: float
    altura_max_m: float
    num_plantas: int
    retranqueo_frontal_m: float
    retranqueo_lateral_m: float
    retranqueo_fondo_m: float
    # Computed
    techo_edificable_m2: float
    ocupacion_max_m2: float
    superficie_por_planta: float
    volumen_max_m3: float
    superficie_libre_m2: float
    pct_libre: float


def calcular_edificabilidad(
    superficie_parcela: float,
    coef_edificabilidad: float,
    ocupacion_max_pct: float,
    altura_max_m: float,
    num_plantas: int,
    retranqueo_frontal_m: float = 0.0,
    retranqueo_lateral_m: float = 0.0,
    retranqueo_fondo_m: float = 0.0,
) -> EdificabilidadResult:
    """Pure-math edificabilidad calculation — no LLM involved."""
    techo = superficie_parcela * coef_edificabilidad
    ocupacion_max = superficie_parcela * (ocupacion_max_pct / 100.0)
    sup_planta = techo / num_plantas if num_plantas > 0 else techo
    volumen = ocupacion_max * altura_max_m
    libre = superficie_parcela - ocupacion_max
    pct_libre = (libre / superficie_parcela * 100) if superficie_parcela > 0 else 0.0
    return EdificabilidadResult(
        superficie_parcela=superficie_parcela,
        coef_edificabilidad=coef_edificabilidad,
        ocupacion_max_pct=ocupacion_max_pct,
        altura_max_m=altura_max_m,
        num_plantas=num_plantas,
        retranqueo_frontal_m=retranqueo_frontal_m,
        retranqueo_lateral_m=retranqueo_lateral_m,
        retranqueo_fondo_m=retranqueo_fondo_m,
        techo_edificable_m2=round(techo, 2),
        ocupacion_max_m2=round(ocupacion_max, 2),
        superficie_por_planta=round(sup_planta, 2),
        volumen_max_m3=round(volumen, 2),
        superficie_libre_m2=round(libre, 2),
        pct_libre=round(pct_libre, 2),
    )


def result_to_csv(result: EdificabilidadResult) -> str:
    """Serialize result as CSV text for export."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Parámetro", "Valor", "Unidad"])
    rows = [
        ("Superficie de parcela", result.superficie_parcela, "m²"),
        ("Coeficiente de edificabilidad", result.coef_edificabilidad, "m²t/m²s"),
        ("Techo edificable máximo", result.techo_edificable_m2, "m²"),
        ("Ocupación máxima (%)", result.ocupacion_max_pct, "%"),
        ("Ocupación máxima (superficie)", result.ocupacion_max_m2, "m²"),
        ("Número de plantas", result.num_plantas, "plantas"),
        ("Superficie útil por planta", result.superficie_por_planta, "m²"),
        ("Altura máxima", result.altura_max_m, "m"),
        ("Volumen máximo edificable", result.volumen_max_m3, "m³"),
        ("Superficie libre de parcela", result.superficie_libre_m2, "m²"),
        ("Porcentaje libre de parcela", result.pct_libre, "%"),
        ("Retranqueo frontal", result.retranqueo_frontal_m, "m"),
        ("Retranqueo lateral", result.retranqueo_lateral_m, "m"),
        ("Retranqueo a fondo de parcela", result.retranqueo_fondo_m, "m"),
    ]
    writer.writerows(rows)
    return buf.getvalue()


# ── Tool wrapper ───────────────────────────────────────────────────────────────

def tool_calcular_edificabilidad(
    superficie_parcela: float,
    coef_edificabilidad: float,
    ocupacion_max_pct: float,
    altura_max_m: float,
    num_plantas: int,
    retranqueo_frontal_m: float = 0.0,
    retranqueo_lateral_m: float = 0.0,
    retranqueo_fondo_m: float = 0.0,
    exportar_csv: bool = False,
    csv_output_path: str = "",
) -> dict[str, Any]:
    """Calculate edificabilidad parameters. Returns structured table and optional CSV."""
    try:
        result = calcular_edificabilidad(
            superficie_parcela=superficie_parcela,
            coef_edificabilidad=coef_edificabilidad,
            ocupacion_max_pct=ocupacion_max_pct,
            altura_max_m=altura_max_m,
            num_plantas=num_plantas,
            retranqueo_frontal_m=retranqueo_frontal_m,
            retranqueo_lateral_m=retranqueo_lateral_m,
            retranqueo_fondo_m=retranqueo_fondo_m,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    csv_path_saved = ""
    if exportar_csv:
        csv_text = result_to_csv(result)
        from pathlib import Path
        out = Path(csv_output_path).expanduser() if csv_output_path else (
            Path.home() / "Desktop" / "edificabilidad.csv"
        )
        out.write_text(csv_text, encoding="utf-8")
        csv_path_saved = str(out)

    tabla = [
        {"parametro": "Techo edificable máximo", "valor": result.techo_edificable_m2, "unidad": "m²"},  # noqa: E501
        {"parametro": "Ocupación máxima", "valor": result.ocupacion_max_m2, "unidad": "m²"},
        {"parametro": "Superficie por planta", "valor": result.superficie_por_planta, "unidad": "m²"},  # noqa: E501
        {"parametro": "Altura máxima", "valor": result.altura_max_m, "unidad": "m"},
        {"parametro": "Número de plantas", "valor": result.num_plantas, "unidad": "plantas"},
        {"parametro": "Volumen máximo", "valor": result.volumen_max_m3, "unidad": "m³"},
        {"parametro": "Superficie libre", "valor": result.superficie_libre_m2, "unidad": "m²"},
        {"parametro": "% libre de parcela", "valor": result.pct_libre, "unidad": "%"},
        {"parametro": "Retranqueo frontal", "valor": result.retranqueo_frontal_m, "unidad": "m"},
        {"parametro": "Retranqueo lateral", "valor": result.retranqueo_lateral_m, "unidad": "m"},
        {"parametro": "Retranqueo fondo", "valor": result.retranqueo_fondo_m, "unidad": "m"},
    ]

    out_data: dict[str, Any] = {"ok": True, "tabla": tabla}
    if csv_path_saved:
        out_data["csv_guardado_en"] = csv_path_saved
    return out_data
