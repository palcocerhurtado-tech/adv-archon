from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from statistics import median

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

DEFAULT_MODELS = ("llama3.1:8b", "deepseek-r1:7b", "deepseek-r1:14b")
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
WEB_SEARCH_QUERY = "potencias económicas y militares mundiales 2026"
WEB_FETCH_URL = "https://www.iana.org/help/example-domains"


@dataclass(slots=True)
class MetricResult:
    name: str
    context: str
    samples: list[float]
    unit: str
    error: str = ""

    @property
    def median_value(self) -> float | None:
        return median(self.samples) if self.samples else None

    @property
    def p95_value(self) -> float | None:
        if not self.samples:
            return None
        ordered = sorted(self.samples)
        idx = min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))
        return ordered[idx]


def measure_ollama_model(
    model: str,
    *,
    samples: int,
    base_url: str,
    num_ctx: int,
    num_predict: int,
) -> list[MetricResult]:
    ttft: list[float] = []
    tokens_per_second: list[float] = []
    errors: list[str] = []
    for _ in range(samples):
        try:
            first_token_s, tps = _ollama_stream_once(
                model,
                base_url=base_url,
                num_ctx=num_ctx,
                num_predict=num_predict,
            )
            ttft.append(first_token_s)
            tokens_per_second.append(tps)
        except Exception as exc:
            errors.append(str(exc))
    error = " | ".join(errors[:2])
    return [
        MetricResult("TTFT Ollama", model, ttft, "s", error=error),
        MetricResult("Tokens/segundo", model, tokens_per_second, "tok/s", error=error),
    ]


def _ollama_stream_once(
    model: str,
    *,
    base_url: str,
    num_ctx: int,
    num_predict: int,
) -> tuple[float, float]:
    prompt = (
        "Responde en español con un análisis breve y estructurado sobre cómo evaluar "
        "la viabilidad urbanística preliminar de un expediente de arquitectura. "
        "Genera una respuesta de unas 350 palabras con apartados claros."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Eres un benchmark local. Responde de forma clara."},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "keep_alive": -1,
        "options": {
            "temperature": 0.0,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
        },
    }
    started = time.perf_counter()
    first_token_at: float | None = None
    eval_count = 0
    with httpx.Client(
        timeout=httpx.Timeout(connect=10.0, read=240.0, write=30.0, pool=10.0)
    ) as client, client.stream("POST", f"{base_url.rstrip('/')}/api/chat", json=payload) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            message = data.get("message", {})
            content = message.get("content", "") if isinstance(message, dict) else ""
            if content and first_token_at is None:
                first_token_at = time.perf_counter()
            if data.get("done"):
                eval_count = int(data.get("eval_count") or 0)
                eval_duration_ns = int(data.get("eval_duration") or 0)
                if eval_count and eval_duration_ns:
                    tps = eval_count / (eval_duration_ns / 1_000_000_000)
                else:
                    elapsed_after_first = max(
                        0.001,
                        time.perf_counter() - (first_token_at or started),
                    )
                    tps = eval_count / elapsed_after_first if eval_count else 0.0
                break
    if first_token_at is None:
        raise RuntimeError(f"{model} no devolvió ningún token.")
    return first_token_at - started, tps


def measure_stt(samples: int) -> MetricResult:
    audio_path = _build_control_audio()
    values: list[float] = []
    errors: list[str] = []
    try:
        from adv_archon.voice.stt import WhisperSpeechToText

        stt = WhisperSpeechToText(
            model_name="small",
            language="es",
            device="cpu",
            compute_type="int8",
        )
        for _ in range(samples):
            started = time.perf_counter()
            try:
                stt.transcribe_file(audio_path)
                values.append(time.perf_counter() - started)
            except Exception as exc:
                errors.append(str(exc))
                break
    finally:
        audio_path.unlink(missing_ok=True)
    return MetricResult(
        "Latencia STT",
        "faster-whisper small cpu/int8 audio 5s",
        values,
        "s",
        error=" | ".join(errors[:2]),
    )


def _build_control_audio() -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="adv-archon-bench-"))
    audio_path = temp_dir / "control.aiff"
    if shutil.which("say") is None:
        raise RuntimeError("No se encontró `say` para generar audio local de control.")
    text = (
        "ADV ARCHON analiza un expediente urbanístico preliminar con una dirección, "
        "una referencia catastral, fuentes oficiales y un informe profesional."
    )
    subprocess.run(["say", "-v", "Jorge", "-o", str(audio_path), text], check=True)
    return audio_path


