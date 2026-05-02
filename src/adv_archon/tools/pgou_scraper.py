"""PGOU auto-scraper: fetches and indexes Spanish municipal urban regulations."""
from __future__ import annotations

import io
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

import httpx
import pdfplumber

from adv_archon.core.pgou_store import PGOUStore

# ---------------------------------------------------------------------------
# Municipality source catalogue
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class MuniSource:
    name: str                    # canonical display name
    url: str                     # primary URL (PDF or HTML)
    kind: str                    # "pdf" | "html" | "boe"
    fallback_query: str          # DuckDuckGo search query if primary fails
    notes: str = ""              # free-text notes


# fmt: off
SOURCES: list[MuniSource] = [
    # ── Grandes ciudades ────────────────────────────────────────────────
    MuniSource(
        name="Madrid",
        url="https://www.madrid.es/UnidadesDescentralizadas/UDCUrbanismo/PGOUM/Normativa/ficheros/NormativaUrbanistica.pdf",
        kind="pdf",
        fallback_query="PGOU Madrid normativa urbanística vigente texto articulado PDF",
    ),
    MuniSource(
        name="Barcelona",
        url="https://ajuntament.barcelona.cat/pla-ordenacio-urbanistica/sites/default/files/2023-10/MPGM_text_refos.pdf",
        kind="pdf",
        fallback_query="PGOU Barcelona PGM texto refundido normativa urbanística PDF",
    ),
    MuniSource(
        name="Valencia",
        url="https://www.valencia.es/cas/urbanismo/VisorNormativaUrbanistica",
        kind="html",
        fallback_query="PGOU Valencia PGOU normativa urbanística vigente PDF texto articulado",
    ),
    MuniSource(
        name="Sevilla",
        url="https://www.sevilla.org/urbanismo/pgou/normativa/normativa-pgou-sevilla.pdf",
        kind="pdf",
        fallback_query="PGOU Sevilla 2006 normativa urbanística texto articulado PDF",
    ),
    MuniSource(
        name="Zaragoza",
        url="https://www.zaragoza.es/sede/portal/urbanismo/plan-general/normativa",
        kind="html",
        fallback_query="PGOU Zaragoza Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Málaga",
        url="https://www.malaga.eu/urbanismo/pgou/normativa-urbanistica.pdf",
        kind="pdf",
        fallback_query="PGOU Málaga Plan General normativa urbanística PDF vigente",
    ),
    MuniSource(
        name="Murcia",
        url="https://www.murcia.es/urbanismo/normativa/pgm-normativa.pdf",
        kind="pdf",
        fallback_query="Plan General Municipal Murcia normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Palma",
        url="https://www.palma.cat/portal/PALMAURL/planeamiento/pgou-palma.pdf",
        kind="pdf",
        fallback_query="PGOU Palma Mallorca normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Las Palmas de Gran Canaria",
        url="https://www.laspalmasgc.es/export/sites/default/es/urbanismo/pgou/normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Las Palmas de Gran Canaria normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Bilbao",
        url="https://www.bilbao.eus/urbanismo/pgou/normas-urbanisticas.pdf",
        kind="pdf",
        fallback_query="PGOU Bilbao Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Alicante",
        url="https://www.alicante.es/es/contenidos/plan-general/normativa-urbanistica",
        kind="html",
        fallback_query="PGOU Alicante Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Córdoba",
        url="https://www.cordoba.es/urbanismo/pgou/normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Córdoba Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Valladolid",
        url="https://www.valladolid.es/es/temas/hacemos/urbanismo/planeamiento/plan-general/normativa.ficheros/normas-urbanisticas.pdf",
        kind="pdf",
        fallback_query="PGOU Valladolid Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Vigo",
        url="https://www.vigo.org/urbanismo/planeamento/PXOM_normativa.pdf",
        kind="pdf",
        fallback_query="PXOM Vigo Plan Xeral normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Gijón",
        url="https://www.gijon.es/urbanismo/plan-general-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Gijón Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Hospitalet de Llobregat",
        url="https://www.l-h.cat/urbanisme/pla-general-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU L'Hospitalet de Llobregat normativa urbanística PDF texto",
    ),
    MuniSource(
        name="A Coruña",
        url="https://www.coruna.gal/urbanismo/pgom-normativa.pdf",
        kind="pdf",
        fallback_query="PGOM A Coruña Plan Xeral normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Vitoria-Gasteiz",
        url="https://www.vitoria-gasteiz.org/wb021/was/contenidoAction.do?uid=eu_96_5e18a89d_1460b5a15e4__7fcb",
        kind="html",
        fallback_query="PGOU Vitoria Gasteiz Plan General normativa urbanística PDF",
    ),
    MuniSource(
        name="Granada",
        url="https://www.granada.org/inet/urbanismo.nsf/normativa-pgou.pdf",
        kind="pdf",
        fallback_query="PGOU Granada Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Elche",
        url="https://www.elche.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Elche Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Oviedo",
        url="https://www.oviedo.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Oviedo Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Badalona",
        url="https://www.badalona.cat/ajuntament/urbanisme/normativa-pgm.pdf",
        kind="pdf",
        fallback_query="PGOU Badalona PGM normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Cartagena",
        url="https://www.cartagena.es/urbanismo/pgm-normativa.pdf",
        kind="pdf",
        fallback_query="PGM Cartagena Plan General Municipal normativa urbanística PDF",
    ),
    MuniSource(
        name="Terrassa",
        url="https://www.terrassa.cat/urbanisme/pla-general-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Terrassa normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Jerez de la Frontera",
        url="https://www.jerez.es/fileadmin/urbanismo/pgou/normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Jerez de la Frontera normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Sabadell",
        url="https://www.sabadell.cat/urbanisme/pla-general-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Sabadell normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Móstoles",
        url="https://www.mostoles.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Móstoles Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Santa Cruz de Tenerife",
        url="https://www.santacruzdetenerife.es/web/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Santa Cruz de Tenerife normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Pamplona",
        url="https://www.pamplona.es/urbanismo/pgm-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Pamplona Plan Municipal normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Almería",
        url="https://www.almeriaciudad.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Almería Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Fuenlabrada",
        url="https://www.fuenlabrada.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Fuenlabrada Plan General normativa urbanística PDF",
    ),
    MuniSource(
        name="Leganés",
        url="https://www.leganes.org/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Leganés Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Alcalá de Henares",
        url="https://www.ayto-alcaladehenares.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Alcalá de Henares normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Donostia-San Sebastián",
        url="https://www.donostia.eus/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Donostia San Sebastian Plan General normativa urbanística PDF",
    ),
    MuniSource(
        name="Burgos",
        url="https://www.aytoburgos.es/urbanismo/pgou/normativa-urbanistica",
        kind="html",
        fallback_query="PGOU Burgos Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Santander",
        url="https://www.santander.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Santander Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Toledo",
        url="https://www.toledo.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Toledo Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Salamanca",
        url="https://www.salamanca.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Salamanca Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Huelva",
        url="https://www.huelva.es/portal/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Huelva Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Badajoz",
        url="https://www.aytobadajoz.es/urbanismo/pgm-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Badajoz Plan General Municipal normativa urbanística PDF",
    ),
    MuniSource(
        name="Logroño",
        url="https://www.logronyo.es/urbanismo/pgm-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Logroño Plan Municipal normativa urbanística PDF texto",
    ),
    MuniSource(
        name="León",
        url="https://www.aytoleon.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU León Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Cádiz",
        url="https://www.cadiz.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Cádiz Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Marbella",
        url="https://www.marbella.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Marbella Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Albacete",
        url="https://www.albacete.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Albacete Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Castellón de la Plana",
        url="https://www.castello.es/urbanismo/pgou-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Castellón de la Plana normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Tarragona",
        url="https://www.tarragona.cat/urbanisme/pla-general-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Tarragona Plan General normativa urbanística PDF texto",
    ),
    MuniSource(
        name="Lleida",
        url="https://www.paeria.cat/urbanisme/pla-general-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Lleida Plan General normativa urbanística PDF texto articulado",
    ),
    MuniSource(
        name="Girona",
        url="https://www.girona.cat/urbanisme/pla-general-normativa.pdf",
        kind="pdf",
        fallback_query="PGOU Girona Plan General normativa urbanística PDF texto articulado",
    ),
]
# fmt: on


