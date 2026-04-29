from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber


@dataclass(slots=True)
class PlanMeasurement:
    value: float
    unit: str
    context: str


@dataclass
class PlanData:
    path: str
    raw_text: str
    page_count: int
    measurements: list[PlanMeasurement] = field(default_factory=list)
    areas_m2: list[PlanMeasurement] = field(default_factory=list)
    heights_m: list[PlanMeasurement] = field(default_factory=list)
    floors: list[int] = field(default_factory=list)
    use_zones: list[str] = field(default_factory=list)
    setbacks_m: list[PlanMeasurement] = field(default_factory=list)
    plot_coverage: list[str] = field(default_factory=list)
    building_use: list[str] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)


# ------------------------------------------------------------------ #
# Regex patterns                                                       #
# ------------------------------------------------------------------ #

_NUM = r"(\d+(?:[.,]\d+)?)"

_AREA_RE = re.compile(
    rf"{_NUM}\s*(?:m[²2]|metros?\s*cuadrados?|m\s*2)", re.IGNORECASE
)
_HEIGHT_RE = re.compile(
    rf"{_NUM}\s*(?:m\.?\s*(?:de\s*altura)?|metros?\s*(?:de\s*altura)?)\b", re.IGNORECASE
)
_FLOOR_RE = re.compile(
    r"(?:(\d+)\s*(?:plantas?|pisos?|alturas?))|(?:planta\s*(\d+|baja|primera|segunda|tercera|cuarta))",
    re.IGNORECASE,
)
_SETBACK_RE = re.compile(
    rf"{_NUM}\s*(?:m\.?\s*(?:de\s*retranqueo)?|metros?\s*(?:de\s*retranqueo)?)",
    re.IGNORECASE,
)
_USE_ZONE_RE = re.compile(
    r"(?:uso|zona|calificaci[oó]n)\s*[:\-]?\s*([A-ZÁÉÍÓÚÜ][^\n,;\.]{3,60})",
    re.IGNORECASE,
)
_COVERAGE_RE = re.compile(
    r"(?:ocupaci[oó]n|coeficiente|edificabilidad|parcela)\s*[:\-]?\s*([^\n,;\.]{3,60})",
    re.IGNORECASE,
)
_BUILDING_USE_KEYWORDS = {
    "residencial", "vivienda", "comercial", "industrial", "terciario",
    "dotacional", "equipamiento", "garaje", "aparcamiento", "oficinas",
    "hotel", "hostelería", "almacén", "nave", "taller",
}

_FLOOR_ORDINALS = {
    "baja": 0, "primera": 1, "segundo": 2, "tercera": 3, "cuarta": 4,
}


def read_plan(path: str) -> PlanData:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Plan not found: {target}")

    suffix = target.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(target)
    raise ValueError(f"Unsupported plan format: {suffix}. Use PDF.")


def _read_pdf(path: Path) -> PlanData:
    pages_text: list[str] = []
    tables: list[dict[str, Any]] = []

    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            pages_text.append(text)

            for tbl in page.extract_tables() or []:
                if tbl and len(tbl) > 1:
                    headers = [str(c).strip() if c else "" for c in tbl[0]]
                    rows = []
                    for row in tbl[1:]:
                        rows.append(
                            {headers[i]: str(c).strip() if c else "" for i, c in enumerate(row)}
                        )
                    tables.append({"page": page_num, "headers": headers, "rows": rows})

    raw_text = "\n\n".join(pages_text)
    data = PlanData(
        path=str(path),
        raw_text=raw_text,
        page_count=page_count,
        tables=tables,
    )
    _extract_measurements(data)
    return data


def _extract_measurements(data: PlanData) -> None:
    text = data.raw_text

    for m in _AREA_RE.finditer(text):
        val = _parse_float(m.group(1))
        ctx = _context(text, m.start(), m.end())
        data.areas_m2.append(PlanMeasurement(value=val, unit="m²", context=ctx))

    for m in _HEIGHT_RE.finditer(text):
        val = _parse_float(m.group(1))
        if 0 < val < 200:
            ctx = _context(text, m.start(), m.end())
            data.heights_m.append(PlanMeasurement(value=val, unit="m", context=ctx))

    for m in _FLOOR_RE.finditer(text):
        num_str = m.group(1) or m.group(2) or ""
        num_str = num_str.lower().strip()
        if num_str in _FLOOR_ORDINALS:
            data.floors.append(_FLOOR_ORDINALS[num_str])
        else:
            try:
                data.floors.append(int(num_str))
            except ValueError:
                pass

    for m in _SETBACK_RE.finditer(text):
        val = _parse_float(m.group(1))
        if 0 < val < 100:
            ctx = _context(text, m.start(), m.end())
            data.setbacks_m.append(PlanMeasurement(value=val, unit="m", context=ctx))

    seen_zones: set[str] = set()
    for m in _USE_ZONE_RE.finditer(text):
        zone = m.group(1).strip()[:80]
        if zone not in seen_zones:
            seen_zones.add(zone)
            data.use_zones.append(zone)

    seen_cov: set[str] = set()
    for m in _COVERAGE_RE.finditer(text):
        cov = m.group(1).strip()[:80]
        if cov not in seen_cov:
            seen_cov.add(cov)
            data.plot_coverage.append(cov)

    lowered = text.lower()
    for keyword in _BUILDING_USE_KEYWORDS:
        if keyword in lowered and keyword not in data.building_use:
            data.building_use.append(keyword)

    data.floors = sorted(set(data.floors))


def plan_to_summary(data: PlanData) -> str:
    """Produce a concise structured summary for LLM consumption."""
    lines: list[str] = [
        f"Plano: {Path(data.path).name}",
        f"Páginas: {data.page_count}",
    ]

    if data.building_use:
        lines.append(f"Usos detectados: {', '.join(data.building_use)}")

    if data.use_zones:
        lines.append("Zonas/calificaciones:")
        for z in data.use_zones[:6]:
            lines.append(f"  - {z}")

    if data.floors:
        lines.append(f"Plantas: {', '.join(str(f) for f in data.floors)}")

    if data.heights_m:
        unique_h = sorted({m.value for m in data.heights_m})[:5]
        lines.append(f"Alturas detectadas (m): {', '.join(str(h) for h in unique_h)}")

    if data.areas_m2:
        unique_a = sorted({m.value for m in data.areas_m2}, reverse=True)[:5]
        lines.append(f"Superficies detectadas (m²): {', '.join(str(a) for a in unique_a)}")

    if data.setbacks_m:
        unique_s = sorted({m.value for m in data.setbacks_m})[:4]
        lines.append(f"Retranqueos detectados (m): {', '.join(str(s) for s in unique_s)}")

    if data.plot_coverage:
        lines.append("Ocupación/edificabilidad:")
        for c in data.plot_coverage[:4]:
            lines.append(f"  - {c}")

    if data.tables:
        lines.append(f"Tablas en el documento: {len(data.tables)}")
        for tbl in data.tables[:2]:
            lines.append(f"  Página {tbl['page']}: {', '.join(tbl['headers'][:6])}")

    lines.append("\n--- Extracto de texto ---")
    lines.append(data.raw_text[:3000])

    return "\n".join(lines)


def _parse_float(s: str) -> float:
    return float(s.replace(",", "."))


def _context(text: str, start: int, end: int, window: int = 80) -> str:
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    return text[lo:hi].replace("\n", " ").strip()