def measure_web_search(samples: int) -> MetricResult:
    def run_once() -> None:
        from adv_archon.tools.web import web_search

        result = web_search(WEB_SEARCH_QUERY, n=5)
        if not result.payload.get("results"):
            raise RuntimeError("web_search no devolvió resultados.")

    return _measure_call("Latencia web_search", WEB_SEARCH_QUERY, "s", samples, run_once)


def measure_web_fetch(samples: int) -> MetricResult:
    def run_once() -> None:
        from adv_archon.tools.web import web_fetch

        result = web_fetch(WEB_FETCH_URL)
        if not str(result.payload.get("text") or "").strip():
            raise RuntimeError("web_fetch no devolvió texto.")

    return _measure_call("Latencia web_fetch", WEB_FETCH_URL, "s", samples, run_once)


def _measure_call(
    name: str,
    context: str,
    unit: str,
    samples: int,
    fn: Callable[[], None],
) -> MetricResult:
    values: list[float] = []
    errors: list[str] = []
    for _ in range(samples):
        started = time.perf_counter()
        try:
            fn()
            values.append(time.perf_counter() - started)
        except Exception as exc:
            errors.append(str(exc))
            break
    return MetricResult(name, context, values, unit, error=" | ".join(errors[:2]))


def render_markdown(results: list[MetricResult]) -> str:
    lines = [
        "# Latency Baseline",
        "",
        f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Métrica | Modelo/contexto | Median | p95 | Unidad | Observaciones |",
        "|---|---|---:|---:|---|---|",
    ]
    for result in results:
        med = _fmt(result.median_value)
        p95 = _fmt(result.p95_value)
        obs = result.error.replace("|", "/") if result.error else ""
        lines.append(
            f"| {result.name} | {result.context} | {med} | {p95} | {result.unit} | {obs} |"
        )
    lines.extend(
        [
            "",
            "## Lectura inicial",
            "",
            _build_bottleneck_summary(results),
            "",
            "## Propuestas sin aplicar",
            "",
            "- Confirmar que `OLLAMA_KEEP_ALIVE=-1` mantiene calientes los modelos entre turnos.",
            "- Evaluar bajar `ollama_num_ctx` de 8192 a 4096 si los expedientes habituales caben.",
            "- Usar `llama3.2:3b` o `llama3.1:8b` para voz/routing y reservar "
            "modelos grandes para razonamiento pesado.",
            "- Mantener `num_predict` acotado para evitar generaciones largas en UI.",
            "- Paralelizar solo tool calls independientes tras medir que son cuello "
            "de botella real.",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_bottleneck_summary(results: list[MetricResult]) -> str:
    slow = [
        result
        for result in results
        if result.median_value is not None
        and result.name
        in {
            "TTFT Ollama",
            "Latencia STT",
            "Latencia web_search",
            "Latencia web_fetch",
        }
    ]
    slow.sort(key=lambda item: item.median_value or 0, reverse=True)
    if not slow:
        return "No hay suficientes muestras válidas para identificar cuellos de botella."
    bullets = []
    for item in slow[:3]:
        bullets.append(
            f"- {item.name} ({item.context}): median {_fmt(item.median_value)} {item.unit}."
        )
    return "\n".join(bullets)


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure ADV ARCHON local latency baseline.")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--num-predict", type=int, default=420)
    parser.add_argument("--output", type=Path, default=Path("docs/latency_baseline.md"))
    parser.add_argument("--skip-stt", action="store_true")
    parser.add_argument("--skip-web", action="store_true")
    args = parser.parse_args()

    results: list[MetricResult] = []
    for model in args.models:
        results.extend(
            measure_ollama_model(
                model,
                samples=args.samples,
                base_url=args.base_url,
                num_ctx=args.num_ctx,
                num_predict=args.num_predict,
            )
        )
    if not args.skip_stt:
        results.append(measure_stt(args.samples))
    if not args.skip_web:
        results.append(measure_web_search(args.samples))
        results.append(measure_web_fetch(args.samples))

    markdown = render_markdown(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
