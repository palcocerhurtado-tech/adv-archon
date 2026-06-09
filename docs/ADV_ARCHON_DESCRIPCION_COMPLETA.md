# Descripción ultra detallada de la interfaz y arquitectura de ADV ARCHON — Beta 0.1

ADV ARCHON es una aplicación de escritorio de inteligencia artificial local, diseñada para arquitectura, urbanismo, expedientes técnicos, análisis normativo, revisión de PGOU, generación de informes, investigación documental, entrenamiento local y asistencia contextual. Visualmente no se comporta como una landing page ni como una web comercial, sino como una herramienta profesional instalada en macOS, con estética de software interno premium para despachos técnicos.

La interfaz tiene una identidad muy marcada: sobria, arquitectónica, institucional, de baja saturación cromática y con una sensación de producto beta avanzado. La aplicación mezcla un lenguaje visual clásico, casi editorial, con componentes funcionales de dashboard técnico. El resultado es una herramienta que parece pensada para arquitectos, urbanistas, consultores, despachos profesionales o equipos técnicos que necesitan analizar documentación y convertirla en entregables.

La aplicación se presenta dentro de una ventana macOS. La barra superior de la ventana es de color gris oscuro, con los tres botones clásicos de macOS en la esquina superior izquierda: rojo, amarillo y verde. En el centro de la barra aparece el título de la aplicación:

**ADV ARCHON — Beta 0.1**

La versión exacta se define en el código como `__version__ = "0.1.0"` con la etiqueta `__beta_label__ = "Beta 0.1"`. En ventanas secundarias o módulos separados, el título de la barra refleja el módulo abierto:

**Expedientes — ADV ARCHON**  
**Studio Demo — ADV ARCHON**  
**Pack Studio — ADV ARCHON**  
**Cliente / Licencia — ADV ARCHON Studio**

La paleta de color es muy consistente:

- Negro profundo (`#111111`) para la estructura principal, navegación, barras de estado y sidebar.
- Blanco roto o crema muy claro (`#F7F4EF`) para el área de trabajo.
- Beige suave para tarjetas secundarias.
- Gris claro para bordes, separadores, textos auxiliares y fondos desactivados.
- Amarillo dorado (`#C9A84C`) como color de acento principal, usado para botones importantes, bordes activos, indicadores, números destacados y estados principales.
- Verde (`#22C55E`) para estados positivos.
- Naranja (`#F59E0B`) para estados condicionados o advertencias.
- Rojo (`#EF4444`) para riesgos críticos.

El diseño evita colores chillones, degradados agresivos o elementos futuristas exagerados. Todo se siente deliberadamente controlado, sobrio y profesional.

---

## 1. Estructura global de la aplicación

La interfaz principal está organizada en cinco grandes zonas fijas:

1. **Sidebar izquierda negra**
2. **Barra superior horizontal de estado**
3. **Área central de trabajo**
4. **Panel derecho de contexto**
5. **Composer inferior de chat y acciones**

Estas zonas se mantienen de forma muy consistente en casi todas las pantallas. La sensación es la de una aplicación modular: existe una carcasa principal fija (`DesktopWindow`, clase `QMainWindow`) y, dentro de ella, se abren diferentes módulos como Inicio, Expedientes, Studio Demo, Chat contextual, Research, Cliente, Pack, Training Lab, Revisión Pro, PGOU, Geo, Briefing y Guía beta.

La ventana principal tiene proporción panorámica, ocupa casi todo el ancho de pantalla y deja ver alrededor el escritorio de macOS. La aplicación tiene sombras suaves sobre el fondo del sistema, lo que refuerza la sensación de software de escritorio real.

---

## 2. Sidebar izquierda

La sidebar izquierda es una columna vertical fija de color negro casi puro. Ocupa toda la altura de la ventana principal y tiene una anchura aproximada de 220 a 250 píxeles. Es la columna de navegación principal.

En la parte superior aparece el bloque de marca. Hay un pequeño logotipo arquitectónico en tonos negros, blancos y amarillos, parecido a una estructura con columnas, una casa técnica o una torre con una "A" en el centro. Junto al logo o debajo aparece el nombre:

**ADV ARCHON**

Debajo aparece un subtítulo en mayúsculas espaciadas:

**ARQUITECTURA · IA · BETA 0.1**

La marca se siente seria, técnica y ligeramente institucional. El uso de mayúsculas espaciadas da una sensación de producto profesional, casi de herramienta de estudio o laboratorio.

Debajo del bloque de marca aparece el menú vertical. Los elementos están alineados a la izquierda, con texto blanco o gris claro, sobre fondo negro. Cada opción tiene altura cómoda y bastante separación vertical. Las trece opciones del menú, que corresponden exactamente a los botones definidos en el código (`_nav_*_btn`), son:

**Inicio** (`_nav_home_btn`)  
**Expedientes** (`_nav_exp_btn`)  
**Revisión Pro** (`_nav_review_btn`)  
**Studio Demo** (`_nav_demo_btn`)  
**Chat contextual** (`_nav_chat_btn`)  
**Research** (`_nav_research_btn`)  
**PGOU** (`_nav_pgou_btn`)  
**Geo** (`_nav_geo_btn`)  
**Briefing** (`_nav_daily_btn`)  
**Cliente** (`_nav_client_btn`)  
**Pack** (`_nav_pack_btn`)  
**Training Lab** (`_nav_training_btn`)  
**Guía beta** (`_nav_beta_btn`)

Los elementos activos se representan con un borde amarillo dorado fino alrededor del botón o con un relleno dorado intenso, según el estado. Cuando están abiertos módulos en ventanas flotantes (Cliente, Pack, Studio Demo), el botón correspondiente en la sidebar puede aparecer resaltado con borde dorado o fondo gris oscuro.

La sidebar también comunica el estado operativo del sistema. En la parte inferior hay una sección de configuración rápida con dos selectores:

**MODO** — `QComboBox` (`_mode_combo`) con valores `local` y `cloud`  
**PERFIL** — `QComboBox` (`_profile_combo`) con perfiles como `general` y `coding` (y los que defina el usuario en `config.toml`)

Los campos tienen fondo gris muy oscuro, borde fino, esquinas redondeadas y texto blanco o gris claro.

