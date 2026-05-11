"""Pre-análisis energético CTE DB-HE.

Asigna la zona climática CTE a un municipio/provincia español y devuelve
los valores máximos de transmitancia térmica (U en W/m²K) exigidos por
el CTE DB-HE 2022 para cada elemento de la envolvente.

Sin LLM — cálculo puro a partir de tablas de referencia.
"""

from __future__ import annotations

from typing import Any

# ── Zonas climáticas CTE DB-HE (por provincia / capital) ─────────────────────
# Fuente: Apéndice B del DB-HE (2022) — tabla B.1 simplificada.
# Clave: nombre de provincia normalizado (minúsculas, sin tildes).
# Muchos municipios pequenos se asignan por capital de provincia como
# aproximación conservadora; el profesional debe verificar.

_ZONA_POR_PROVINCIA: dict[str, str] = {
    # Zona A
    "santa_cruz_de_tenerife": "A3",
    "las_palmas":              "A3",
    # Zona B
    "almeria":    "B4",
    "cadiz":      "B3",
    "huelva":     "B4",
    "malaga":     "B3",
    "murcia":     "B3",
    "alicante":   "B3",
    # Zona C
    "sevilla":       "C4",
    "cordoba":       "C4",
    "granada":       "C3",
    "jaen":          "C4",
    "badajoz":       "C4",
    "caceres":       "C4",
    "toledo":        "C4",
    "ciudad_real":   "C4",
    "valencia":      "C3",
    "castellon":     "C2",
    "tarragona":     "C2",
    "baleares":      "C2",
    "barcelona":     "C2",
    "girona":        "C2",
    "lleida":        "D3",  # interior → zona D
    # Zona D
    "madrid":        "D3",
    "guadalajara":   "D2",
    "cuenca":        "D3",
    "albacete":      "D2",
    "la_rioja":      "D2",
    "navarra":       "D1",
    "aragon":        "D3",
    "zaragoza":      "D3",
    "huesca":        "D2",
    "teruel":        "D3",
    "salamanca":     "D2",
    "zamora":        "D2",
    "leon":          "D2",
    "valladolid":    "D2",
    "palencia":      "D2",
    "burgos":        "E1",
    "segovia":       "D2",
    "avila":         "E1",
    "soria":         "E1",
    "cantabria":     "D1",
    "asturias":      "D1",
    "pais_vasco":    "D1",
    "vizcaya":       "D1",
    "guipuzcoa":     "D1",
    "alava":         "D2",
    "pontevedra":    "C2",
    "a_coruna":      "C1",
    "lugo":          "D1",
    "ourense":       "D2",
}

# Alias normalizados frecuentes
_ALIAS: dict[str, str] = {
    "tenerife":          "santa_cruz_de_tenerife",
    "canarias":          "las_palmas",
    "baleares":          "baleares",
    "mallorca":          "baleares",
    "ibiza":             "baleares",
    "menorca":           "baleares",
    "pais vasco":        "pais_vasco",
    "euskadi":           "pais_vasco",
    "la rioja":          "la_rioja",
    "ciudad real":       "ciudad_real",
    "a coruña":          "a_coruna",
    "a coruna":          "a_coruna",
    "coruña":            "a_coruna",
    "coruna":            "a_coruna",
    "santa cruz de tenerife": "santa_cruz_de_tenerife",
    "las palmas":        "las_palmas",
    "vizcaya":           "vizcaya",
    "bizkaia":           "vizcaya",
    "guipuzcoa":         "guipuzcoa",
    "gipuzkoa":          "guipuzcoa",
    "alava":             "alava",
    "araba":             "alava",
}

# ── Transmitancias máximas W/m²K — CTE DB-HE tabla 3.1.1.a (2022) ────────────
# Claves: muro_fachada, cubierta, suelo, huecos (ventanas+puertas acristaladas)
_U_MAX: dict[str, dict[str, float]] = {
    "A1": {"muro_fachada": 0.94, "cubierta": 0.38, "suelo": 0.97, "huecos": 4.40},
    "A2": {"muro_fachada": 0.94, "cubierta": 0.38, "suelo": 0.97, "huecos": 4.40},
    "A3": {"muro_fachada": 0.94, "cubierta": 0.38, "suelo": 0.97, "huecos": 4.40},
    "A4": {"muro_fachada": 0.94, "cubierta": 0.38, "suelo": 0.97, "huecos": 4.40},
    "B3": {"muro_fachada": 0.82, "cubierta": 0.38, "suelo": 0.82, "huecos": 3.80},
    "B4": {"muro_fachada": 0.82, "cubierta": 0.38, "suelo": 0.82, "huecos": 3.80},
    "C1": {"muro_fachada": 0.56, "cubierta": 0.33, "suelo": 0.50, "huecos": 3.00},
    "C2": {"muro_fachada": 0.56, "cubierta": 0.33, "suelo": 0.50, "huecos": 3.00},
    "C3": {"muro_fachada": 0.56, "cubierta": 0.33, "suelo": 0.50, "huecos": 3.00},
    "C4": {"muro_fachada": 0.56, "cubierta": 0.33, "suelo": 0.50, "huecos": 3.00},
    "D1": {"muro_fachada": 0.41, "cubierta": 0.24, "suelo": 0.38, "huecos": 2.50},
    "D2": {"muro_fachada": 0.37, "cubierta": 0.22, "suelo": 0.36, "huecos": 2.30},
    "D3": {"muro_fachada": 0.37, "cubierta": 0.22, "suelo": 0.36, "huecos": 2.30},
    "E1": {"muro_fachada": 0.25, "cubierta": 0.17, "suelo": 0.30, "huecos": 1.80},
}

