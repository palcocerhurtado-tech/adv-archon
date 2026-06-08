# DOCX / XLSX / PDF — Plan de Integración

## 1. Dependencias nuevas (`pyproject.toml`)

```toml
[project.optional-dependencies]
export = [
  "python-docx>=1.1.2",
  "docxtpl>=0.18.0",
  "openpyxl>=3.1.2",
]
```

Instalación: `uv pip install "adv-archon[export]"`  
Las dependencias son **completamente locales** — ningún servicio externo requerido.

---

## 2. `tools/docx_generator.py`

### Interfaz pública

```python
def generate_docx(
    expediente_data: dict[str, Any],
    template_path: Path | None = None,
) -> bytes:
    """Devuelve los bytes de un .docx listo para guardar o descargar."""
```

### Estructura del documento generado

| Sección | Contenido | Estilo Word |
|---|---|---|
| Portada | Título expediente, dirección, municipio, fecha, logo | `Heading 1` + párrafo centrado |
| Resumen ejecutivo | Veredicto (VIABLE / CONDICIONADO / REVISAR) + 2-3 frases | `Heading 2` + custom `Verdict` |
| Tabla de afecciones | Filas: categoría, estado, fuente, observaciones | `Table Grid`, cabecera dorada RGB(201,168,76) |
| Parámetros urbanísticos | Edificabilidad, ocupación, altura, retranqueos, usos | Lista de 2 columnas |
| Artículos de referencia | Artículos PGOU citados, con texto extractado | `Quote` style |
| Anotaciones del analista | Campo editable pre-relleno con notas del agente | `Normal` editable |
| Próximos pasos | Lista numerada con acciones recomendadas | `List Number` |

### Estilos Word personalizados (python-docx)

```python
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

GOLD = RGBColor(0xC9, 0xA8, 0x4C)
DARK = RGBColor(0x11, 0x11, 0x11)

def _apply_custom_styles(doc: Document) -> None:
    # Estilo "Verdict" — texto grande, centrado, color según veredicto
    style = doc.styles.add_style("Verdict", WD_STYLE_TYPE.PARAGRAPH)
    style.font.size = Pt(22)
    style.font.bold = True
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
```

### Cabecera de tabla

```python
def _fill_table_header(row, labels: list[str]) -> None:
    for i, label in enumerate(labels):
        cell = row.cells[i]
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        cell.paragraphs[0].runs[0].font.bold = True
        _set_cell_bg(cell, "C9A84C")
```

### Template opcional (`docxtpl`)

Si `template_path` existe, se usa `docxtpl.DocxTemplate` con contexto `Jinja2`.  
Template variables: `{{ titulo }}`, `{{ veredicto }}`, `{{ tabla_afecciones }}`, `{{ fecha }}`.

---

## 3. `tools/xlsx_generator.py`

### Interfaz pública

```python
def generate_xlsx(expediente_data: dict[str, Any]) -> bytes:
    """Devuelve bytes de un .xlsx con 3 hojas."""
```

### Hoja 1 — Parámetros Urbanísticos

| Columna | Ancho | Descripción |
|---|---|---|
| A: Parámetro | 28 | Nombre del parámetro (edificabilidad, etc.) |
| B: Valor extraído | 18 | Valor numérico o texto |
| C: Unidad | 12 | m²/m², %, m, plantas… |
| D: Confianza | 14 | Alta / Media / Baja |
| E: Artículo ref. | 22 | Art. 23.1 PGOU… |

**Formato condicional** en columna D (Confianza):
- Alta → relleno `#D4EDDA` (verde claro)
- Media → relleno `#FFF3CD` (amarillo)
- Baja → relleno `#F8D7DA` (rojo claro)

Cabeceras: fondo `#C9A84C`, texto `#111111`, bold, freeze_panes en `A2`.

```python
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.formatting.rule import ColorScaleRule

GOLD_FILL = PatternFill("solid", fgColor="C9A84C")
HEADER_FONT = Font(bold=True, color="111111")
```

### Hoja 2 — Afecciones Sectoriales

Semáforo por tipo de afección:

| Columna | Contenido |
|---|---|
| A | Categoría (inundación, costas, carreteras…) |
| B | Estado: ✓ Libre / ⚠ Condicionado / ✗ Afectado |
| C | Valor obtenido |
| D | Fuente (SNCZI, SIGCOSTAS, etc.) |
| E | Observaciones |

**Iconos de estado en celda**: se usa `openpyxl` `DataBar` o coloreado de fondo:
- Libre → `#22C55E`
- Condicionado → `#F59E0B`
- Afectado → `#EF4444`

### Hoja 3 — Artículos PGOU

| Columna | Contenido |
|---|---|
| A | Nº artículo |
| B | Título del artículo |
| C | Extracto (max 500 chars) |
| D | Puntuación relevancia (0-10) |
| E | URL fuente (si disponible) |