Más abajo aparecen tres acciones secundarias:

**Ajustes** (`_settings_button`)  
**QA permisos** (`_qa_button`)  
**Estado sistema** (`_system_button`)

Estas opciones dan acceso a configuración del motor local, diagnóstico de permisos y estado del sistema.

En el borde inferior de la aplicación, conectado visualmente con la sidebar, hay una barra de estado negra con cuatro etiquetas:

**Beta 0.1** — etiqueta dorada (`_beta_badge_lbl`)  
**Ollama ●** — punto verde si activo, gris si inactivo (`_ollama_badge_lbl`)  
**Modelo: llama3.1:8b** — modelo activo (`_model_badge_lbl`)  
**Último expediente: Sin expediente** — expediente activo (`_last_exp_badge_lbl`)

---

## 3. Barra superior horizontal de estado

Justo encima del área central hay una barra horizontal negra. Esta barra funciona como línea de estado, consola mínima o indicador de actividad. Contiene:

- **Texto de estado** (`_status_label`): gris claro, pequeño, alineado a la izquierda. Mensajes como:
  - `Abriendo bases de datos de memoria y conocimiento...`
  - `Inicio Studio listo.`
  - `Training Lab listo.`
  - `Research Workbench listo.`
- **Barra de progreso** (`_progress_bar`, `QProgressBar`): oculta cuando el sistema está inactivo; aparece con relleno dorado durante operaciones largas.
- **Botón Cancelar** (`_cancel_button`): aparece durante operaciones activas para interrumpir la ejecución del agente.

Esta barra convierte la aplicación en una herramienta viva: no es una pantalla estática, sino un entorno que informa de carga, preparación, ejecución y disponibilidad del sistema.

---

## 4. Área central de trabajo

El área central ocupa la mayor parte del espacio de la aplicación. Tiene fondo blanco roto, crema muy claro o gris cálido (`#F7F4EF`). No es blanco puro.

La composición se basa en tarjetas con bordes finos (`1px solid #E8E4DD`), esquinas redondeadas y fondos ligeramente beige. Las tarjetas están distribuidas en retículas limpias, con márgenes amplios y separación regular.

La tipografía tiene dos niveles diferenciados:

- Los **títulos principales** usan una serif gruesa, elegante y editorial (Georgia o similar), con aspecto institucional.
- Los **textos funcionales** (descripciones, etiquetas, placeholders, botones) usan una sans-serif limpia (Inter o sistema). Esta combinación de serif para jerarquía y sans-serif para función crea un contraste muy reconocible.

### Barra de expediente activo

En la parte superior del área de chat, cuando hay un expediente seleccionado, aparece una barra fija (`_exp_context_bar`) de fondo beige claro con el título y municipio del expediente activo, y un botón × para desvincularlo. Esta barra conecta visualmente el chat con el caso urbanístico en curso, recordando al usuario que las respuestas del agente están contextualizadas.

---

## 5. Panel derecho de contexto

A la derecha de la interfaz principal hay un panel vertical fijo, separado del área central por una línea vertical gris clara (`1px solid #E8E4DD`). Tiene fondo blanco roto y ocupa aproximadamente una quinta parte de la anchura total de la app.

Este panel es persistente en casi todas las pantallas. Su función es mostrar el contexto operativo de la IA, herramientas activas, fuentes consultadas, historial y adjuntos recientes. El panel muestra en tiempo real qué está usando el agente: qué herramientas se han activado, qué fuentes se han consultado y qué documentos recientes se han adjuntado.

En la parte superior aparece el título:

**CONTEXTO**

Debajo, el campo `_context_view` (`QPlainTextEdit`, solo lectura) muestra: intención detectada, perfil activo, modo (local/cloud), memoria episódica recuperada y resultados de la base de conocimiento.

Después aparece la sección:

**HERRAMIENTAS**

El `_tools_container` muestra una fila de chips o badges con el nombre de cada tool activada durante el turno actual (por ejemplo: `resolve_coordinates`, `plan_compliance_check`, `boe_search`).

Después:

**FUENTES**

El campo `_sources_view` (`QPlainTextEdit`, solo lectura) muestra: fuentes consultadas por el agente en el turno (memoria local, base de conocimiento, fuentes web, APIs oficiales).

Después:

**HISTORIAL**

El `_history_list` (`QListWidget`) lista las interacciones recientes de la sesión con timestamp y resumen.

En la parte inferior:

**ADJUNTOS RECIENTES**

El `_recent_attachments_list` (`QListWidget`) muestra los últimos archivos adjuntados.

Finalmente, cuando se completa un análisis de cumplimiento normativo, aparece una tarjeta oculta en reposo:

**COMPLIANCE** (`_compliance_card`, `QFrame`)

Esta tarjeta contiene el resumen del análisis (`_compliance_summary_lbl`), estadísticas por estado (`_compliance_stats_lbl`) y un botón dorado para exportar el informe a PDF (`_export_button`).

---

## 6. Composer inferior de chat

En la parte inferior del área central aparece una zona fija de consulta tipo chat. Es una franja grande de fondo blanco, con borde superior suave.

A la izquierda aparece el campo de texto (`_input`, `QTextEdit`) con el placeholder:

**Escribe tu consulta... (Ctrl+Enter para enviar)**

Debajo del campo de texto aparece la zona de arrastre (`_DropZoneFrame`): cuando el usuario arrastra un archivo sobre la ventana, el área parpadea con borde dorado indicando que puede soltarlo.

A la derecha hay un bloque de acciones:

**Enviar** (`_send_button`) — botón amarillo dorado principal; mientras el agente procesa, muestra un spinner circular y queda desactivado.  
**Hablar con ARCHON** (`_voice_button`) — activa el sistema STT con Whisper local.  
**Adjuntar** (`_add_button`) — abre `QFileDialog` para adjuntar archivos.

Cuando hay archivos PDF adjuntos, aparece el botón:

**Analizar plano** (`_analyze_button`) — lanza directamente el flujo de análisis de cumplimiento sin necesidad de escribir nada.

Cuando hay archivos adjuntados, aparece el botón:

**→ KB** (`_import_button`) — importa los archivos a la base de conocimiento local del agente.

