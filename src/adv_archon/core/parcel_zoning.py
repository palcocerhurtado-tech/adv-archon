"""Preliminary parcel zoning extraction from indexed municipal planning text."""
from __future__ import annotations

import re
from typing import Any

from adv_archon.core.pgou_store import PGOUChunk, PGOUStore

_ZONING_QUERY = (
    "clasificación calificación ordenanza zona uso permitido uso principal "
    "edificabilidad ocupación altura retranqueo alineación parcela"
)

_SIGNAL_TERMS = (
    "clasificación",
    "clasificacion",
    "calificación",
    "calificacion",
    "ordenanza",
    "zona",
    "uso permitido",
    "uso principal",
    "edificabilidad",
    "ocupación",
    "ocupacion",
    "altura máxima",
    "altura maxima",
    "retranqueo",
)


def query_parcel_zoning(
    store: PGOUStore,
    municipality: str,
    *,
    pgou_indexed: bool,
) -> dict[str, Any]:
    """
    Extract textual zoning clues from the indexed PGOU for a municipality.

    This is intentionally not a cadastral-geometry overlay. It only surfaces
    candidate planning parameters found in indexed text and flags that the exact
    parcel ordinance still requires map/plan confirmation.
    """
    result: dict[str, Any] = {
        "queried": False,
        "available": False,
        "classification": "",
        "zoning": "",
        "ordinance": "",
        "allowed_uses": [],
        "buildability": "",
        "occupancy": "",
        "height": "",
        "setbacks": "",
        "source": "PGOU municipal indexado",
        "method": "búsqueda textual preliminar en normativa PGOU indexada",
        "requires_map_crossing": True,
        "confidence": "low",
        "excerpts": [],
        "error": "",
    }

    municipality = municipality.strip()
    if not municipality or not pgou_indexed:
        result["error"] = "PGOU municipal no indexado; no se puede extraer zonificación textual."
        return result

    result["queried"] = True
    try:
        search = store.search(_ZONING_QUERY, municipality=municipality, limit=8)
    except Exception as exc:
        result["error"] = str(exc)[:160]
        return result

    candidate_chunks = [chunk for chunk in search.chunks if _has_zoning_signal(chunk)]
    if not candidate_chunks:
        result["error"] = (
            "No se han encontrado referencias textuales claras a ordenanza, "
            "calificación o parámetros urbanísticos en los chunks PGOU indexados."
        )
        return result

    combined = "\n".join(chunk.text for chunk in candidate_chunks)
    result["available"] = True
    result["classification"] = _extract_first(
        combined,
        (
            r"clasificaci[oó]n(?:\s+del\s+suelo)?\s*[:\-]?\s*([^\.;\n]{3,100})",
            r"suelo\s+(urbano(?:\s+consolidado)?|urbanizable|no urbanizable[^\.;\n]{0,80})",
        ),
    )
    result["zoning"] = _extract_first(
        combined,
        (
            r"calificaci[oó]n(?:\s+urban[íi]stica)?\s*[:\-]?\s*([^\.;\n]{3,100})",
            r"zona\s+([A-ZÁÉÍÓÚÜÑ0-9][^\.;\n]{2,90})",
        ),
    )
    result["ordinance"] = _extract_first(
        combined,
        (
            r"ordenanza(?:\s+de\s+aplicaci[oó]n)?\s*[:\-]?\s*([^\.;\n]{2,100})",
            r"ordenanza\s+([A-ZÁÉÍÓÚÜÑ]{1,8}[\w\-. ]{0,60})",
        ),
    )
    result["allowed_uses"] = _extract_uses(combined)
    result["buildability"] = _extract_first(
        combined,
        (
            r"edificabilidad(?:\s+m[aá]xima)?\s*[:\-]?\s*([^\.;\n]{2,80})",
        ),
    )
    result["occupancy"] = _extract_first(
        combined,
        (
            r"ocupaci[oó]n(?:\s+m[aá]xima)?\s*[:\-]?\s*([^\.;\n]{2,80})",
        ),
    )
    result["height"] = _extract_first(
        combined,
        (
            r"altura(?:\s+m[aá]xima)?\s*[:\-]?\s*([^\.;\n]{2,80})",
            r"n[uú]mero\s+m[aá]ximo\s+de\s+plantas\s*[:\-]?\s*([^\.;\n]{2,80})",
        ),
    )
    result["setbacks"] = _extract_first(
        combined,
        (
            r"retranqueos?\s*[:\-]?\s*([^\.;\n]{2,100})",
            r"alineaciones?\s*[:\-]?\s*([^\.;\n]{2,100})",
        ),
    )
    result["source"] = _first_source(candidate_chunks)
    result["confidence"] = "medium" if _has_structured_value(result) else "low"
    result["excerpts"] = [_chunk_excerpt(chunk) for chunk in candidate_chunks[:4]]
    return result


def _has_zoning_signal(chunk: PGOUChunk) -> bool:
    haystack = f"{chunk.article_ref} {chunk.title} {chunk.text}".lower()
    return any(term in haystack for term in _SIGNAL_TERMS)


def _extract_first(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_value(match.group(1))
    return ""


def _extract_uses(text: str) -> list[str]:
    value = _extract_first(
        text,
        (
            r"usos?\s+permitidos?\s*[:\-]?\s*([^\.;\n]{3,140})",
            r"uso\s+principal\s*[:\-]?\s*([^\.;\n]{3,120})",
            r"uso\s+caracter[íi]stico\s*[:\-]?\s*([^\.;\n]{3,120})",
        ),
    )
    if not value:
        return []
    parts = re.split(r",|;|\sy\s|\se\s", value)
    return [_clean_value(part) for part in parts if _clean_value(part)][:6]


def _clean_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" :-–—\t\r\n")
    return cleaned[:140]


def _has_structured_value(result: dict[str, Any]) -> bool:
    keys = (
        "classification",
        "zoning",
        "ordinance",
        "buildability",
        "occupancy",
        "height",
        "setbacks",
    )
    return any(str(result.get(key) or "").strip() for key in keys) or bool(result["allowed_uses"])


def _first_source(chunks: list[PGOUChunk]) -> str:
    for chunk in chunks:
        if chunk.source:
            return chunk.source
    return "PGOU municipal indexado"


def _chunk_excerpt(chunk: PGOUChunk) -> dict[str, str]:
    text = re.sub(r"\s+", " ", chunk.text).strip()
    return {
        "article_ref": chunk.article_ref,
        "title": chunk.title,
        "text": text[:360],
        "source": chunk.source,
    }
