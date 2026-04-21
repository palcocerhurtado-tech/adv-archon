from __future__ import annotations

import io
import warnings
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
import pytesseract  # type: ignore[import-untyped]
import trafilatura
from docx import Document
from openpyxl import load_workbook  # type: ignore[import-untyped]
from pdf2image import convert_from_path
from PIL import Image
from pptx import Presentation
from pypdf import PdfReader

IGNORED_DIRS = {".git", "node_modules", ".venv", "__pycache__"}
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".ts",
    ".js",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
    ".tsv",
    ".rst",
    ".ini",
}
IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".gif",
    ".webp",
}


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    if target.is_dir():
        raise IsADirectoryError(f"Expected file, got directory: {target}")

    text = _read_by_extension(target)

    lines = text.splitlines()
    start_index = max((start_line or 1) - 1, 0)
    end_index = end_line if end_line is not None else len(lines)
    clipped = lines[start_index:end_index]

    return ToolResult(
        name="read_file",
        payload={
            "path": str(target),
            "start_line": start_line or 1,
            "end_line": end_index,
            "content": "\n".join(clipped),
        },
    )


def list_dir(path: str, depth: int = 1) -> ToolResult:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"Expected directory, got file: {target}")

    entries = list(_walk(target, depth=depth))
    return ToolResult(
        name="list_dir",
        payload={
            "path": str(target),
            "depth": depth,
            "entries": entries,
        },
    )


def _walk(path: Path, *, depth: int, prefix: str = "") -> list[str]:
    if depth < 0:
        return []

    entries: list[str] = []
    children = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    for child in children:
        if child.name in IGNORED_DIRS:
            continue
        marker = "/" if child.is_dir() else ""
        entries.append(f"{prefix}{child.name}{marker}")
        if child.is_dir() and depth > 0:
            entries.extend(_walk(child, depth=depth - 1, prefix=f"{prefix}{child.name}/"))
    return entries


def _read_by_extension(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8", errors="replace")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            if suffix == ".pdf":
                return _read_pdf(path)
            if suffix == ".docx":
                return _read_docx(path)
            if suffix == ".xlsx":
                return _read_xlsx(path)
            if suffix == ".pptx":
                return _read_pptx(path)
            if suffix in {".html", ".htm"}:
                return _read_html(path)
            if suffix in IMAGE_EXTENSIONS:
                return _read_image_with_ocr(path)
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    fragments: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            fragments.append(extracted)

    table_text = _read_pdf_tables(path)
    if table_text:
        fragments.append(table_text)

    combined = "\n\n".join(fragment for fragment in fragments if fragment.strip())
    if combined.strip():
        return combined

    ocr_text = _ocr_pdf(path)
    if ocr_text:
        return ocr_text

    return (
        "No he podido extraer texto del PDF. "
        "Si es un PDF escaneado, instala `tesseract` y `poppler` para activar OCR."
    )


def _read_pdf_tables(path: Path) -> str:
    fragments: list[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                for table_index, table in enumerate(tables, start=1):
                    fragments.append(f"Page {page_index}, table {table_index}:")
                    for row in table:
                        values = [
                            cell.strip() if isinstance(cell, str) else str(cell or "")
                            for cell in row
                        ]
                        if any(value for value in values):
                            fragments.append("\t".join(values))
    except Exception:
        return ""
    return "\n".join(fragments)


def _ocr_pdf(path: Path) -> str:
    try:
        images = convert_from_path(str(path))
    except Exception:
        return ""
    fragments: list[str] = []
    for image in images:
        text = pytesseract.image_to_string(image)
        if text.strip():
            fragments.append(text)
    return "\n\n".join(fragments)


def _read_docx(path: Path) -> str:
    document = Document(str(path))
    fragments: list[str] = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            fragments.append(paragraph.text)
    for table in document.tables:
        for row in table.rows:
            values = [cell.text.strip() for cell in row.cells]
            if any(values):
                fragments.append("\t".join(values))
    return "\n".join(fragments)


def _read_xlsx(path: Path) -> str:
    workbook = load_workbook(path, read_only=True, data_only=True)
    fragments: list[str] = []
    for sheet in workbook.worksheets:
        fragments.append(f"# Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            values = ["" if value is None else str(value) for value in row]
            if any(values):
                fragments.append("\t".join(values))
    return "\n".join(fragments)


def _read_pptx(path: Path) -> str:
    presentation = Presentation(str(path))
    fragments: list[str] = []
    for index, slide in enumerate(presentation.slides, start=1):
        fragments.append(f"# Slide {index}")
        for shape in slide.shapes:
            if hasattr(shape, "text") and isinstance(shape.text, str) and shape.text.strip():
                fragments.append(shape.text.strip())
    return "\n".join(fragments)


def _read_html(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    extracted = trafilatura.extract(raw, include_links=True, include_tables=True)
    return extracted if extracted else raw


def _read_image_with_ocr(path: Path) -> str:
    with Image.open(path) as image:
        extracted = str(pytesseract.image_to_string(image))
    if extracted.strip():
        return extracted
    return "No he podido extraer texto mediante OCR."