Los archivos adjuntados se muestran como chips o pills coloreados (con icono de tipo y botón × para eliminar) justo encima del campo de texto.

**Atajos de teclado activos:**

| Atajo | Acción |
|---|---|
| Ctrl+Enter | Enviar consulta |
| (Arrastrar archivo) | Adjuntar automáticamente |

---

## 7. Stream de respuesta del agente

Las respuestas del agente se renderizan token a token en burbujas de mensaje (`_start_assistant_stream`, `_append_assistant_chunk`, `_flush_assistant_stream`). El área de mensajes (`_messages_scroll`, `QScrollArea`) hace auto-scroll al recibir cada nuevo fragmento. Los mensajes del usuario aparecen alineados a la derecha con fondo beige claro; los del agente, alineados a la izquierda con fondo blanco y borde fino.

---

## 8. Pantalla principal / Inicio Studio

La pantalla de inicio muestra la identidad funcional de la herramienta. En la zona superior del área central aparece una tarjeta hero grande con borde amarillo dorado, esquinas redondeadas y fondo blanco roto.

Dentro de esta tarjeta hero aparece a la izquierda el icono arquitectónico de ADV ARCHON. A la derecha del icono aparece un texto pequeño, en mayúsculas espaciadas:

**ADV ARCHON STUDIO**

Debajo aparece el título principal (serif):

**Expedientes urbanísticos, de la parcela al informe.**

Debajo del título aparece la explicación:

**Crea un expediente, ADV ARCHON consulta fuentes oficiales, detecta riesgos y genera un informe preliminar profesional.**

A la derecha de la tarjeta hero hay un botón amarillo dorado:

**Nuevo expediente**

Debajo del hero hay un sistema de tarjetas de módulo. Las más habituales:

| Módulo | Descripción | Botón |
|---|---|---|
| **Research** | Investiga fuentes, extrae fórmulas y prepara entregables. | Abrir (dorado) |
| **Documentos** | 8 entregables generados. | Abrir |
| **Estado sistema** | Motor local, rendimiento, permisos y modelos. | Abrir |
| **Acciones rápidas** | Chat, voz, adjuntos y primer borrador desde un único flujo. | Abrir |
| **Expedientes** | Lista, detalle, plano, análisis y exportación PDF. | Abrir |
| **Studio Demo** | Tres casos guiados con semáforo, riesgos, fuentes e informe. | Abrir (dorado) |
| **Cliente / Licencia** | Despacho beta ADV ARCHON · Studio Edition Beta. | Abrir |
| **Training Lab** | Dataset real, sintético y preparación de fine-tuning local. | Abrir |

La primera tarjeta activa suele estar más destacada con botón amarillo.

Debajo de las tarjetas hay una fila de métricas en tarjetas blancas con borde fino. Los valores principales aparecen en amarillo dorado:

| Valor | Etiqueta |
|---|---|
| **3** | Expedientes |
| **3** | Informes |
| **8** | Documentos |
| **6** | Riesgos |
| **Listo / Cloud** | Ollama |
| **llama3.1:8b** | Modelo |

---

## 9. Sección de últimos expedientes

En la parte inferior de la pantalla principal aparece una tarjeta grande titulada:

**Últimos expedientes**

Cada expediente aparece como una fila con fondo blanco, borde gris claro, esquinas redondeadas y un botón "Abrir" alineado a la derecha. Los expedientes demo son:

**DEMO - Vivienda unifamiliar con PGOU pendiente** · Valencia  
**DEMO - Parcela con riesgo de inundabilidad** · Zaragoza  
**DEMO - Cambio de uso local a vivienda** · Madrid

---

## 10. Sección de documentos generados y última actividad

Una tarjeta titulada **Documentos generados** lista los entregables ya producidos (informes PDF, planos, memorias). Otra tarjeta **Última actividad** muestra un registro de las últimas acciones del sistema: expediente activo, documentos actualizados, etc.

---

## 11. Flujo guiado

Una tarjeta **Flujo guiado** presenta los cinco pasos del proceso principal:

1. Tipo de actuación
2. Dirección, Catastro o coordenadas
3. Plano del expediente
4. Análisis PGOU y afecciones
5. Informe PDF profesional

---

## 12. Ventana de Expedientes

El módulo de Expedientes (`_open_expedientes`) se abre como una ventana secundaria grande titulada **Expedientes — ADV ARCHON**. Tiene estructura de dos columnas separadas por una línea vertical.

**Columna izquierda** — Lista de expedientes. El expediente seleccionado aparece resaltado en amarillo dorado.

**Columna derecha (detalle)** — Muestra todos los campos del expediente activo:

- Título, municipio, estado, tipo de actuación
- Línea de estado con punto de color y fecha
- Sección **Calidad del expediente** con tabla de dos columnas:
  - Estado (Completo / Incompleto)
  - Riesgo jurídico (en rojo si es alto)
  - Fuentes oficiales (consultadas / pendientes)
  - Base municipal (estado de PGOU)
  - Campos faltantes
  - Estado de revisión

- Botón **Ejecutar Autopilot** (amarillo dorado) — lanza el agente en modo autónomo sobre el expediente.
- Campo **Plano** con ruta del PDF y botón "Adjuntar plano..."
- Fila de botones de análisis:
  - **Analizar con PGOU** (amarillo dorado)
  - **Exportar informe PDF** (blanco/neutro)
  - **Abrir informe** (verde, si ya existe)
  - **Hablar con ARCHON** (blanco/neutro)

- Fila de revisión arquitectónica:
  - **Revisión arquitecto**
  - **Confirmar**
  - **Corregir**
  - **Excluir informe**
  - **Añadir nota**

- Tarjeta grande **Documento de entrega** con:
  - Etiqueta "Borrador listo" en la esquina
  - Campo editable de contenido del informe
  - Pestaña/sección "Resumen ejecutivo" con el veredicto en JSON
  - Sección "Adjuntos / evidencias"
  - Botones de exportación: **Guardar borrador** · **PDF** (dorado) · **DOCX** · **XLSX**