Celdas de extracto con `wrap_text=True`, altura de fila auto.

---

## 4. `tools/pdf_generator_v2.py`

### Filosofía: JSON Draft Intermedio

En lugar de generar PDF directamente, el agente produce un objeto `DraftReport` editable que el usuario puede modificar en la UI antes de rasterizar.

```python
@dataclass
class DraftReport:
    title: str
    sections: list[DraftSection]
    metadata: dict[str, Any]

@dataclass
class DraftSection:
    id: str
    heading: str
    body: str          # Markdown editado por el usuario
    visible: bool = True

def draft_to_pdf(draft: DraftReport) -> bytes:
    """Rasteriza el DraftReport usando reportlab o weasyprint (local)."""
```

### Flujo editorial

```
Agente genera DraftReport (JSON)
        ↓
  QTextEdit editable en columna 30%
        ↓
  Usuario edita secciones / oculta bloques
        ↓
  "Actualizar vista previa" → renderiza PDF en panel flotante
        ↓
  "Exportar como…" → guarda bytes a disco
```

### Backend de rasterización (local, sin cloud)

Opción A — **reportlab** (ya en entorno): ligero, usa FPDF-like API  
Opción B — **weasyprint** (add dep): HTML/CSS → PDF, mejor para layouts complejos

Recomendación: reportlab para V2, migrar a weasyprint si se necesitan estilos CSS.

---

## 5. Integración con el Agente

### Nuevas tools disponibles para el LLM

```python
# En tools/export_tools.py — registro en AgentRuntime

{
    "name": "generate_docx",
    "description": "Genera un informe Word (.docx) del expediente activo.",
    "parameters": {
        "expediente_id": {"type": "integer"},
        "include_sections": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Secciones a incluir: portada, afecciones, parametros, articulos, pasos"
        }
    }
}

{
    "name": "generate_xlsx",
    "description": "Genera una hoja Excel (.xlsx) con parámetros, afecciones y artículos.",
    "parameters": {
        "expediente_id": {"type": "integer"}
    }
}

{
    "name": "update_pdf_draft",
    "description": "Actualiza el borrador PDF editable. Devuelve el DraftReport actualizado.",
    "parameters": {
        "expediente_id": {"type": "integer"},
        "section_id": {"type": "string"},
        "new_body": {"type": "string"}
    }
}
```

### Registro en `core/runtime.py`

```python
from adv_archon.tools.export_tools import ExportTools

self.export_tools = ExportTools(self.config.paths.data_dir)
# ExportTools registra generate_docx, generate_xlsx, update_pdf_draft
```

---

## 6. UI — Editor de Borrador (columna 30%)

```
Estado A — Generando informe
┌─────────────────────────┐
│  ✏ BORRADOR EN VIVO     │
│  ─────────────────────  │
│  [QTextEdit Markdown]   │  ← editable, monospace 13px
│  # Resumen ejecutivo    │
│  Veredicto: VIABLE      │
│  ...                    │
│                         │
│  [Actualizar vista ▸]   │  → renderiza PDF en ventana flotante
│  [Exportar como… ▾]     │  → submenú: PDF / DOCX / XLSX
└─────────────────────────┘
```

**Comportamiento del botón "Exportar como…"**:
- `PDF` → llama `draft_to_pdf(draft)`, `QFileDialog.getSaveFileName`
- `DOCX` → llama `generate_docx(data)`, `QFileDialog.getSaveFileName`
- `XLSX` → llama `generate_xlsx(data)`, `QFileDialog.getSaveFileName`

**Señales Qt**:
- `draft_updated = Signal(str)` — emitida cuando el agente actualiza el borrador
- `export_ready = Signal(bytes, str)` — emitida cuando los bytes están listos (bytes, extension)

---

## 7. Tests requeridos

| Archivo | Tests |
|---|---|
| `tests/test_docx_generator.py` | `generate_docx` produce bytes válidos, secciones presentes, tabla con N filas, sin template, con template |
| `tests/test_xlsx_generator.py` | `generate_xlsx` produce bytes, 3 hojas presentes, cabeceras doradas, formato condicional aplicado |
| `tests/test_pdf_draft.py` | `DraftReport` serializable, `draft_to_pdf` produce bytes, sección oculta no aparece en output |

Todos los tests usan fixtures locales (`tmp_path`), sin red.

---

## 8. Fases de implementación

| Fase | Entregable | Días estimados |
|---|---|---|
| F1 | `tools/docx_generator.py` + tests | 1 |
| F2 | `tools/xlsx_generator.py` + tests | 1 |
| F3 | `tools/pdf_generator_v2.py` (DraftReport) | 1 |
| F4 | `tools/export_tools.py` (agent integration) | 0.5 |
| F5 | UI: botones Exportar + editor borrador | 1.5 |
| **Total** | | **5 días** |