_SEVERIDAD: dict[str, str] = {
    "A": "Muy cálida — mínima demanda calefacción, gestión de ganancias solares",
    "B": "Cálida — refrigeración estival prioritaria",
    "C": "Media — equilibrio calefacción/refrigeración",
    "D": "Fría — calefacción prioritaria, aislamiento reforzado",
    "E": "Muy fría — aislamiento máximo, puentes térmicos críticos",
}

_DESCRIPCION_ZONA: dict[str, str] = {
    "A1": "Zona A1 — Muy cálida, húmeda",
    "A2": "Zona A2 — Muy cálida, seca",
    "A3": "Zona A3 — Muy cálida, húmeda (Canarias)",
    "A4": "Zona A4 — Muy cálida, muy húmeda",
    "B3": "Zona B3 — Cálida, seca interior",
    "B4": "Zona B4 — Cálida, muy seca",
    "C1": "Zona C1 — Media, atlántica húmeda",
    "C2": "Zona C2 — Media, mediterránea costera",
    "C3": "Zona C3 — Media, interior suave",
    "C4": "Zona C4 — Media-cálida, interior",
    "D1": "Zona D1 — Fría, atlántica",
    "D2": "Zona D2 — Fría, meseta",
    "D3": "Zona D3 — Fría, interior",
    "E1": "Zona E1 — Muy fría, alta meseta / montaña",
}


def _normalizar(texto: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", texto.lower().strip())
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_str.replace(" ", "_")


def zona_climatica(municipio: str, provincia: str) -> str:
    """Return the CTE climate zone for a Spanish municipality/province.

    Falls back to 'D3' (national median) when the province is unknown.
    """
    for raw in (provincia, municipio):
        key = _normalizar(raw)
        if key in _ALIAS:
            key = _ALIAS[key]
        if key in _ZONA_POR_PROVINCIA:
            return _ZONA_POR_PROVINCIA[key]
    return "D3"


def analisis_energetico(municipio: str, provincia: str) -> dict[str, Any]:
    """Return pre-analysis energy data for the given location.

    No LLM involved — pure table lookups against CTE DB-HE 2022.
    """
    zona = zona_climatica(municipio, provincia)
    letra = zona[0]
    u_max = _U_MAX.get(zona, _U_MAX["D3"])

    return {
        "zona_climatica": zona,
        "descripcion_zona": _DESCRIPCION_ZONA.get(zona, zona),
        "severidad_climatica": _SEVERIDAD.get(letra, "—"),
        "transmitancias_maximas_W_m2K": {
            "Muro de fachada": u_max["muro_fachada"],
            "Cubierta":        u_max["cubierta"],
            "Suelo":           u_max["suelo"],
            "Huecos (ventanas/puertas acristaladas)": u_max["huecos"],
        },
        "recomendaciones": _recomendaciones(zona),
        "normativa": "CTE DB-HE 2022, Tabla 3.1.1.a",
        "aviso": (
            "Análisis preliminar orientativo. "
            "Requiere verificación con el Apéndice B del DB-HE "
            "y comprobación del municipio concreto."
        ),
    }


def _recomendaciones(zona: str) -> list[str]:
    letra = zona[0]
    num = int(zona[1]) if len(zona) > 1 and zona[1].isdigit() else 0
    recs: list[str] = []

    if letra in ("D", "E"):
        recs += [
            "Aislamiento exterior (SATE o fachada ventilada) recomendado",
            "Rotura de puente térmico en carpinterías obligatoria",
            "Doble o triple vidrio con gas argón",
        ]
    if letra == "E" or (letra == "D" and num >= 2):
        recs.append("Considerar VRF o bomba de calor de alta eficiencia")
    if letra in ("A", "B"):
        recs += [
            "Protecciones solares en fachadas Este/Oeste/Sur",
            "Cubierta ajardinada o alta reflectividad (cool roof)",
            "Ventilación natural cruzada prioritaria",
        ]
    if letra == "C":
        recs += [
            "Aislamiento en cubierta prioridad alta",
            "Ventanas con control solar en orientación Sur",
        ]

    recs.append(
        f"Consultar mapa de zonas climáticas del Apéndice B del CTE DB-HE "
        f"para confirmación de zona {zona}"
    )
    return recs


# ── Tool wrapper ──────────────────────────────────────────────────────────────

def tool_analisis_energetico(
    municipio: str,
    provincia: str,
) -> dict[str, Any]:
    """Pre-análisis energético CTE DB-HE para un municipio español.

    Devuelve zona climática, transmitancias máximas y recomendaciones.
    Sin LLM — cálculo puro.
    """
    try:
        return {"ok": True, **analisis_energetico(municipio, provincia)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def zonas_disponibles() -> list[str]:
    return list(_U_MAX.keys())