Los campos del modelo `Expediente` que alimentan esta vista incluyen: `id`, `title`, `address`, `municipality`, `province`, `latitude`, `longitude`, `cadastral_ref`, `status`, `case_type`, `plan_path`, `report_path`, `site_context` (JSON con checks legales), `analysis_result` (JSON con veredicto), `created_at`, `updated_at`, `notes`, `review_state`, `quality_score`, `quality_result`, `agent_history`, `agent_step_reviews`, `extracted_params` (parámetros urbanísticos extraídos), `params_confirmed` y `orchestrator_state`.

---

## 13. Módulo Revisión Pro

El módulo **Revisión Pro** (`_show_professional_review`) es una pantalla de revisión arquitectónica que permite al profesional auditar cada paso del agente y tomar decisiones sobre las anotaciones del análisis. Se accede desde la sidebar o directamente desde el detalle de expediente.

La pantalla muestra un dashboard de pasos de revisión con cuatro filtros activables mediante botones de cabecera:

| Filtro | Significado |
|---|---|
| **Pendientes** | Pasos aún sin decisión del arquitecto |
| **Validados** | Pasos aprobados por el profesional |
| **Advertencias** | Pasos con advertencia aceptada |
| **Excluidos** | Pasos excluidos del informe final |

Cada fila de paso muestra: expediente de origen, tipo de actuación, artículo de referencia, descripción del análisis del agente, estado de cumplimiento y una fila de acciones inline:

- **Validar** — acepta el paso como correcto
- **Aceptar advertencia** — mantiene el paso pero marca la advertencia
- **Repetir** — vuelve a ejecutar el análisis de ese paso
- **Excluir del informe** — elimina el paso del entregable final

Esta pantalla transforma ADV ARCHON de una herramienta de análisis automático en un sistema de revisión humano-en-el-bucle, donde el arquitecto actúa como árbitro final del veredicto.

---

## 14. Ventana de Studio Demo

El módulo Studio Demo se abre como una ventana secundaria centrada titulada **Studio Demo — ADV ARCHON**. Contiene una tarjeta hero con borde amarillo dorado.

El título principal es:

**Demo comercial guiada de 10 minutos**

La descripción dice:

**Tres expedientes preparados para enseñar valor: decisión, horas ahorradas, riesgos, fuentes oficiales e informe listo para abrir.**

Debajo aparece una línea destacada en amarillo dorado:

**Preparado para: Despacho beta ADV ARCHON · Studio Edition Beta · Madrid, Zaragoza, Barcelona, Valencia, Sevilla**

A la derecha de la tarjeta hero hay un botón amarillo dorado:

**Iniciar demo comercial**

Esta ventana está pensada para presentaciones comerciales de ~10 minutos. La demo no bloquea el chat principal.

---

## 15. Pantalla de Chat contextual

La pantalla de Chat contextual es minimalista. El área central aparece casi vacía hasta que hay un expediente activo, mostrando el mensaje:

**Chat contextual listo. Abre un expediente para que ARCHON use su parcela, municipio, PGOU y afecciones en la respuesta.**

Esto indica que el chat no funciona como chatbot genérico, sino como asistente contextual que necesita un expediente activo para responder con datos del caso. El composer inferior permanece siempre visible.

---

## 16. Pantalla Research Workbench

El módulo Research aparece dentro del shell principal. Su hero lleva el texto:

**AGENTIC STUDIO** · **Research Workbench**

**Investiga, extrae evidencias, detecta fórmulas y exporta entregables.**

La pantalla se divide en tres columnas:

**Brief** — Campo de texto para instrucciones de investigación. Placeholder: *"Ej.: resuelve este trabajo, busca fuentes y prepara entrega..."*. Adjuntos, botón **Ejecutar investigación** (dorado), exportación directa a **DOCX**, **PDF**, **Excel auditoría**.

**Resultado** — Muestra la investigación generada token a token. Mensaje en reposo: *"Research Workbench listo. Adjunta un enunciado/PDF o escribe el brief."*

**Borrador de entrega** — Campo editable con el borrador del entregable. Estado inicial: *"Pendiente de investigación"*. Secciones: Síntesis, Adjuntos / evidencias. Botones de exportación: **Guardar borrador** · **PDF** (dorado) · **DOCX** · **XLSX**.

Una tarjeta adicional **Document Intelligence** muestra métricas de análisis documental:

**Tablas 0 · Fórmulas 0 · Magnitudes 0**

y el mensaje: *"Analiza un borrador o ejecuta Research para ver señales."*

Internamente, Research utiliza la skill `research` registrada en el agente, que encadena `web_search`, `web_fetch`, síntesis LLM y generación de borrador editable.

---

## 17. Pantalla Training Lab

El módulo Training Lab presenta su hero con:

**TRAINING LAB LOCAL**

**Dataset, feedback y fine-tuning sin tocar scripts.**

**Revisa ejemplos reales aprobados por el juez local, exporta dataset y genera sintéticos con Ollama para preparar experimentos LoRA offline.**

Fila de métricas:

| Valor | Etiqueta |
|---|---|
| 0 | Reales |
| 0 | Aprobados |
| 0 | Sintéticos |
| 20 | Plantillas |
| Pendiente de ejemplos | Estado |

Dos tarjetas principales:

**Preparación del dataset** — Lista de estado: ejemplos reales guardados, aprobados por juez local, score medio del juez, plantillas sintéticas, dataset JSONL path, estado general.

**Acciones** — Botón **Exportar dataset real** (dorado), botones **Generar 20 sintéticos**, **Actualizar estado** y nota: *"Fine-tuning sigue siendo offline y opcional. No se activa dentro del flujo normal de expedientes."*

El juez local es un `ComplianceJudge` integrado en el runtime que evalúa la calidad de cada análisis con una puntuación de 0 a 100 y flags como `"incomplete"`, `"high_risk"`, `"low_confidence"`.

---

## 18. Modal QA de voz, Ollama y visión

Un modal bloqueante titulado **QA de voz, Ollama y visión** comprueba cinco sistemas:

