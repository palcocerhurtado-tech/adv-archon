from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus
from urllib.request import urlopen

_BOE_API = "https://www.boe.es/api.php"
_BOE_BASE = "https://www.boe.es"
_TIMEOUT = 15


@dataclass(slots=True)
class BoeItem:
    identificador: str
    titulo: str
    fecha: str
    seccion: str
    departamento: str
    url_html: str
    url_pdf: str
    extracto: str = ""


@dataclass(slots=True)
class BoeTextResult:
    identificador: str
    titulo: str
    fecha: str
    texto: str
    url: str


def boe_search(query: str, *, max_results: int = 5) -> list[BoeItem]:
    """Search the BOE full-text index. Returns up to *max_results* items."""
    encoded = quote_plus(query)
    url = f"{_BOE_API}?op=search&q={encoded}&lang=es&ws=2"
    try:
        with urlopen(url, timeout=_TIMEOUT) as resp:  # noqa: S310
            raw = resp.read()
    except Exception as exc:
        raise RuntimeError(f"Error conectando con el BOE: {exc}") from exc

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RuntimeError(f"Respuesta BOE no parseable: {exc}") from exc

    items: list[BoeItem] = []
    for result in root.findall(".//resultado"):
        ident = _text(result, "identificador")
        if not ident:
            continue
        items.append(
            BoeItem(
                identificador=ident,
                titulo=_text(result, "titulo") or "(sin título)",
                fecha=_text(result, "fecha_publicacion") or "",
                seccion=_text(result, "seccion") or "",
                departamento=_text(result, "departamento") or "",
                url_html=_text(result, "url_html") or f"{_BOE_BASE}/buscar/doc.php?id={ident}",
                url_pdf=_text(result, "url_pdf") or "",
                extracto=_clean(_text(result, "extracto") or ""),
            )
        )
        if len(items) >= max_results:
            break
    return items


def boe_fetch_text(identificador: str) -> BoeTextResult:
    """Fetch the full text of a BOE document by its identifier (e.g. BOE-A-2022-1234)."""
    url = f"{_BOE_API}?op=getXmlBoletin&id={identificador}&lang=es"
    try:
        with urlopen(url, timeout=_TIMEOUT) as resp:  # noqa: S310
            raw = resp.read()
    except Exception as exc:
        raise RuntimeError(f"Error obteniendo documento BOE {identificador}: {exc}") from exc

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RuntimeError(f"Respuesta BOE no parseable: {exc}") from exc

    titulo = _text(root, ".//titulo") or identificador
    fecha = _text(root, ".//fecha_publicacion") or ""
    url_html = _text(root, ".//url_html") or f"{_BOE_BASE}/buscar/doc.php?id={identificador}"

    # Gather all text nodes under <texto> elements
    partes: list[str] = []
    for elem in root.iter("texto"):
        t = (elem.text or "").strip()
        if t:
            partes.append(t)
    if not partes:
        # Fallback: extract all text content
        partes = [_clean(ET.tostring(root, encoding="unicode", method="text"))]

    return BoeTextResult(
        identificador=identificador,
        titulo=titulo,
        fecha=fecha,
        texto="\n\n".join(partes),
        url=url_html,
    )


# ── Tool wrappers ──────────────────────────────────────────────────────────────

def tool_boe_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Tool wrapper: search BOE and return structured results."""
    try:
        items = boe_search(query, max_results=max_results)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc), "results": []}
    return {
        "ok": True,
        "total": len(items),
        "results": [
            {
                "identificador": it.identificador,
                "titulo": it.titulo,
                "fecha": it.fecha,
                "seccion": it.seccion,
                "departamento": it.departamento,
                "extracto": it.extracto,
                "url": it.url_html,
            }
            for it in items
        ],
    }


def tool_boe_fetch(identificador: str) -> dict[str, Any]:
    """Tool wrapper: fetch full text of a BOE document."""
    try:
        result = boe_fetch_text(identificador)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc), "texto": ""}
    return {
        "ok": True,
        "identificador": result.identificador,
        "titulo": result.titulo,
        "fecha": result.fecha,
        "texto": result.texto[:8000],   # cap to avoid context overflow
        "url": result.url,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _text(element: ET.Element, tag: str) -> str | None:
    found = element.find(tag)
    if found is None:
        return None
    return (found.text or "").strip() or None


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
