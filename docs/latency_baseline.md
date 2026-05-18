# Latency Baseline

Fecha: 2026-05-18 12:31:19

| Métrica | Modelo/contexto | Median | p95 | Unidad | Observaciones |
|---|---|---:|---:|---|---|
| TTFT Ollama | llama3.1:8b | 0.111 | 2.747 | s |  |
| Tokens/segundo | llama3.1:8b | 21.907 | 22.542 | tok/s |  |
| TTFT Ollama | deepseek-r1:7b | 12.347 | 13.403 | s |  |
| Tokens/segundo | deepseek-r1:7b | 24.428 | 24.613 | tok/s |  |
| TTFT Ollama | deepseek-r1:14b | n/a | n/a | s | deepseek-r1:14b no devolvió ningún token. / deepseek-r1:14b no devolvió ningún token. |
| Tokens/segundo | deepseek-r1:14b | n/a | n/a | tok/s | deepseek-r1:14b no devolvió ningún token. / deepseek-r1:14b no devolvió ningún token. |
| Latencia STT | faster-whisper small cpu/int8 audio 5s | 1.146 | 3.613 | s |  |
| Latencia web_search | potencias económicas y militares mundiales 2026 | 1.480 | 2.199 | s | Medida en segunda pasada web-only. |
| Latencia web_fetch | https://www.iana.org/help/example-domains | 0.808 | 0.835 | s | Medida en segunda pasada web-only. |

## Lectura inicial

- TTFT Ollama (deepseek-r1:7b): median 12.347 s.
- Latencia STT (faster-whisper small cpu/int8 audio 5s): median 1.146 s.
- Latencia web_search (potencias económicas y militares mundiales 2026): median 1.480 s.

## Notas de medición

- `llama3.1:8b` ya estaba caliente: TTFT mediano muy bajo, pero p95 de 2.747 s.
- `deepseek-r1:7b` generó a buen ritmo, pero el TTFT mediano fue alto: 12.347 s.
- `deepseek-r1:14b` no devolvió token visible durante la prueba. Esto no significa que el modelo no exista; significa que, para este flujo interactivo concreto, no ofreció primera salida útil medible.
- El primer `web_fetch` contra `example.com` cayó por reset en fallback browser. Se repitió con una URL estática de IANA para medir el fetch sin contaminar el resultado.

## Propuestas sin aplicar

- Confirmar que `OLLAMA_KEEP_ALIVE=-1` mantiene calientes los modelos entre turnos.
- Evaluar bajar `ollama_num_ctx` de 8192 a 4096 si los expedientes habituales caben.
- Mantener `num_predict` acotado para evitar generaciones largas en UI.
- Paralelizar solo tool calls independientes tras medir que son cuello de botella real.

## Optimización aplicada

Tras esta medición se aprobó la siguiente política local:

- `planner_local_model = "llama3.2:3b"` para decisiones de herramienta.
- `fast_local_model = "llama3.2:3b"` para rutas rápidas.
- `reasoning_local_model = "llama3.1:8b"` para razonamiento interactivo.
- `document_local_model = "llama3.1:8b"` para documentos en flujo normal.
- `coding_local_model = "deepseek-r1:14b"` reservado para tareas pesadas bajo demanda.

Smoke posterior:

| Métrica | Modelo/contexto | Median | p95 | Unidad |
|---|---|---:|---:|---|
| TTFT Ollama | llama3.2:3b | 0.081 | 0.663 | s |
| Tokens/segundo | llama3.2:3b | 50.017 | 51.551 | tok/s |
| TTFT Ollama | llama3.1:8b | 0.105 | 2.489 | s |
| Tokens/segundo | llama3.1:8b | 22.252 | 22.774 | tok/s |