| Indicador | Qué comprueba |
|---|---|
| 🟢 Micrófono | Entrada detectada (Micrófono del MacBook Pro) |
| 🟢 Ollama | Servidor activo en `http://127.0.0.1:11434` |
| 🟢 Modelo local | Instalado (por defecto llama3.1:8b) |
| 🟡 Visión local (llava:latest) | Si no está instalado, muestra modelos disponibles y comando `ollama pull llava:latest` |
| 🟢 Grabación de pantalla | Captura de pantalla permitida |

Botones: **Volver a comprobar** (dorado) y **Cerrar**.

---

## 19. Modal Modelo local Ollama

Un modal titulado **Modelo local Ollama** permite seleccionar el modelo de inferencia local. Muestra el modelo activo (ej. `llama3.1:8b · 4.6 GB`), el número de modelos disponibles y un botón **Actualizar lista**. Botones de acción: **Cancelar** y **Guardar**.

El sistema de enrutamiento de tareas (`task_routing_enabled = true` en config) selecciona automáticamente el modelo más adecuado según el tipo de tarea:

| Perfil de tarea | Modelo por defecto |
|---|---|
| Respuestas rápidas | `fast_local_model` (llama3.2:3b) |
| Planificación | `planner_local_model` (llama3.2:3b) |
| Documentos largos | `document_local_model` (llama3.1:8b) |
| Código | `coding_local_model` (llama3.1:8b) |
| Razonamiento | `reasoning_local_model` (llama3.1:8b) |

En modo cloud, cada perfil tiene su equivalente: `fast_cloud_model`, `planner_cloud_model`, etc.

---

## 20. Ventana Pack Studio

El módulo Pack se abre como ventana secundaria titulada **Pack Studio — ADV ARCHON**.

Hero: **ADV ARCHON STUDIO** · **Paquete profesional para despacho**

Tres tarjetas horizontales:

- **Instalación local** — App configurada en el equipo del despacho, motor local, privacidad y flujo de expedientes.
- **Municipios configurados** — Paquete inicial de municipios con estado validado, preliminar o pendiente.
- **Expedientes demo** — Casos de prueba o ejemplos guiados.

Tarjeta **Alcance del paquete** con lista de entregables:
- Instalación local en el despacho
- Municipios incluidos y etiquetados por estado de validación
- Expedientes demo configurados para el flujo completo
- Plantilla PDF personalizada con nombre y logo del cliente
- Soporte beta privado durante la implantación
- Actualizaciones de producto durante el periodo contratado

---

## 21. Ventana Cliente / Licencia

Ventana secundaria titulada **Cliente / Licencia — ADV ARCHON Studio**. Formulario con los campos:

- **NOMBRE DEL DESPACHO** — input editable (ej. "Despacho beta ADV ARCHON")
- **LOGO DEL DESPACHO** — campo + botón "Elegir logo..." + nota "Sin logo de cliente"
- **MUNICIPIOS INCLUIDOS** — lista: Madrid, Zaragoza, Barcelona, Valencia, Sevilla
- **ESTADO DE LICENCIA** — valor "Beta privada"
- **ETIQUETA VISIBLE** — valor "Studio Edition Beta"
- Ruta del archivo local: `/Users/.../studio_client.json`

Botones: **Cerrar** · **Guardar**. Esta configuración determina la personalización de marca que aparece en todos los informes PDF generados.

---

## 22. Ventana de prueba recomendada para despacho

Pequeña ventana flotante con guía de onboarding:

**Prueba recomendada para un despacho:**

1. Abre Expedientes y crea un expediente nuevo.
2. Introduce dirección, coordenadas o referencia catastral.
3. Adjunta un plano PDF si tienes uno de prueba.
4. Pulsa Analizar y revisa el verdict preliminar.
5. Exporta el informe PDF.

Preguntas de feedback para beta testers: ¿Entiendes el flujo sin explicación? ¿El informe parece presentable ante un cliente interno? ¿Qué dato falta para confiar en la revisión? ¿Qué parte te hizo dudar?

Aviso: *"Esta beta es preliminar y no sustituye comprobación oficial ni criterio profesional."*

---

## 23. Módulo PGOU

La pantalla PGOU (`_show_pgou_status`) muestra la tabla de municipios indexados en la base de datos local (`pgou.db`). Para cada municipio muestra: nombre canónico, número de chunks indexados, fuente y fecha de indexación.

El sistema PGOU tiene tres niveles:

1. **Manual** — El usuario pega el texto del PGOU via `pgou_add` o el agente lo indexa tras buscarlo en la web.
2. **Automático** — `pgou_fetch(municipio)` descarga el PGOU desde el portal oficial del ayuntamiento y lo indexa.
3. **Daemon de refresco** — `ScraperDaemon` ejecuta en background un ciclo periódico (configurable, defecto 24h) que detecta municipios con datos de más de 30 días y los re-indexa automáticamente.

La búsqueda dentro del índice PGOU usa embeddings semánticos (`all-MiniLM-L6-v2` por defecto) con búsqueda híbrida BM25 + coseno.

---

## 24. Módulo Geo

La pantalla Geo muestra información de resolución geográfica. El sistema `GeoTools` integra seis APIs del gobierno español para construir el contexto legal completo de una parcela:

| API | Institución | Datos obtenidos |
|---|---|---|
| **Nominatim** (OSM) | OpenStreetMap | Municipio, provincia, comunidad autónoma |
| **Catastro OVC** | Ministerio de Hacienda | Referencia catastral, dirección, uso del suelo, datos de parcela |
| **SNCZI** | MITERD | Zonas de inundabilidad, periodos de retorno T10/T100/T500 |
| **Natura 2000** | MITERD/CNIG | Zonas de protección natural europeas, hábitats |
| **Dominio Público Marítimo-Terrestre** (Costas) | MITERD | Protección costera, zona de influencia |
| **Carreteras** (INSPIRE/CNIG) | Ministerio de Transportes | Dominio, servidumbre y afección viaria |

Las seis llamadas se ejecutan **en paralelo** mediante `ThreadPoolExecutor(max_workers=5)`, pasando de latencia serie (~suma de tiempos) a latencia paralela (~máximo de tiempos). Cada llamada está protegida por **CircuitBreaker** individual y **PersistentAPICache** con TTL de 7 días.

Los resultados se almacenan en `geo.db` con un radio de cache de 100 m: coordenadas a menos de 100 m de un punto ya resuelto se sirven desde caché sin llamadas a red.

