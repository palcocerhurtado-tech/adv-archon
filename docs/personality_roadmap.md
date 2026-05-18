# Personality Roadmap

Fecha: 2026-05-18.

## Hito actual

ADV ARCHON ya tiene la infraestructura base de personalidad local-first:

- `personality/core_identity.json` como identidad estable editable a mano.
- `~/.adv-archon/personality/adaptive_state.sqlite` como estado adaptativo local.
- `personality/context_builder.py` para construir el system prompt efectivo.
- `personality/evolution.py` como punto de extensión al cerrar sesión.

El estado actual es passthrough: con `core_identity.json` vacío, el comportamiento debe
mantenerse funcionalmente igual al prompt anterior.

## Siguiente hito elegido

El siguiente hito recomendado es memoria episódica con recall asociativo.

No elegiría todavía “estado de ánimo” ni “opiniones emergentes”. Para ADV ARCHON, que
aspira a ser un producto profesional de despacho, la prioridad no es que parezca más
humano, sino que recuerde con precisión contexto útil: preferencias del arquitecto,
expedientes recurrentes, criterios del despacho, municipios habituales y decisiones
tomadas en sesiones anteriores.

## Diseño propuesto

Usar embeddings locales vía Ollama con `nomic-embed-text` y almacenamiento vectorial en
SQLite.

Componentes:

- Modelo local: `nomic-embed-text` mediante Ollama.
- Storage: `~/.adv-archon/personality/episodic_memory.sqlite`.
- Vector search: `sqlite-vec` si encaja bien en el entorno; si no, fallback inicial con
  embeddings serializados y similitud coseno en Python para volúmenes pequeños.
- Tabla mínima:
  - `episodes(id, summary, source, created_at, importance, confidence, metadata_json)`.
  - `episode_embeddings(episode_id, embedding)`.

Flujo:

1. Al cerrar conversación, `evolve_personality()` recibe un resumen de interacción.
2. Si el resumen supera un umbral de importancia, se guarda como episodio.
3. Antes de cada prompt, el `context_builder` busca 3-5 episodios relevantes.
4. El prompt solo recibe episodios con fuente, fecha y confianza, nunca memoria cruda sin anclar.

## Restricciones locales

Coste aproximado:

- `nomic-embed-text` ocupa varios cientos de MB en Ollama.
- Cada embedding suele ocupar del orden de 1-3 KB serializado, según dimensión y formato.
- 10.000 episodios quedarían normalmente por debajo de decenas de MB para vectores más
  metadatos, asumible en local.
- Latencia objetivo de recall: menos de 300 ms para bases pequeñas/medias; menos de 1 s
  para bases grandes.

En un Mac sin GPU dedicada, conviene:

- Embeddings batch pequeños.
- Recall máximo 3-5 episodios por turno.
- No resumir toda la memoria en cada prompt.
- No usar modelos 14B/32B para clasificar recuerdos.

## Riesgos

- Alucinación de recuerdos: el LLM puede mezclar episodios parecidos y afirmar algo que
  nunca ocurrió. Mitigación: cada recuerdo inyectado debe llevar fecha, fuente y texto
  literal o resumen marcado como resumen.
- Sycophancy: si el sistema premia demasiado lo que el usuario aprueba, puede volverse
  complaciente. Mitigación: guardar preferencias, no “verdades”; conservar reglas de
  honestidad y límites técnicos.
- Deriva incoherente: recuerdos viejos pueden contradecir preferencias nuevas.
  Mitigación: timestamps, decay temporal y prioridad a preferencias confirmadas.
- Privacidad: todo debe vivir en `~/.adv-archon/personality/`; nada de cloud para memoria.

## Métrica de éxito

El hito estará logrado cuando:

- ADV ARCHON recuerde un criterio estable del usuario entre sesiones sin que se lo repita.
- Cada recuerdo usado aparezca como contexto trazable, con fecha/fuente.
- El recall añada menos de 1 s al turno normal.
- La app permita borrar memoria episódica desde Ajustes.
- En una prueba de 20 preguntas, cero respuestas inventen recuerdos no guardados.

## Orden recomendado

1. Instalar y verificar `nomic-embed-text` en Ollama.
2. Crear `episodic_memory.sqlite` con schema y tests.
3. Añadir `remember_episode()` y `search_episodes()`.
4. Integrar recall en `context_builder` con límite estricto de tokens.
5. Añadir UI mínima en Ajustes: ver, buscar y borrar recuerdos.
