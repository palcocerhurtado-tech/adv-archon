# ADV ARCHON Agentic Studio Roadmap

## Objetivo

Convertir ADV ARCHON en un agente de despacho local-first: un copiloto capaz de llevar
expedientes urbanísticos, investigar en profundidad, resolver cálculos, generar documentos
maquetados, preparar presentaciones, construir hojas de cálculo y ayudar en tareas de
operación diaria del estudio.

La prioridad no es imitar un modelo gigante. Con presupuesto 0 EUR, la vía realista es
sumar a Ollama una capa de orquestación, herramientas verificables, memoria local y
autoevaluación.

## Principios Tomados De Investigación Pública

- DeepSeek-R1 muestra que la mejora de razonamiento viene de bucles de verificación,
  auto-reflexión y adaptación de estrategia en tareas verificables:
  https://arxiv.org/abs/2501.12948
- ReAct combina razonamiento y acciones externas. Para ADV ARCHON significa alternar:
  planificar, buscar, leer fuentes, calcular, redactar, verificar y corregir:
  https://arxiv.org/abs/2210.03629
- Toolformer muestra la idea clave de decidir cuándo usar herramientas simples:
  búsqueda, calculadora, calendario, traductor o QA. Para ADV ARCHON, el modelo no debe
  "saberlo todo"; debe saber elegir la herramienta correcta:
  https://arxiv.org/abs/2302.04761
- DeepSeek-V3 usa eficiencia arquitectónica a escala de entrenamiento. Eso no se replica
  en un Mac, pero sí inspira routing: modelo rápido para clasificar, modelo más fuerte para
  razonamiento pesado, herramientas para cálculo exacto:
  https://arxiv.org/abs/2412.19437

## Arquitectura Propuesta

### 1. Agentic Router

Clasifica cada petición en un modo operativo:

- Expediente urbanístico.
- Investigación profunda.
- Documento entregable.
- Presentación.
- Hoja de cálculo / cálculo.
- Presupuesto / propuesta comercial.
- Operación diaria de despacho.
- Chat contextual.

Cada modo activa un playbook concreto y una lista cerrada de herramientas.

### 2. Deep Research Local-First

Flujo:

1. Descomponer la pregunta en subpreguntas.
2. Buscar en web abierta sin APIs de pago.
3. Abrir fuentes relevantes.
4. Extraer citas, datos y contradicciones.
5. Construir tabla de evidencias.
6. Generar síntesis.
7. Pasar self-check: fuentes, fecha, lagunas, incertidumbre.
8. Exportar informe DOCX/PDF si procede.

Reglas:

- Nunca mezclar inferencia con fuente.
- Mostrar fuentes y fecha de consulta.
- Penalizar respuestas sin evidencia.
- Si una fuente es débil, marcarla como secundaria.

### 3. Deliverable Studio

Motor de entregables:

- DOCX: trabajos de clase, informes de encargo, propuestas, memorias.
- PPTX: presentaciones comerciales, defensa de proyecto, briefing cliente.
- XLSX: presupuestos, PEM, comparativas, tablas de superficies, cash-flow sencillo.
- PDF: versión final maquetada.

Cada entregable debe tener:

- Brief inicial.
- Estructura.
- Fuentes/datos.
- Borrador.
- Revisión.
- Export final.

### 4. Calculation Brain

Para fórmulas complejas, el LLM no debe calcular de memoria. Debe delegar en:

- Python sandbox para cálculo simbólico/numérico.
- OpenPyXL para hojas con fórmulas.
- Herramientas puras existentes: PEM, edificabilidad, energía, comparador.

El agente debe explicar:

- Fórmula usada.
- Supuestos.
- Unidades.
- Resultado.
- Comprobación rápida.

### 5. Architect Brain + Office Memory

El expediente sigue siendo el núcleo premium.

Memoria local:

- Municipios habituales.
- Ordenanzas validadas por el despacho.
- Advertencias aceptadas/rechazadas.
- Pasos repetidos.
- Estilo de informe preferido.

Uso:

- Autopilot cambia sus preguntas según criterios recurrentes.
- El informe incorpora trazabilidad del criterio del despacho.
- ARCHON no presenta la memoria como normativa oficial.

### 6. Self-Verification Loop

Cada tarea importante pasa por un juez local:

- ¿Hay fuentes?
- ¿Hay cálculos verificables?
- ¿Hay supuestos explícitos?
- ¿Se han separado hechos e inferencias?
- ¿El entregable está completo?

Resultado:

- score 0-100.
- flags.
- acciones correctivas.

## Primeras Fases Recomendadas

### Fase A - Office Memory Gobernando Autopilot

Estado: iniciada.

Objetivo:

- Registrar decisiones del arquitecto.
- Convertirlas en políticas municipales locales.
- Usarlas en Autopilot.

### Fase B - Research Workbench

Crear una vista "Investigación" con:

- Pregunta.
- Subpreguntas generadas.
- Fuentes encontradas.
- Fuentes leídas.
- Evidencias.
- Síntesis.
- Export DOCX/PDF.

### Fase C - Deliverable Studio

Crear una vista "Entregables" con plantillas:

- Trabajo académico.
- Informe técnico.
- Presentación de cliente.
- Presupuesto de reforma.
- Tabla comparativa.

### Fase D - Spreadsheet Brain

Crear motor XLSX:

- Presupuesto por partidas.
- Comparativa de alternativas.
- Tabla de superficies.
- Fórmulas auditables.
- Export Excel + PDF resumen.

### Fase E - Presentation Brain

Crear motor PPTX:

- Guion.
- Diapositivas.
- Notas del presentador.
- Export PPTX.
- Plantilla visual Archon premium.

## Límite Honesto

ADV ARCHON puede comportarse como una IA mucho más completa si se apoya en herramientas,
memoria, verificación y flujos. No se convertirá en DeepSeek-R1 por prompt. La ruta correcta
es un sistema agentico: modelos locales pequeños y rápidos para decidir, herramientas exactas
para ejecutar, y memoria local para no empezar de cero en cada tarea.