---

## 25. Arquitectura de resiliencia (P0)

ADV ARCHON incorpora una capa de resiliencia completa para las llamadas a APIs externas, implementada en `integrations/resilient.py`:

### PersistentAPICache

Cache SQLite con TTL configurable (defecto 7 días). Las claves se calculan como SHA-256 del endpoint + parámetros serializados. Sobrevive reinicios de la aplicación. Al arrancar, el runtime llama `init_cache(config.paths.api_cache_db)` para activarla globalmente. Soporta purga de entradas expiradas.

### CircuitBreaker

Por cada endpoint externo existe un `CircuitBreaker` independiente con tres estados:
- **CLOSED** — operación normal
- **OPEN** — endpoint bloqueado tras N fallos consecutivos (defecto 3); devuelve valor degradado inmediatamente
- **HALF_OPEN** — tras el timeout de reset (defecto 120s), permite un intento de prueba

### resilient_call()

Función de una línea que encadena automáticamente: Cache → Circuit → Retry (3 intentos con backoff exponencial) → Degradación suave. Devuelve un `ResilientResult` con campos: `data`, `ok`, `degraded`, `source` ("live" / "cache" / "circuit_open" / "error"), `error`.

---

## 26. Sistema de memoria episódica (P0)

El módulo `core/episodic_memory.py` persiste el historial de análisis de cumplimiento. Cada vez que el agente completa un análisis, almacena un episodio con: municipio, tipo de caso, veredicto (VIABLE/CONDICIONADO/REVISAR), parámetros extraídos, resumen y embedding vectorial.

En análisis futuros, el sistema recupera los 3 episodios más similares (por similitud coseno entre embeddings + filtro de municipio) e inyecta esa experiencia acumulada en el prompt del agente, mejorando la consistencia de los veredictos para casos similares.

---

## 27. Extractor de parámetros urbanísticos (P0)

El módulo `core/param_extractor.py` ejecuta una llamada LLM local que analiza los chunks PGOU recuperados y extrae un diccionario estructurado con los parámetros urbanísticos canónicos:

| Parámetro | Ejemplo |
|---|---|
| `uso_principal` | "residencial" |
| `clasificacion` | "suelo urbano consolidado" |
| `calificacion` | "zona residencial plurifamiliar" |
| `edificabilidad_m2m2` | 1.5 |
| `ocupacion_pct` | 60 |
| `altura_maxima_m` | 10.5 |
| `num_plantas` | 3 |
| `retranqueos_m` | 5.0 |
| `usos_permitidos` | ["residencial", "comercial planta baja"] |
| `usos_prohibidos` | ["industrial"] |
| `articulos_referencia` | ["Art. 23.1", "Art. 45.3"] |
| `confianza` | "alta" / "media" / "baja" |

Estos parámetros se inyectan en el prompt de análisis antes de la llamada principal al LLM, y se persisten en el campo `extracted_params` del `Expediente` en la base de datos.

El módulo `core/pgou_reranker.py` complementa al extractor: antes de pasar los chunks al LLM principal, un segundo modelo puntúa cada chunk de 0 a 10 por relevancia respecto al caso en análisis, y reordena el contexto priorizando los artículos más pertinentes.

---

## 28. Herramientas del agente — inventario completo

El agente dispone de más de 60 herramientas registradas en `build_agent_tools()`. A continuación, el listado completo por categoría:

### Ficheros y directorio
`read_file` · `list_dir` · `find_local`

### Web
`web_search` · `web_fetch`

### Shell y Python
`shell_execute` · `python_execute`

### macOS nativo
`open_url` · `run_applescript` · `set_clipboard` · `get_clipboard`

### Gestión de tareas
`list_tasks` · `create_task` · `update_task` · `complete_task` · `delete_task`

### Herramientas personales
`note` · `memo` · `reminder`

### Navegador (Playwright headless)
`browser_navigate` · `browser_click` · `browser_type` · `browser_read` · `browser_screenshot`

### Google Workspace (si configurado)
`gmail_read_inbox` · `gmail_send` · `gmail_search` · `calendar_list_events` · `calendar_create_event` · `drive_list_files` · `drive_read_file` · `drive_write_file`

### Base de conocimiento
`knowledge_search` · `knowledge_add` · `knowledge_remove` · `knowledge_list`

### Biblioteca web
`web_library_add` · `web_library_search` · `web_library_list`

### Cumplimiento urbanístico y PGOU
`pgou_add` · `pgou_fetch` · `pgou_fetch_all` · `pgou_catalogue` · `pgou_status`  
`plan_compliance_check` · `plan_compliance_check_by_coordinates` · `plan_compliance_export`

### Geolocalización
`resolve_coordinates` · `site_compliance_context`

### Cálculos urbanísticos (matemáticas puras, sin LLM)
`calcular_edificabilidad` — Calcula techo edificable, ocupación, volumen, área libre y retranqueos.  
`calcular_pem` — Calcula Presupuesto de Ejecución Material con módulos COA 2024 por tipología y zona.  
`comparar_parcelas` — Compara 2-3 parcelas en tabla con recomendación de la mejor opción.

### Registros oficiales
`boe_search` · `boe_fetch` — Búsqueda y lectura del Boletín Oficial del Estado en tiempo real.

### Hojas de cálculo
`spreadsheet_create` · `spreadsheet_write` · `spreadsheet_read` · `spreadsheet_list_sheets`

### Visión y OCR
`vision_ocr` · `vision_analyze` — Análisis de imágenes con modelo de visión local (llava).

### Generación de documentos
`redactar_memoria` — Memoria Descriptiva completa con artículos PGOU citados literalmente.  
`exportar_memoria_pdf` — Memoria como PDF profesional con portada y branding del despacho.  
`exportar_pem_pdf` — Presupuesto PEM como PDF con desglose por partidas y disclaimer.  
`generar_informe_proyecto` — Informe integrado (edificabilidad + PEM + CTE energía + memoria) en PDF único.  
`exportar_expediente` — Exportar caso como fichero `.archon` portable.  
`importar_expediente` — Importar fichero `.archon` en la base de datos local.

