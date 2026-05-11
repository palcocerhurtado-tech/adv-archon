from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adv_archon.core.knowledge import KnowledgeStore

log = logging.getLogger(__name__)

# Detects PGOU article/section headings at line start.
# Captures: Artículo 12, Art. 3.1, CAPÍTULO I, SECCIÓN 2ª, TÍTULO III, DISPOSICIÓN ADICIONAL
_HEADING_RE = re.compile(
    r"^(?:"
    r"Art[ií]culo\s+\d+[\d\.]*"
    r"|Art\.\s*\d+[\d\.]*"
    r"|CAP[ÍI]TULO\s+[IVXLCDM\d]+"
    r"|SECCI[ÓO]N\s+[IVXLCDM\d\ªa-z]+"
    r"|T[ÍI]TULO\s+[IVXLCDM\d]+"
    r"|DISPOSICI[ÓO]N\s+\w+"
    r"|ANEXO\s+[IVXLCDM\d]+"
    r"|NORMA\s+\d+"
    r")",
    re.IGNORECASE,
)

_CHUNK_HARD_MAX = 2000   # chars: hard upper limit per chunk
_WINDOW_SIZE    = 1400   # chars: sliding window when no structure found
_WINDOW_OVERLAP = 200    # chars: overlap between windows


# ── Text extraction ────────────────────────────────────────────────────────────

def extract_pdf_text(path: Path) -> str:
    """Extract text from a PDF: pdfplumber first, OCR fallback for scanned pages."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required: uv add pdfplumber") from exc

    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if len(text.strip()) < 50:
                text = _ocr_page(page)
            pages.append(text)
    return "\n".join(pages)


def _ocr_page(page: object) -> str:
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError:
        return ""
    try:
        raw = page.pdf.stream.get_data()  # type: ignore[attr-defined]
        pnum = page.page_number           # type: ignore[attr-defined]
        images = convert_from_bytes(raw, first_page=pnum, last_page=pnum)
        if images:
            return pytesseract.image_to_string(images[0], lang="spa")
    except Exception as exc:
        log.debug("OCR falló en página: %s", exc)
    return ""


# ── Chunking ───────────────────────────────────────────────────────────────────

def chunk_by_article(text: str, source_title: str) -> list[tuple[str, str]]:
    """Split PGOU text into one chunk per article/section.

    Each chunk preserves the complete literal text of the article so the LLM
    can cite word-for-word. Falls back to sliding windows when no structure found.

    Returns list of (heading_title, full_body_text).
    """
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading = source_title
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if _HEADING_RE.match(stripped):
            if current_lines and "".join(current_lines).strip():
                sections.append((current_heading, current_lines))
            current_heading = stripped
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines and "".join(current_lines).strip():
        sections.append((current_heading, current_lines))

    # If no structure found, fall back to sliding windows
    if len(sections) <= 1:
        return _sliding_windows(text, source_title)

    chunks: list[tuple[str, str]] = []
    for heading, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        if len(body) <= _CHUNK_HARD_MAX:
            # Perfect: the full article fits in one chunk
            chunks.append((heading, body))
        else:
            # Article too long: split into sub-windows but keep heading context
            for i, (_, window_text) in enumerate(_sliding_windows(body, heading)):
                label = f"{heading} (parte {i + 1})"
                chunks.append((label, window_text))

    return chunks or _sliding_windows(text, source_title)


def _sliding_windows(text: str, title: str) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    start = 0
    part = 1
    while start < len(text):
        end = min(start + _WINDOW_SIZE, len(text))
        body = text[start:end].strip()
        if body:
            chunks.append((f"{title} — parte {part}", body))
        if end >= len(text):
            break
        start = end - _WINDOW_OVERLAP
        part += 1
    return chunks or [(title, text[:_WINDOW_SIZE].strip())]


# ── Ingestion pipeline ─────────────────────────────────────────────────────────

def ingest_pgou_pdf(
    pdf_path: Path,
    knowledge_store: KnowledgeStore,
    *,
    document_title: str | None = None,
    force: bool = False,
) -> int:
    """Full pipeline: extract → chunk per article → embed → upsert.

    Returns number of chunks ingested.
    Synthetic path per chunk: <pdf_stem>_chunk_NNNN.pgou
    """
    doc_title = document_title or pdf_path.stem.replace("_", " ").replace("-", " ")

    log.info("Extrayendo texto de %s…", pdf_path.name)
    text = extract_pdf_text(pdf_path)
    if not text.strip():
        log.warning("Sin texto extraído de %s", pdf_path)
        return 0

    log.info("Dividiendo en artículos…")
    chunks = chunk_by_article(text, doc_title)
    if not chunks:
        return 0

    log.info("Ingestando %d chunks en KnowledgeStore…", len(chunks))
    ingested = 0
    for i, (title, excerpt) in enumerate(chunks):
        chunk_path = pdf_path.parent / f"{pdf_path.stem}_chunk_{i:04d}.pgou"

        if not force:
            from contextlib import suppress
            with suppress(Exception):
                from adv_archon.core.knowledge import INDEXED_STATUS
                state = knowledge_store._file_state(str(chunk_path))  # noqa: SLF001
                if (
                    state is not None
                    and str(state.get("last_index_status", "")) == INDEXED_STATUS
                ):
                    log.debug("Chunk ya indexado, saltando: %s", chunk_path.name)
                    continue

        try:
            # Preserve full text — no truncation so citations are always complete
            safe_excerpt = excerpt[:_CHUNK_HARD_MAX]
            knowledge_store.ingest_chunk(
                path=chunk_path,
                title=title,
                excerpt=safe_excerpt,
                root=str(pdf_path.parent),
            )
            ingested += 1
        except Exception as exc:
            log.warning("Error ingestando chunk %d: %s", i, exc)

    log.info("Ingesta: %d/%d chunks añadidos.", ingested, len(chunks))
    return ingested
