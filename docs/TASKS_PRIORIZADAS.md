# TASKS PRIORIZADAS — ADV ARCHON V2

> Fecha de revisión: 2026-06-08  
> Rama activa: `claude/deepseek-v4-exploration-P51AF`  
> Restricciones: todo local, 0 deps cloud, ruff 0 errores, ≥264 tests

---

## P0 — Crítico (bloquea funcionalidad core)

### T-01 · Export DOCX/XLSX/PDF (borrador editable)
Implementar `tools/docx_generator.py`, `tools/xlsx_generator.py` y `tools/pdf_generator_v2.py` con el objeto `DraftReport` editable antes de exportar.  
**Estimación**: 5 días  
**Deps**: ninguna (primera tarea)  
**Spec**: `docs/DOCX_XLSX_INTEGRATION_PLAN.md`

---

### T-02 · Wiring de ExportTools en el agente
Registrar `generate_docx`, `generate_xlsx`, `update_pdf_draft` como tools del LLM en `core/runtime.py` y exponer los botones "Exportar como…" en la columna 30% de la UI.  
**Estimación**: 1 día  
**Deps**: T-01

---

### T-03 · UI V2 — Sidebar con grupos colapsables
Implementar el sidebar de 220px con 5 grupos colapsables (INICIO, ANÁLISIS, AGENTE, DATOS, CONFIGURACIÓN), animación ▸/▾, borde dorado en ítem activo, y footer con estado de Ollama.  
**Estimación**: 2 días  
**Deps**: ninguna  
**Spec**: `docs/INTERFAZ_V2_DESIGN.md §2`

---

### T-04 · UI V2 — Composer multimodal
Reemplazar el campo de texto actual por el Composer de 140px: `QPlainTextEdit` + botón 🎤 con `QPropertyAnimation` + botón ✨ con spinner + franja de adjuntos + drag-and-drop con parpadeo de borde dorado.  
**Estimación**: 2 días  
**Deps**: ninguna  
**Spec**: `docs/INTERFAZ_V2_DESIGN.md §6`

---

### T-05 · PGOUReranker en hot path
Mover el `PGOUReranker` de módulo auxiliar a llamada activa en `_run_analysis()`: re-ordenar los chunks antes de pasar al LLM, respetando el feature flag `enable_reranker` en `config.toml`.  
**Estimación**: 1 día  
**Deps**: ninguna (módulo ya existe en `core/pgou_reranker.py`)

---

## P1 — Alta prioridad (mejora directa de calidad)

### T-06 · UI V2 — Panel lateral derecho con historial en tiempo real
Implementar el panel de 280px con secciones colapsables: Herramientas activas, Fuentes consultadas, Historial de acciones (fade-in por ítem), Adjuntos recientes (miniaturas 40×40px).  
**Estimación**: 2 días  
**Deps**: T-03 (layout establecido)  
**Spec**: `docs/INTERFAZ_V2_DESIGN.md §5`

---

### T-07 · Confirmación de parámetros urbanísticos extraídos
Mostrar en la columna 30% el Estado B "PARÁMETROS" con los valores del `ParamExtractor`, permitir edición inline, y guardar `params_confirmed=True` en `Expediente` tras confirmación del usuario.  
**Estimación**: 1.5 días  
**Deps**: T-03, T-04  
**Spec**: `docs/INTERFAZ_V2_DESIGN.md §4.2 Estado B`

---

### T-08 · Barra de estado superior con progreso animado
Añadir la barra de 32px con `QPropertyAnimation` sobre altura (aparece/desaparece según estado del sistema), barra de progreso dorada, icono pulsante durante carga, ✓ verde cuando listo.  
**Estimación**: 1 día  
**Deps**: T-03  
**Spec**: `docs/INTERFAZ_V2_DESIGN.md §3`

---

### T-09 · Hero compacto 52px + botón "Nuevo expediente"
Reemplazar el header actual por el hero compacto con título serif, separador dorado `·`, subtítulo dinámico y botón "Nuevo expediente" con estilo `#C9A84C`.  
**Estimación**: 0.5 días  
**Deps**: T-03  
**Spec**: `docs/INTERFAZ_V2_DESIGN.md §4.1`

---