def _canonicalize_name(name: str) -> str:
    nfd = unicodedata.normalize("NFD", name.lower().strip())
    ascii_name = "".join(char for char in nfd if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")


# Index by canonical name for fast lookup
_SOURCES_BY_CANONICAL: dict[str, MuniSource] = {}
for _s in SOURCES:
    _SOURCES_BY_CANONICAL[_canonicalize_name(_s.name)] = _s


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
}
_TIMEOUT = 30
_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB


@dataclass
class FetchResult:
    text: str
    source_url: str
    ok: bool
    error: str = ""
    pages_extracted: int = 0
    strategy: str = ""


class PGOUScraper:
    """Fetches and indexes PGOU text for Spanish municipalities."""

    def __init__(self, pgou_store: PGOUStore) -> None:
        self._store = pgou_store

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def list_available(self) -> list[str]:
        """Return display names of all municipalities in the catalogue."""
        return [s.name for s in SOURCES]

    def scrape_and_index(
        self,
        municipality: str,
        *,
        progress_cb: Any = None,
    ) -> dict[str, Any]:
        """
        Fetch PGOU text for a municipality and index it.
        Returns a dict with keys: ok, municipality, source_url, chunks, error, strategy.
        progress_cb(msg: str) called with status updates if provided.
        """
        def _progress(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)

        source = self._find_source(municipality)
        if source is None:
            return {
                "ok": False,
                "municipality": municipality,
                "error": (
                    f"Municipio '{municipality}' no está en el catálogo. "
                    f"Municipios disponibles: {', '.join(self.list_available()[:10])}..."
                ),
            }

        _progress(f"Descargando normativa de {source.name}...")
        result = self._fetch(source)

        if not result.ok:
            _progress(f"URL primaria falló ({result.error}). Probando búsqueda alternativa...")
            result = self._fetch_via_search(source, progress_cb=_progress)

        if not result.ok:
            return {
                "ok": False,
                "municipality": source.name,
                "source_url": result.source_url,
                "error": result.error,
            }

        _progress(f"Indexando {len(result.text):,} caracteres ({result.pages_extracted} pgs)...")
        chunks = self._store.index_text(
            result.text,
            municipality=source.name,
            source=result.source_url,
        )

        return {
            "ok": True,
            "municipality": source.name,
            "source_url": result.source_url,
            "chunks": chunks,
            "pages_extracted": result.pages_extracted,
            "strategy": result.strategy,
        }

    def scrape_all(
        self,
        *,
        skip_indexed: bool = True,
        progress_cb: Any = None,
        delay_s: float = 2.0,
    ) -> list[dict[str, Any]]:
        """Scrape all catalogued municipalities. Returns list of per-municipality results."""
        results: list[dict[str, Any]] = []
        indexed_names = {m.name for m in self._store.list_municipalities()}

        for source in SOURCES:
            if skip_indexed and source.name in indexed_names:
                if progress_cb:
                    progress_cb(f"[skip] {source.name} ya indexado")
                results.append({"ok": True, "municipality": source.name, "skipped": True})
                continue

            result = self.scrape_and_index(source.name, progress_cb=progress_cb)
            results.append(result)
            time.sleep(delay_s)

        return results

    # ------------------------------------------------------------------ #
    # Private: fetch strategies                                            #
    # ------------------------------------------------------------------ #

    def _find_source(self, municipality: str) -> MuniSource | None:
        return _SOURCES_BY_CANONICAL.get(_canonicalize_name(municipality))

    def _fetch(self, source: MuniSource) -> FetchResult:
        try:
            with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(source.url)
                resp.raise_for_status()
        except Exception as exc:
            return FetchResult(text="", source_url=source.url, ok=False,
                               error=str(exc)[:200], strategy="direct")

        content_type = resp.headers.get("content-type", "").lower()

        if "pdf" in content_type or source.url.lower().endswith(".pdf"):
            return self._parse_pdf(resp.content, source.url, strategy="direct_pdf")

        return self._parse_html(resp.text, source.url, strategy="direct_html")

    def _fetch_via_search(
        self,
        source: MuniSource,
        *,
        progress_cb: Any = None,
    ) -> FetchResult:
        """Try DuckDuckGo HTML search to find an alternative URL."""
        query = source.fallback_query
        search_url = f"https://html.duckduckgo.com/html/?q={httpx.QueryParams({'q': query})}"
        try:
            with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(search_url)
            candidates = _extract_search_result_urls(resp.text)
        except Exception as exc:
            return FetchResult(text="", source_url=source.url, ok=False,
                               error=f"Search failed: {exc}", strategy="search")

        for url in candidates[:5]:
            if any(blocked in url for blocked in ("duckduckgo.com", "google.com", "bing.com")):
                continue
            if progress_cb:
                progress_cb(f"  Probando {url[:80]}...")
            try:
                with httpx.Client(
                    headers=_HEADERS,
                    timeout=_TIMEOUT,
                    follow_redirects=True,
                ) as client:
                    r = client.get(url)
                    r.raise_for_status()
                ct = r.headers.get("content-type", "").lower()
                if "pdf" in ct or url.lower().endswith(".pdf"):
                    result = self._parse_pdf(r.content, url, strategy="search_pdf")
                else:
                    result = self._parse_html(r.text, url, strategy="search_html")
                if result.ok and len(result.text) > 500:
                    return result
            except Exception:
                continue

        return FetchResult(text="", source_url=source.url, ok=False,
                           error="No se encontró contenido válido en ninguna URL candidata.",
                           strategy="search")

    def _parse_pdf(self, data: bytes, url: str, *, strategy: str) -> FetchResult:
        if len(data) > _MAX_PDF_BYTES:
            return FetchResult(text="", source_url=url, ok=False,
                               error=f"PDF demasiado grande ({len(data) // 1024} KB)",
                               strategy=strategy)
        try:
            pages_text: list[str] = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    txt = page.extract_text() or ""
                    if txt.strip():
                        pages_text.append(txt)
            text = "\n\n".join(pages_text)
            if not text.strip():
                return FetchResult(text="", source_url=url, ok=False,
                                   error="PDF sin texto extraíble (posiblemente escaneado)",
                                   strategy=strategy)
            return FetchResult(
                text=text,
                source_url=url,
                ok=True,
                pages_extracted=len(pages_text),
                strategy=strategy,
            )
        except Exception as exc:
            return FetchResult(text="", source_url=url, ok=False,
                               error=f"Error procesando PDF: {exc}", strategy=strategy)

    def _parse_html(self, html: str, url: str, *, strategy: str) -> FetchResult:
        text = _html_to_text(html)
        if len(text) < 300:
            return FetchResult(text="", source_url=url, ok=False,
                               error="Página HTML con poco contenido textual", strategy=strategy)
        return FetchResult(
            text=text,
            source_url=url,
            ok=True,
            pages_extracted=1,
            strategy=strategy,
        )


# ---------------------------------------------------------------------------
# HTML helpers (no external dependency)
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"[ \t]{2,}")
_NL_RE = re.compile(r"\n{3,}")


def _html_to_text(html: str) -> str:
    text = _SCRIPT_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    import html as _html_mod
    text = _html_mod.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = _NL_RE.sub("\n\n", text)
    return text.strip()


_RESULT_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*result__url[^"]*"[^>]*href="([^"]+)"',
    re.IGNORECASE,
)
_UDDG_RE = re.compile(r'uddg=([^&"]+)', re.IGNORECASE)


def _extract_search_result_urls(html: str) -> list[str]:
    """Extract result URLs from DuckDuckGo HTML search page."""
    urls: list[str] = []
    for m in _RESULT_LINK_RE.finditer(html):
        href = m.group(1)
        # DuckDuckGo wraps URLs with uddg= param
        uddg = _UDDG_RE.search(href)
        if uddg:
            import urllib.parse
            url = urllib.parse.unquote(uddg.group(1))
        else:
            url = href
        if url.startswith("http"):
            urls.append(url)
    return urls
