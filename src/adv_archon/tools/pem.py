"""Calculadora de Presupuesto de Ejecución Material (PEM).

Módulos de referencia por tipología y calidad, basados en los baremos
orientativos de los Colegios de Arquitectos de España (valores 2024).
Sin LLM — cálculo puro.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── Módulos €/m² (PEM base sin IVA) ──────────────────────────────────────────
# Fuente: baremos orientativos COA España 2024.
# Estructura: tipología → calidad → €/m²
_MODULOS: dict[str, dict[str, float]] = {
    "residencial_unifamiliar": {
        "basica":    850.0,
        "media":    1150.0,
        "alta":     1500.0,
        "lujo":     2200.0,
    },
    "residencial_plurifamiliar": {
        "basica":    750.0,
        "media":    1000.0,
        "alta":     1350.0,
        "lujo":     2000.0,
    },
    "comercial": {
        "basica":    650.0,
        "media":     900.0,
        "alta":     1200.0,
        "lujo":     1800.0,
    },
    "oficinas": {
        "basica":    700.0,
        "media":     950.0,
        "alta":     1300.0,
        "lujo":     1900.0,
    },
    "industrial": {
        "basica":    400.0,
        "media":     550.0,
        "alta":      750.0,
        "lujo":     1100.0,
    },
    "equipamiento": {
        "basica":    800.0,
        "media":    1050.0,
        "alta":     1400.0,
        "lujo":     2000.0,
    },
    "hotelero": {
        "basica":    900.0,
        "media":    1250.0,
        "alta":     1700.0,
        "lujo":     2600.0,
    },
    "rehabilitacion": {
        "basica":    500.0,
        "media":     750.0,
        "alta":     1100.0,
        "lujo":     1800.0,
    },
}

# Factor zona geográfica (coste relativo al promedio nacional)
_FACTOR_ZONA: dict[str, float] = {
    "madrid":       1.15,
    "barcelona":    1.18,
    "pais_vasco":   1.20,
    "navarra":      1.12,
    "baleares":     1.10,
    "canarias":     1.05,
    "cataluna":     1.10,
    "andalucia":    0.95,
    "comunidad_valenciana": 0.97,
    "castilla_leon": 0.93,
    "castilla_mancha": 0.90,
    "galicia":      0.92,
    "aragon":       0.95,
    "murcia":       0.93,
    "extremadura":  0.88,
    "asturias":     0.95,
    "cantabria":    0.97,
    "rioja":        0.93,
    "nacional":     1.00,
}

# Honorarios orientativos (% sobre PEM) — escala decreciente
def _honorarios_pct(pem: float) -> float:
    if pem <= 150_000:
        return 0.060
    if pem <= 300_000:
        return 0.055
    if pem <= 600_000:
        return 0.050
    if pem <= 1_200_000:
        return 0.045
    return 0.040


@dataclass(slots=True)
class PEMResult:
    # Entradas
    superficie_construida_m2: float
    tipologia: str
    calidad: str
    zona: str
    num_plantas: int
    superficie_sótano_m2: float
    # Módulos aplicados
    modulo_base_eur_m2: float
    factor_zona: float
    modulo_final_eur_m2: float
    # Resultados
    pem_eur: float
    pem_con_beneficio_industrial_eur: float   # PEM × 1.13 (GG 13% + BI 6%)
    pec_sin_iva_eur: float                    # PEM + honorarios + licencia
    pec_con_iva_eur: float                    # PEC × 1.21
    honorarios_tecnicos_eur: float
    licencia_obras_eur: float                 # ~4% PEM (ICIO municipal orientativo)
    honorarios_pct: float
    desglose: list[dict[str, Any]]


def calcular_pem(
    superficie_construida_m2: float,
    tipologia: str = "residencial_unifamiliar",
    calidad: str = "media",
    zona: str = "nacional",
    num_plantas: int = 1,
    superficie_sótano_m2: float = 0.0,
) -> PEMResult:
    """Calculate the Presupuesto de Ejecución Material for a building project.

    All monetary values are in EUR (without IVA unless stated).
    """
    tip = tipologia.lower().replace(" ", "_").replace("á", "a").replace("ó", "o")
    cal = calidad.lower()
    zon = zona.lower().replace(" ", "_").replace("á", "a").replace("ó", "o")

    if tip not in _MODULOS:
        tip = "residencial_unifamiliar"
    if cal not in _MODULOS[tip]:
        cal = "media"
    factor_z = _FACTOR_ZONA.get(zon, 1.0)

    modulo_base = _MODULOS[tip][cal]
    # Sótano tiene un sobrecoste del 30 % sobre el módulo base
    modulo_sotano = modulo_base * 1.30 * factor_z
    modulo_final = modulo_base * factor_z

    pem_sup = superficie_construida_m2 * modulo_final
    pem_sot = superficie_sótano_m2 * modulo_sotano
    pem = round(pem_sup + pem_sot, 2)

    pem_con_bi = round(pem * 1.13, 2)          # GG 13% + BI 6% ≈ PEC obra
    hon_pct = _honorarios_pct(pem)
    honorarios = round(pem * hon_pct, 2)
    licencia = round(pem * 0.04, 2)             # ICIO 4% orientativo
    pec_sin_iva = round(pem_con_bi + honorarios + licencia, 2)
    pec_con_iva = round(pec_sin_iva * 1.21, 2)

    desglose: list[dict[str, Any]] = [
        {"concepto": "Superficie construida", "valor": superficie_construida_m2, "unidad": "m²"},
        {"concepto": "Superficie sótano", "valor": superficie_sótano_m2, "unidad": "m²"},
        {"concepto": "Tipología",                  "valor": tipologia,                "unidad": ""},
        {"concepto": "Calidad",                    "valor": calidad,                  "unidad": ""},
        {"concepto": "Zona geográfica",            "valor": zona,                     "unidad": ""},
        {"concepto": "Módulo base", "valor": modulo_base, "unidad": "€/m²"},
        {"concepto": "Factor zona", "valor": factor_z, "unidad": "×"},
        {"concepto": "Módulo final aplicado", "valor": modulo_final, "unidad": "€/m²"},
        {"concepto": "PEM", "valor": pem, "unidad": "€"},
        {"concepto": "PEM + GG/BI (×1.13)", "valor": pem_con_bi, "unidad": "€"},
        {"concepto": f"Honorarios técnicos ({hon_pct*100:.1f}%)", "valor": honorarios, "unidad": "€"},  # noqa: E501
        {"concepto": "Licencia de obras (ICIO ~4%)", "valor": licencia, "unidad": "€"},
        {"concepto": "PEC total sin IVA", "valor": pec_sin_iva, "unidad": "€"},
        {"concepto": "PEC total con IVA (21%)", "valor": pec_con_iva, "unidad": "€"},
    ]

    return PEMResult(
        superficie_construida_m2=superficie_construida_m2,
        tipologia=tipologia,
        calidad=calidad,
        zona=zona,
        num_plantas=num_plantas,
        superficie_sótano_m2=superficie_sótano_m2,
        modulo_base_eur_m2=modulo_base,
        factor_zona=factor_z,
        modulo_final_eur_m2=modulo_final,
        pem_eur=pem,
        pem_con_beneficio_industrial_eur=pem_con_bi,
        pec_sin_iva_eur=pec_sin_iva,
        pec_con_iva_eur=pec_con_iva,
        honorarios_tecnicos_eur=honorarios,
        licencia_obras_eur=licencia,
        honorarios_pct=hon_pct,
        desglose=desglose,
    )


def result_to_csv(result: PEMResult) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Concepto", "Valor", "Unidad"])
    for row in result.desglose:
        writer.writerow([row["concepto"], row["valor"], row["unidad"]])
    return buf.getvalue()


def tipologias_disponibles() -> list[str]:
    return list(_MODULOS.keys())


def zonas_disponibles() -> list[str]:
    return list(_FACTOR_ZONA.keys())


# ── Tool wrapper ──────────────────────────────────────────────────────────────

def tool_calcular_pem(
    superficie_construida_m2: float,
    tipologia: str = "residencial_unifamiliar",
    calidad: str = "media",
    zona: str = "nacional",
    num_plantas: int = 1,
    superficie_sótano_m2: float = 0.0,
    exportar_csv: bool = False,
    csv_output_path: str = "",
) -> dict[str, Any]:
    """Calculate PEM (Presupuesto de Ejecución Material) for a building project."""
    try:
        result = calcular_pem(
            superficie_construida_m2=superficie_construida_m2,
            tipologia=tipologia,
            calidad=calidad,
            zona=zona,
            num_plantas=num_plantas,
            superficie_sótano_m2=superficie_sótano_m2,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    csv_saved = ""
    if exportar_csv:
        csv_text = result_to_csv(result)
        out = (
            Path(csv_output_path).expanduser()
            if csv_output_path
            else Path.home() / "Desktop" / "presupuesto_pem.csv"
        )
        out.write_text(csv_text, encoding="utf-8")
        csv_saved = str(out)

    out_data: dict[str, Any] = {
        "ok": True,
        "desglose": result.desglose,
        "resumen": {
            "PEM": f"{result.pem_eur:,.0f} €",
            "PEC sin IVA": f"{result.pec_sin_iva_eur:,.0f} €",
            "PEC con IVA (21%)": f"{result.pec_con_iva_eur:,.0f} €",
            "Honorarios técnicos": f"{result.honorarios_tecnicos_eur:,.0f} €",
            "Licencia obras (ICIO)": f"{result.licencia_obras_eur:,.0f} €",
        },
        "tipologias_disponibles": tipologias_disponibles(),
        "zonas_disponibles": zonas_disponibles(),
    }
    if csv_saved:
        out_data["csv_guardado_en"] = csv_saved
    return out_data