### T-10 · Métricas del dashboard y lista de expedientes recientes
Implementar la fila de 4 tarjetas de métricas (expedientes, informes, riesgos, modelo) y la lista de expedientes recientes con estado de color y hover animado.  
**Estimación**: 1 día  
**Deps**: T-03, T-09  
**Spec**: `docs/INTERFAZ_V2_DESIGN.md §4.2 columna izquierda`

---

### T-11 · Modo oscuro / claro con tokens CSS y QPropertyAnimation
Implementar el toggle de modo desde Configuración, `QPropertyAnimation` sobre `palette()` 300ms, y los 8 tokens de color especificados en la tabla de diseño.  
**Estimación**: 1.5 días  
**Deps**: T-03  
**Spec**: `docs/INTERFAZ_V2_DESIGN.md §7`

---

### T-12 · Memoria episódica: búsqueda por similitud en el chat
Cuando el usuario envíe un mensaje de análisis, buscar en `EpisodicMemory` los 3 casos más similares e inyectarlos como contexto previo en el prompt del agente.  
**Estimación**: 1 día  
**Deps**: módulo `core/episodic_memory.py` ya operativo

---

## P2 — Media prioridad (calidad de vida / robustez)

### T-13 · PGOUReranker batch — evitar llamadas LLM por chunk
Implementar un modo batch en `PGOUReranker._score_batch()` que pase todos los chunks en un único prompt y parsee las puntuaciones en bloque, reduciendo llamadas de N a 1.  
**Estimación**: 1 día  
**Deps**: T-05

---

### T-14 · Tests de integración UI (pytest-qt headless)
Añadir `tests/test_ui_sidebar.py` y `tests/test_ui_composer.py` con `pytest-qt` y `QTest` en modo headless para verificar que los componentes V2 se renderizan sin errores.  
**Estimación**: 1.5 días  
**Deps**: T-03, T-04

---

### T-15 · Caché de embeddings para PGOU chunks
Almacenar los embeddings de chunks PGOU en `pgou.db` al indexar, evitando regenerarlos en cada `search_similar`. Añadir columna `embedding BLOB` a la tabla de chunks.  
**Estimación**: 1 día  
**Deps**: ninguna

---

### T-16 · Exportación a plantilla DOCX personalizada
Permitir al usuario seleccionar una plantilla `.docx` corporativa desde Configuración. Si existe, `generate_docx` usa `docxtpl.DocxTemplate`; si no, usa la plantilla por defecto.  
**Estimación**: 0.5 días  
**Deps**: T-01, T-02

---

### T-17 · CLI: comandos `export` y `draft`
Añadir a la CLI (`cli/main.py`) los subcomandos:  
- `adv-archon export --id <n> --format docx|xlsx|pdf --output <path>`  
- `adv-archon draft --id <n>` (abre el borrador en el editor del sistema)  
**Estimación**: 1 día  
**Deps**: T-01

---

### T-18 · Purga automática de caché API al arrancar
Llamar `PersistentAPICache.purge_expired()` al inicio del runtime y loguear el número de entradas purgadas. Añadir opción `cache_max_entries` en `config.toml` para limitar el tamaño.  
**Estimación**: 0.5 días  
**Deps**: módulo `integrations/resilient.py` ya operativo

---

## Resumen de estimaciones

| Prioridad | Tareas | Días totales |
|---|---|---|
| P0 | T-01 a T-05 | 11 días |
| P1 | T-06 a T-12 | 8 días |
| P2 | T-13 a T-18 | 5.5 días |
| **Total** | **18 tareas** | **~24.5 días** |

---

## Orden de ejecución sugerido (2 semanas activas)

```
Semana 1:
  Lun: T-01 (DOCX/XLSX generadores)
  Mar: T-01 cont. + T-02 (wiring agente)
  Mié: T-03 (Sidebar V2)
  Jue: T-04 (Composer multimodal)
  Vie: T-05 (PGOUReranker hot path) + T-18 (purga caché)

Semana 2:
  Lun: T-08 (barra estado) + T-09 (hero)
  Mar: T-10 (métricas + lista expedientes)
  Mié: T-06 (panel derecho)
  Jue: T-07 (confirmación parámetros) + T-12 (episodic search)
  Vie: T-11 (modo oscuro) + T-16 (plantilla DOCX custom)

Backlog posterior: T-13, T-14, T-15, T-17
```