### Colaboración en equipo
`sincronizar_conocimiento` — Sincroniza la base de conocimiento local con la carpeta compartida del equipo (NAS, iCloud, Dropbox).

### Skills de fase 2 (auto-registradas)
`code_patcher` · `email_responder` · `finance_briefing` · `interview_prep` · `readme_generator` · `research`

---

## 29. Sistema de memoria multicapa

ADV ARCHON tiene cuatro sistemas de memoria diferenciados:

### Memoria de sesión (MemoryStore)
`core/memory.py` — Base de datos SQLite con embeddings semánticos. Almacena registros con campos: contenido, etiquetas, fuente, tipo, namespace, categoría, importancia y metadatos. Búsqueda por similitud coseno sobre vectores `all-MiniLM-L6-v2`. Categorías: `general`, `interests`, `projects`, `people`, `preferences`.

### Base de conocimiento personal (PersonalKB)
`core/personal_kb.py` — Auto-RAG para documentos personales del usuario. El agente la consulta automáticamente cuando detecta frases como "según mis datos", "mis notas", "lo que te conté". CLI: `/kb index <ruta>`, `/kb ask <consulta>`, `/kb list`, `/kb clear`. Umbral de similitud: 0.35; máximo 4 chunks por prompt.

### Memoria episódica (EpisodicMemory)
`core/episodic_memory.py` — Historial de análisis de cumplimiento con embeddings por caso, filtros por municipio y búsqueda por similitud. Se almacena en `episodic.db`.

### Base de conocimiento PGOU (PGOUStore)
`core/pgou_store.py` — Índice de normativas municipales con chunks, artículos, embeddings y metadatos de fuente.

---

## 30. Motor de voz (STT y TTS)

### Speech-to-Text (WhisperSpeechToText)
- Modelo: Whisper local (defecto "small"), configurable vía `config.toml`
- Idioma por defecto: español (`es`)
- Dispositivo: CPU (o GPU si disponible)
- Parámetros de grabación: sample rate 16 kHz, máximo 45 s, silencio 1.2 s, umbral de amplitud 0.015
- **Wake word opcional**: usando Porcupine, activable con `wake_word_enabled = true` y `wake_word_keyword = "jarvis"`
- Métodos: `listen_once`, `listen_streaming`, `transcribe_file`, `wait_for_wake_word`

### Text-to-Speech (MacTextToSpeech)
- Motor: comando macOS `say`
- Voz por defecto: `Jorge` (español)
- Velocidad: 190 wpm
- Se activa/desactiva desde `config.toml` (`voice.enabled`)

---

## 31. Sistema de personalidad adaptativa

ADV ARCHON incorpora un sistema de personalidad que evoluciona con el uso. Al arrancar, `ArchonRuntime` carga `personality/core_identity.json` y `~/.adv-archon/personality/adaptive_state.sqlite` para construir el prompt de sistema efectivo mediante `build_system_prompt`. Al cerrar la sesión, llama a `evolve_personality` para actualizar el estado adaptativo basándose en la sesión terminada. Este sistema permite que el agente adapte su tono, énfasis y estilo al perfil de uso del despacho a lo largo del tiempo.

---

## 32. API REST (FastAPI)

ADV ARCHON incluye una API REST local para integraciones con otros sistemas. Los endpoints principales son:

### Cuenta y uso
- `POST /register` — Registrar usuario (nombre, email)
- `GET /account` — Información de cuenta
- `GET /usage` — Historial de uso y créditos

### Cumplimiento normativo
- `GET /municipalities` — Lista de municipios con PGOU indexado
- `POST /compliance-check` — Analizar plan PDF contra PGOU (con tarea asíncrona)
- `POST /compliance-check-coordinates` — Análisis por coordenadas GPS
- `GET /compliance-report/{task_id}` — Resultado del análisis asíncrono

### Geolocalización
- `GET /resolve-location` — Resolver coordenadas a municipio y contexto
- `GET /site-context` — Contexto legal completo de una parcela

### Administración
- `GET /admin/status` — Estado del sistema
- `POST /admin/api-key` — Crear clave API
- `GET /admin/keys` — Listar claves
- `POST /admin/key/{id}/deactivate` — Desactivar clave
- `POST /admin/credits/{key_id}` — Añadir créditos
- `POST /admin/municipality/fetch` — Descargar PGOU
- `POST /admin/municipality/add` — Añadir municipio
- `DELETE /admin/municipality/{name}` — Eliminar municipio

Autenticación: cabecera `X-API-Key`. La generación de PDFs es asíncrona con polling por `task_id`.

---

## 33. CLI de línea de comandos

ADV ARCHON tiene una CLI completa gestionada por `ui/commands.py`. Los comandos principales accesibles mediante `/` en el chat o desde terminal:

| Comando | Función |
|---|---|
| `/memory` | Gestión de memoria semántica (recall, record, search) |
| `/kb index <ruta>` | Indexar documento en base de conocimiento personal |
| `/kb ask <consulta>` | Consultar base de conocimiento personal |
| `/kb list` | Listar documentos indexados |
| `/kb clear` | Limpiar base de conocimiento |
| `/task list` | Listar tareas |
| `/task create` | Crear tarea |
| `/profile <nombre>` | Cambiar perfil activo |
| `/config` | Mostrar/modificar configuración |
| `/research` | Lanzar investigación agentic |

---

## 34. Configuración (`config.toml`)

El sistema se configura mediante un archivo TOML en `~/.adv-archon/config.toml`. Secciones principales:

| Sección | Parámetros relevantes |
|---|---|
| `[llm]` | `mode` (local/cloud), `ollama_model`, modelos por tarea (fast, planner, document, coding, reasoning), `task_routing_enabled`, `force_local_private_context` |
| `[ui]` | `max_tool_steps`, `show_context_panel` |
| `[memory]` | `embedding_model` (all-MiniLM-L6-v2), límites de recall |
| `[knowledge]` | Rutas de indexación, límites de ficheros |
| `[shell]` | Timeout, lista blanca de comandos |
| `[tasks]` | Zona horaria (Europe/Madrid), notificaciones |
| `[browser]` | Chromium headless, timeouts, reintentos |
| `[voice]` | Modelo Whisper, voz TTS, wake word, parámetros de grabación |
| `[google]` | Gmail, Calendar, Drive (opcional, requiere OAuth) |
| `[research]` | Queries semilla, resultados por búsqueda |
| `[team]` | Ruta compartida (NAS/iCloud/Dropbox), nombre de usuario |
| `[profiles.<nombre>]` | System hint, knowledge roots, vault roots por perfil |

