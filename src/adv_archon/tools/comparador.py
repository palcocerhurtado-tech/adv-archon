"""Comparador de parcelas — compara hasta 3 parcelas en una sola consulta."""

from __future__ import annotations

from typing import Any

from adv_archon.tools.edificabilidad import calcular_edificabilidad
from adv_archon.tools.energia import zona_climatica
from adv_archon.tools.pem import calcular_pem


def comparar_parcelas(parcelas: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare 2-3 building plots side by side.

    For each parcela, calculates edificabilidad, PEM estimate, and CTE climate zone.
    Returns a comparative table and an auto-generated recommendation.
    """
    if not parcelas or len(parcelas) < 2:
        return {"ok": False, "error": "Se requieren al menos 2 parcelas para comparar."}
    if len(parcelas) > 3:
        return {"ok": False, "error": "El comparador admite un máximo de 3 parcelas."}

    tabla: list[dict[str, Any]] = []

    for parcela in parcelas:
        nombre = parcela.get("nombre", "Parcela")
        try:
            # 1. Edificabilidad
            edif = calcular_edificabilidad(
                superficie_parcela=float(parcela["superficie_parcela_m2"]),
                coef_edificabilidad=float(parcela["coeficiente_edificabilidad"]),
                ocupacion_max_pct=float(parcela["ocupacion_maxima_pct"]),
                altura_max_m=float(parcela["altura_maxima_m"]),
                num_plantas=int(parcela["num_plantas"]),
            )

            techo = edif.techo_edificable_m2
            ocupacion = edif.ocupacion_max_m2

            # 2. PEM
            tipologia = parcela.get("tipologia", "residencial_unifamiliar")
            calidad = parcela.get("calidad", "media")
            zona_pem = parcela.get("zona", "nacional")

            pem_result = calcular_pem(
                superficie_construida_m2=techo,
                tipologia=tipologia,
                calidad=calidad,
                zona=zona_pem,
                num_plantas=int(parcela["num_plantas"]),
            )

            pem_eur = pem_result.pem_eur
            pec_con_iva_eur = pem_result.pec_con_iva_eur
            pem_eur_m2 = round(pem_eur / techo, 0) if techo > 0 else 0.0

            # 3. Zona CTE (optional)
            municipio = parcela.get("municipio", "")
            provincia = parcela.get("provincia", "")
            if municipio or provincia:
                zona_cte = zona_climatica(municipio or "", provincia or "")
            else:
                zona_cte = "—"

            tabla.append(
                {
                    "parcela": nombre,
                    "superficie_parcela_m2": float(parcela["superficie_parcela_m2"]),
                    "techo_edificable_m2": techo,
                    "ocupacion_m2": ocupacion,
                    "num_plantas": int(parcela["num_plantas"]),
                    "pem_eur": pem_eur,
                    "pec_con_iva_eur": pec_con_iva_eur,
                    "pem_eur_m2": pem_eur_m2,
                    "zona_cte": zona_cte,
                    "tipologia": tipologia,
                    "calidad": calidad,
                }
            )

        except Exception as exc:  # noqa: BLE001
            tabla.append(
                {
                    "parcela": nombre,
                    "error": str(exc),
                }
            )

    # Auto-generate recommendation from valid rows only
    valid = [row for row in tabla if "error" not in row]
    recomendacion = _generar_recomendacion(valid)

    return {
        "ok": True,
        "num_parcelas": len(parcelas),
        "tabla_comparativa": tabla,
        "recomendacion": recomendacion,
        "aviso": "Análisis orientativo — verificar con PGOU municipal vigente.",
    }


def _generar_recomendacion(filas: list[dict[str, Any]]) -> str:
    if not filas:
        return "No hay parcelas válidas para comparar."

    if len(filas) == 1:
        f = filas[0]
        return (
            f"Solo {f['parcela']} calculada correctamente: "
            f"{f['techo_edificable_m2']:,.0f} m² edificables a {f['pem_eur_m2']:,.0f} €/m²."
        )

    # Best techo (highest aprovechamiento)
    mejor_techo = max(filas, key=lambda r: r["techo_edificable_m2"])
    # Best PEM/m² (lowest unit cost)
    mejor_precio = min(filas, key=lambda r: r["pem_eur_m2"])

    if mejor_techo["parcela"] == mejor_precio["parcela"]:
        nombre = mejor_techo["parcela"]
        techo = mejor_techo["techo_edificable_m2"]
        precio = mejor_techo["pem_eur_m2"]
        return (
            f"{nombre} ofrece el mayor aprovechamiento ({techo:,.0f} m² edificables) "
            f"y el menor coste unitario ({precio:,.0f} €/m²), siendo la opción más ventajosa."
        )

    techo_val = mejor_techo["techo_edificable_m2"]
    precio_val = mejor_precio["pem_eur_m2"]
    return (
        f"{mejor_techo['parcela']} destaca por mayor aprovechamiento "
        f"({techo_val:,.0f} m² edificables); "
        f"{mejor_precio['parcela']} ofrece menor coste unitario "
        f"({precio_val:,.0f} €/m²). "
        "La elección depende de si se prioriza superficie o coste de construcción."
    )


# ── Tool wrapper ───────────────────────────────────────────────────────────────


def tool_comparar_parcelas(parcelas: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare 2-3 building plots side by side. Pure calculation — no LLM."""
    try:
        return comparar_parcelas(parcelas)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