Variables de entorno que sobreescriben config:
- `ADV_ARCHON_DEFAULT_MODE` — Forzar modo local/cloud
- `ADV_ARCHON_DEFAULT_OLLAMA_MODEL` — Forzar modelo
- `GEMINI_API_KEY` — Autenticación Gemini para modo cloud
- `ADV_ARCHON_HOME` — Directorio de datos alternativo
- `HF_TOKEN` — Token HuggingFace para descarga de modelos de embedding

---

## 35. Lenguaje visual de botones

Los botones siguen una jerarquía clara:

**Botones primarios** — amarillo dorado (`#C9A84C`) con texto negro en negrita: Nuevo expediente, Abrir, Ejecutar investigación, Iniciar demo comercial, Analizar con PGOU, PDF, Ejecutar Autopilot, Volver a comprobar.

**Botones secundarios** — blancos/beige con borde gris: Exportar informe PDF, Hablar con ARCHON, Adjuntar plano, Cancelar, Guardar, Cerrar, DOCX, XLSX.

**Botones positivos** — verde (`#22C55E`): Abrir informe (cuando ya existe).

**Botones de advertencia** — naranja (`#F59E0B`) en etiquetas de estado condicionado.

**Botones destructivos/críticos** — rojo (`#EF4444`) en etiquetas de riesgo jurídico alto.

---

## 36. Lenguaje visual de tarjetas

Las tarjetas son el componente principal del diseño:

- Fondo blanco roto o beige claro (`#FFFFFF` / `#FAF8F5`)
- Borde `1px solid #E8E4DD`
- Border-radius 8px
- Padding amplio (12-16px)
- Separación clara entre bloques
- Títulos en serif negra
- Texto descriptivo en sans-serif
- Sombra `0 1px 3px rgba(0,0,0,0.08)`; en hover `0 4px 12px rgba(0,0,0,0.12)`
- Botones en la parte inferior derecha

Tipos de tarjeta: hero (con borde dorado), de módulo, estadística, de lista, de formulario, de diagnóstico y de compliance (oculta hasta análisis completado).

---

## 37. Comportamiento de ventanas y aperturas

ADV ARCHON combina tres tipos de apertura:

### 1. Navegación interna
Clic en sidebar → el contenido del área central cambia manteniendo la carcasa (sidebar + barra estado + panel derecho + composer). Ejemplos: Inicio, Chat contextual, Research, Training Lab, PGOU, Geo, Briefing, Revisión Pro.

### 2. Ventanas secundarias
Módulos que se abren como ventanas flotantes con barra macOS propia y sombra. Ejemplos: Expedientes, Studio Demo, Pack Studio, Cliente / Licencia.

### 3. Modales bloqueantes
Acciones técnicas que oscurecen el fondo e impiden interacción hasta cerrar. Ejemplos: QA de voz/Ollama/visión, Selector de modelo local Ollama, Guía de prueba para despacho.

---

## 38. Personalidad visual de la interfaz

La personalidad de ADV ARCHON es muy clara: una IA profesional, local, seria y de despacho. No usa estética "tech startup" típica con azules, morados o degradados.

Parece una mezcla entre:
- Software de arquitectura
- Dashboard jurídico-urbanístico
- Asistente IA local con personalidad adaptativa
- Gestor documental con flujos de revisión profesional
- Herramienta de investigación técnica
- Laboratorio de entrenamiento de modelos
- Panel de control de infraestructura AI local
- Producto beta comercializable para despachos

El uso de serif en los títulos le da autoridad y carácter. El negro profundo de la navegación da sensación de control. El amarillo dorado comunica acción, decisión y marca. El blanco roto y beige reducen la frialdad técnica y aportan elegancia.

---

## 39. Descripción sintética final

ADV ARCHON — Beta 0.1 (`__version__ = "0.1.0"`) es una aplicación de escritorio macOS para IA aplicada a arquitectura y urbanismo. Su clase principal es `DesktopWindow(QMainWindow)`, construida sobre PySide6.

La interfaz se organiza en cinco zonas fijas: sidebar negra de 220px con 13 ítems de navegación, barra superior de estado con progreso y cancelación, área central con tarjetas y módulos intercambiables, panel derecho persistente con contexto del agente, y composer inferior con chat multimodal.

El sistema dispone de más de 60 herramientas registradas en el agente, abarcando ficheros, web, shell, Python, macOS, tareas, notas, navegador Playwright, Google Workspace, base de conocimiento, PGOU, geolocalización, cálculos urbanísticos puros, BOE, hojas de cálculo, visión OCR, generación de documentos PDF/DOCX/XLSX, colaboración en equipo y seis skills de fase 2.

La arquitectura de datos incluye: `Expediente` (SQLite, 23 campos), `PGOUStore` (chunks con embeddings semánticos), `GeoStore` (cache de coordenadas a 100m), `EpisodicMemory` (historial de análisis), `PersistentAPICache` (TTL 7 días) y `CircuitBreaker` por endpoint externo.

Las seis APIs gubernamentales españolas (Catastro, SNCZI, Natura2000, Costas, Carreteras, Nominatim) se llaman en paralelo con `ThreadPoolExecutor(max_workers=5)`, protegidas por circuit breaker y cache persistente.

El sistema incluye cuatro capas de memoria (sesión, personal-KB, episódica, PGOU), un subsistema de personalidad adaptativa, motor de voz local Whisper + macOS TTS, enrutamiento de tareas a modelos especializados, un módulo de revisión profesional humano-en-el-bucle, una API REST FastAPI para integraciones externas y una CLI completa con comandos `/kb`, `/memory`, `/task`, `/profile` y `/config`.

Todo el procesamiento es local y privado: ningún dato urbanístico sale del equipo salvo cuando el usuario activa explícitamente el modo cloud con `force_local_private_context = true` desactivado.
