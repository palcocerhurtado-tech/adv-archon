from __future__ import annotations

import json
import sqlite3
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx

from adv_archon.core.config import AppConfig, load_app_config

ProbeStatus = Literal["ok", "warning", "error", "skipped"]
FindingSeverity = Literal["info", "warning", "critical"]


@dataclass(frozen=True, slots=True)
class PerformanceProbe:
    name: str
    category: str
    elapsed_ms: float
    status: ProbeStatus
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PerformanceFinding:
    severity: FindingSeverity
    area: str
    title: str
    recommendation: str
    evidence: str


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    generated_at: str
    project: str
    active_model: str
    fast_model: str
    probes: tuple[PerformanceProbe, ...]
    findings: tuple[PerformanceFinding, ...]

    @property
    def worst_severity(self) -> FindingSeverity:
        weight: dict[FindingSeverity, int] = {"info": 0, "warning": 1, "critical": 2}
        return (
            max(self.findings, key=lambda item: weight[item.severity]).severity
            if self.findings
            else "info"
        )

    def render_markdown(self) -> str:
        lines = [
            "# ADV ARCHON Performance Profiler",
            "",
            f"- Generado: {self.generated_at}",
            f"- Proyecto: {self.project}",
            f"- Modelo principal: `{self.active_model}`",
            f"- Modelo rápido/planner: `{self.fast_model or 'no configurado'}`",
            f"- Severidad máxima: **{self.worst_severity.upper()}**",
            "",
            "## Diagnóstico accionable",
        ]
        if not self.findings:
            lines.append("- Sin hallazgos críticos: el perfil base parece saludable.")
        for finding in self.findings:
            lines += [
                f"- **{finding.severity.upper()} · {finding.area}**: {finding.title}",
                f"  - Evidencia: {finding.evidence}",
                f"  - Acción: {finding.recommendation}",
            ]
        lines += ["", "## Mediciones"]
        lines += [
            f"- `{probe.category}/{probe.name}` [{probe.status}] "
            f"{probe.elapsed_ms:.1f} ms: {probe.detail}"
            for probe in self.probes
        ]
        return "\n".join(lines)


class PerformanceProfiler:
    """Profiler local-first y consciente de la arquitectura real de ADV ARCHON.

    No usa multiprocessing ni cachés JSON manuales. Mide lo que importa en la
    app de despacho: Ollama, warmup, QThread, SQLite, fuentes oficiales españolas
    y generación PDF directa.
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        *,
        project_root: Path | None = None,
        official_probe_overrides: Mapping[str, Callable[[], Any]] | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.config = config or load_app_config()
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self._official_probe_overrides = dict(official_probe_overrides or {})
        self._clock = clock
        self._probes: list[PerformanceProbe] = []

    def run(
        self,
        *,
        include_ollama: bool = True,
        include_qthread: bool = True,
        include_official_sources: bool = True,
    ) -> PerformanceReport:
        self._probes = []
        self._profile_static_architecture()
        if include_ollama:
            self._profile_ollama()
        if include_qthread:
            self._profile_qthread_dispatch()
        self._profile_sqlite_stores()
        if include_official_sources:
            self._profile_official_sources()
        self._profile_pdf_generation()
        return PerformanceReport(
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            project="ADV ARCHON Studio Workspace",
            active_model=self.config.llm.ollama_model,
            fast_model=self.config.llm.fast_local_model
            or self.config.llm.planner_local_model
            or "",
            probes=tuple(self._probes),
            findings=tuple(self._build_findings(self._probes)),
        )

    def _profile_static_architecture(self) -> None:
        warmup = self.project_root / "src/adv_archon/desktop/warmup_agent.py"
        workers = self.project_root / "src/adv_archon/desktop/workers.py"
        self._add(
            "warmup_agent",
            "architecture",
            0,
            "ok" if warmup.exists() else "warning",
            "warmup_agent.py localizado" if warmup.exists() else "No se localiza warmup_agent.py",
            {
                "keep_alive": self.config.llm.ollama_keep_alive,
                "model": self.config.llm.ollama_model,
                "fast_model": self.config.llm.fast_local_model,
            },
        )
        self._add(
            "desktop_workers",
            "architecture",
            0,
            "ok" if workers.exists() else "warning",
            "workers.py localizado; pipeline desktop usa QThread"
            if workers.exists()
            else "No se localiza workers.py",
        )

    def _profile_ollama(self) -> None:
        base = self.config.llm.ollama_base_url.rstrip("/")
        model = self.config.llm.ollama_model

        def tags() -> dict[str, Any]:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base}/api/tags")
                response.raise_for_status()
                data = response.json()
            return data if isinstance(data, dict) else {}

        result = self._measure(
            "ollama_tags",
            "ollama",
            tags,
            "Ollama responde a /api/tags",
            "Ollama no responde; la app debe degradar sin bloquear UI",
        )
        if not isinstance(result, dict):
            return
        models = [
            str(item.get("name") or "")
            for item in result.get("models", [])
            if isinstance(item, dict)
        ]
        found = any(name == model or name.startswith(f"{model}:") for name in models)
        self._add(
            "ollama_model_available",
            "ollama",
            0,
            "ok" if found else "warning",
            f"Modelo local activo `{model}` {'disponible' if found else 'no visible'}",
            {"available_models": models[:8]},
        )
        if found:
            self._profile_ollama_ttft(base, model)

    def _profile_ollama_ttft(self, base_url: str, model: str) -> None:
        first_token_at: float | None = None
        token_count = 0

        def stream() -> dict[str, Any]:
            nonlocal first_token_at, token_count
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Responde breve."},
                    {"role": "user", "content": "Di OK en una frase."},
                ],
                "stream": True,
                "keep_alive": -1,
                "options": {
                    "num_predict": 32,
                    "num_ctx": min(int(self.config.llm.ollama_num_ctx), 4096),
                    "temperature": 0,
                },
            }
            start = self._clock()
            with (
                httpx.Client(timeout=30.0) as client,
                client.stream(
                    "POST",
                    f"{base_url}/api/chat",
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message", {})
                    content = message.get("content", "") if isinstance(message, dict) else ""
                    if content:
                        first_token_at = first_token_at or self._clock() - start
                        token_count += max(1, len(str(content).split()))
                    if data.get("done"):
                        break
            total = self._clock() - start
            return {
                "ttft_ms": (first_token_at or total) * 1000,
                "tokens_per_second": token_count / total if total else 0.0,
                "tokens": token_count,
            }

        result = self._measure(
            "ollama_ttft",
            "ollama",
            stream,
            "Streaming local medido con /api/chat",
            "No se pudo medir streaming local de Ollama",
        )
        if isinstance(result, dict):
            self._probes[-1].metadata.update(result)

    def _profile_qthread_dispatch(self) -> None:
        try:
            from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal
        except Exception as exc:
            self._add("qthread_roundtrip", "desktop", 0, "skipped", f"PySide6 no disponible: {exc}")
            return

        class ProbeWorker(QObject):
            done = Signal()

            def run(self) -> None:
                self.done.emit()

        app = QCoreApplication.instance() or QCoreApplication([])
        thread = QThread()
        worker = ProbeWorker()
        worker.moveToThread(thread)
        elapsed: dict[str, float] = {}
        started = self._clock()

        def finish() -> None:
            elapsed["value"] = (self._clock() - started) * 1000
            thread.quit()

        worker.done.connect(finish)
        thread.started.connect(worker.run)
        thread.start()
        deadline = self._clock() + 2
        while thread.isRunning() and self._clock() < deadline:
            app.processEvents()
            time.sleep(0.001)
        if thread.isRunning():
            thread.quit()
            thread.wait(500)
            self._add("qthread_roundtrip", "desktop", 2000, "warning", "QThread no completó en 2s")
            return
        thread.wait(500)
        ms = elapsed.get("value", 0.0)
        self._add(
            "qthread_roundtrip",
            "desktop",
            ms,
            "ok" if ms < 100 else "warning",
            "Roundtrip QThread mínimo para worker desktop",
        )

    def _profile_sqlite_stores(self) -> None:
        for name, path in {
            "pgou_db": self.config.paths.pgou_db,
            "geo_db": self.config.paths.geo_db,
            "expedientes_db": self.config.paths.root / "expedientes.db",
            "knowledge_db": self.config.paths.knowledge_db,
        }.items():
            self._profile_sqlite_db(name, path)

    def _profile_sqlite_db(self, name: str, path: Path) -> None:
        if not path.exists():
            self._add(name, "sqlite", 0, "skipped", f"{path.name} no existe todavía")
            return

        def query() -> dict[str, Any]:
            with sqlite3.connect(path) as conn:
                journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
                pages = conn.execute("PRAGMA page_count").fetchone()[0]
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            return {
                "journal_mode": str(journal),
                "page_count": int(pages),
                "table_count": len(tables),
            }

        result = self._measure(
            name, "sqlite", query, f"Consulta SQLite sobre {path.name}", f"Fallo en {path.name}"
        )
        if isinstance(result, dict):
            self._probes[-1].metadata.update(result)

    def _profile_official_sources(self) -> None:
        for name, fn in self._official_source_probes().items():
            result = self._measure(
                name,
                "official_sources",
                fn,
                f"{name} respondió en el flujo urbanístico",
                f"{name} falló; el expediente debe marcar pending_review",
            )
            if isinstance(result, dict):
                self._probes[-1].metadata.update(_summarize_payload(result))

    def _official_source_probes(self) -> dict[str, Callable[[], Any]]:
        if self._official_probe_overrides:
            return dict(self._official_probe_overrides)
        lat, lon = 40.4168, -3.7038

        def geocode() -> dict[str, Any]:
            from adv_archon.integrations.nominatim import reverse_geocode

            return reverse_geocode(lat, lon)

        def catastro() -> dict[str, Any]:
            from adv_archon.integrations.catastro import get_cadastral_data

            return get_cadastral_data(lat, lon)

        def pgou() -> dict[str, Any]:
            from adv_archon.core.pgou_store import PGOUStore

            store = PGOUStore(self.config.paths.pgou_db)
            return {
                "indexed_count": len(store.list_municipalities()),
                "madrid_indexed": store.get_municipality("Madrid") is not None,
            }

        return {
            "geocodificacion_nominatim": geocode,
            "catastro_ovc": catastro,
            "snczi_cnig": self._official_fn("snczi", "query_flood_zone", lat, lon),
            "red_natura_2000_cnig": self._official_fn(
                "natura2000", "query_protected_area", lat, lon
            ),
            "costas_sigcostas": self._official_fn("costas", "query_coastal_zone", lat, lon),
            "carreteras_idee": self._official_fn("carreteras", "query_road_zone", lat, lon),
            "pgou_sqlite": pgou,
        }

    @staticmethod
    def _official_fn(module_name: str, fn_name: str, lat: float, lon: float) -> Callable[[], Any]:
        def call() -> Any:
            module = __import__(f"adv_archon.integrations.{module_name}", fromlist=[fn_name])
            return getattr(module, fn_name)(lat, lon)

        return call

    def _profile_pdf_generation(self) -> None:
        def generate() -> dict[str, Any]:
            from adv_archon.core.expediente import ExpedienteStore
            from adv_archon.core.report_generator import generate_expediente_pdf

            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                store = ExpedienteStore(root / "expedientes.db")
                exp = store.create(
                    title="Profiler - expediente demo",
                    address="Calle Mayor 24, Madrid",
                    municipality="Madrid",
                    province="Madrid",
                    cadastral_ref="2807901VK4720G0001ZX",
                    case_type="cambio_uso_vivienda",
                )
                exp.site_context = json.dumps(
                    _demo_site_context(exp.cadastral_ref), ensure_ascii=False
                )
                exp.analysis_result = json.dumps(
                    {
                        "verdict": "viable",
                        "summary": "Profiler PDF generado sin llamada LLM.",
                        "next_steps": ["Validar ordenanza exacta."],
                    },
                    ensure_ascii=False,
                )
                path = generate_expediente_pdf(exp, output_path=root / "profiler.pdf")
                return {"pdf_bytes": path.stat().st_size}

        result = self._measure(
            "generate_expediente_pdf",
            "pdf",
            generate,
            "Generación PDF directa sin LLM",
            "La generación PDF falló; revisar report_generator.py",
        )
        if isinstance(result, dict):
            self._probes[-1].metadata.update(result)

    def _build_findings(self, probes: list[PerformanceProbe]) -> list[PerformanceFinding]:
        findings: list[PerformanceFinding] = []
        by_name = {probe.name: probe for probe in probes}
        self._find_ollama(findings, by_name)
        self._find_qthread(findings, by_name)
        self._find_sqlite(findings, probes)
        self._find_official_sources(findings, probes)
        self._find_pdf(findings, by_name)
        return findings

    def _find_ollama(
        self, findings: list[PerformanceFinding], by_name: dict[str, PerformanceProbe]
    ) -> None:
        tags = by_name.get("ollama_tags")
        if tags and tags.status == "error":
            findings.append(
                _finding(
                    "critical",
                    "Ollama",
                    "El motor local no responde.",
                    "Mostrar badge 'Ollama sin conexión' y pedir abrir "
                    "Ollama.app u `ollama serve`.",
                    tags.detail,
                )
            )
            return
        model = by_name.get("ollama_model_available")
        if model and model.status == "warning":
            findings.append(
                _finding(
                    "warning",
                    "Ollama",
                    "El modelo configurado no aparece en Ollama.",
                    f"Ejecutar `ollama pull {self.config.llm.ollama_model}` "
                    "o cambiar Ajustes a un modelo instalado.",
                    model.detail,
                )
            )
        ttft = by_name.get("ollama_ttft")
        if ttft and ttft.status == "ok":
            ttft_ms = float(ttft.metadata.get("ttft_ms") or ttft.elapsed_ms)
            tps = float(ttft.metadata.get("tokens_per_second") or 0)
            if ttft_ms > 10_000:
                findings.append(
                    _finding(
                        "critical",
                        "Ollama",
                        "Primer token demasiado lento.",
                        "Activar warmup con `warmup_agent.py`, mantener "
                        '`ollama_keep_alive = "-1"` y usar `llama3.2:3b` '
                        "para planner/voz.",
                        f"TTFT {ttft_ms:.0f} ms con {self.config.llm.ollama_model}.",
                    )
                )
            elif ttft_ms > 3_000:
                findings.append(
                    _finding(
                        "warning",
                        "Ollama",
                        "El modelo local entra frío o tarda en prefilling.",
                        "Precalentar `llama3.1:8b` y `llama3.2:3b`; "
                        "evitar `deepseek-r1:14b` en chat interactivo.",
                        f"TTFT {ttft_ms:.0f} ms.",
                    )
                )
            if 0 < tps < 12:
                findings.append(
                    _finding(
                        "warning",
                        "Ollama",
                        "La generación local va justa para UX tipo ChatGPT.",
                        "Bajar `num_predict`, usar modelo Q4 y reservar "
                        "modelos grandes solo para tareas bajo demanda.",
                        f"{tps:.1f} tokens/s medidos.",
                    )
                )
        if self.config.llm.ollama_keep_alive.strip() != "-1":
            findings.append(
                _finding(
                    "warning",
                    "Warmup",
                    "Ollama puede descargar el modelo de RAM entre turnos.",
                    'Configurar `ollama_keep_alive = "-1"` para mantener el modelo caliente.',
                    f"keep_alive actual: {self.config.llm.ollama_keep_alive}",
                )
            )

    @staticmethod
    def _find_qthread(
        findings: list[PerformanceFinding], by_name: dict[str, PerformanceProbe]
    ) -> None:
        probe = by_name.get("qthread_roundtrip")
        if probe and probe.status == "warning":
            findings.append(
                _finding(
                    "warning",
                    "PySide6/QThread",
                    "El roundtrip de worker no es fluido.",
                    "Revisar que Catastro, SNCZI, Ollama y PDF sigan en "
                    "workers y no en el hilo principal.",
                    f"Roundtrip {probe.elapsed_ms:.1f} ms.",
                )
            )

    @staticmethod
    def _find_sqlite(findings: list[PerformanceFinding], probes: list[PerformanceProbe]) -> None:
        for probe in probes:
            if probe.category != "sqlite" or probe.status == "skipped":
                continue
            if probe.status == "error" or probe.elapsed_ms > 80:
                findings.append(
                    _finding(
                        "warning",
                        "SQLite",
                        f"Consulta lenta o fallida en {probe.name}.",
                        "Mantener WAL, evitar migraciones en caliente y "
                        "revisar índices si PGOU/Knowledge crecen.",
                        f"{probe.detail}; {probe.elapsed_ms:.1f} ms.",
                    )
                )
            if probe.metadata.get("journal_mode") not in (None, "wal", "memory"):
                findings.append(
                    _finding(
                        "warning",
                        "SQLite",
                        f"{probe.name} no usa WAL.",
                        "Activar PRAGMA journal_mode=WAL para evitar bloqueos entre UI y workers.",
                        f"journal_mode={probe.metadata.get('journal_mode')}",
                    )
                )

    @staticmethod
    def _find_official_sources(
        findings: list[PerformanceFinding], probes: list[PerformanceProbe]
    ) -> None:
        for probe in probes:
            if probe.category != "official_sources":
                continue
            if probe.status == "error":
                findings.append(
                    _finding(
                        "warning",
                        "Fuentes oficiales",
                        f"{probe.name} no respondió.",
                        "No romper el expediente: marcar el check como "
                        "`pending_review` y exportar con advertencia visible.",
                        probe.detail,
                    )
                )
            elif probe.elapsed_ms > 5_000:
                findings.append(
                    _finding(
                        "warning",
                        "Fuentes oficiales",
                        f"{probe.name} tarda demasiado.",
                        "Aplicar cache TTL de una hora por coordenadas/ref. "
                        "catastral y mostrar progreso indeterminado.",
                        f"{probe.elapsed_ms:.0f} ms.",
                    )
                )

    @staticmethod
    def _find_pdf(findings: list[PerformanceFinding], by_name: dict[str, PerformanceProbe]) -> None:
        pdf = by_name.get("generate_expediente_pdf")
        if not pdf:
            return
        if pdf.status == "error":
            findings.append(
                _finding(
                    "critical",
                    "PDF",
                    "El informe no se genera.",
                    "Revisar `report_generator.py`; el PDF debe generarse sin LLM y en worker.",
                    pdf.detail,
                )
            )
        elif pdf.elapsed_ms > 1_500:
            findings.append(
                _finding(
                    "warning",
                    "PDF",
                    "El PDF directo tarda más de lo esperable.",
                    "Mantener logo cacheado, evitar imágenes enormes y no invocar LLM al exportar.",
                    f"{pdf.elapsed_ms:.0f} ms.",
                )
            )

    def _measure(self, name: str, category: str, fn: Callable[[], Any], ok: str, error: str) -> Any:
        start = self._clock()
        try:
            result = fn()
        except Exception as exc:
            self._add(
                name,
                category,
                (self._clock() - start) * 1000,
                "error",
                f"{error}: {exc}",
                {"error": type(exc).__name__},
            )
            return None
        elapsed = (self._clock() - start) * 1000
        self._add(
            name, category, elapsed, "ok" if elapsed < _threshold(category) else "warning", ok
        )
        return result

    def _add(
        self,
        name: str,
        category: str,
        elapsed_ms: float,
        status: ProbeStatus,
        detail: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._probes.append(
            PerformanceProbe(
                name, category, round(elapsed_ms, 3), status, detail, dict(metadata or {})
            )
        )


def _finding(
    severity: FindingSeverity, area: str, title: str, recommendation: str, evidence: str
) -> PerformanceFinding:
    return PerformanceFinding(severity, area, title, recommendation, evidence)


def _threshold(category: str) -> float:
    return {
        "ollama": 3_000.0,
        "desktop": 100.0,
        "sqlite": 80.0,
        "official_sources": 5_000.0,
        "pdf": 1_500.0,
    }.get(category, 1_000.0)


def _summarize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in (
            "ok",
            "municipality",
            "province",
            "cadastral_ref",
            "in_flood_zone",
            "in_protected_area",
            "in_public_domain",
            "in_affection_zone",
            "indexed_count",
            "madrid_indexed",
            "error",
        )
        if key in payload
    }


def _demo_site_context(cadastral_ref: str) -> dict[str, Any]:
    return {
        "municipality": "Madrid",
        "cadastral_ref": cadastral_ref,
        "parcel_detail": {"surface_m2": 84, "use_detail": "Comercial"},
        "flood_zone": {"in_flood_zone": False, "source": "SNCZI/CNIG"},
        "natura2000": {"in_protected_area": False, "source": "Red Natura/CNIG"},
        "costas": {"in_public_domain": False, "source": "SIGCOSTAS"},
        "carreteras": {"in_affection_zone": False, "source": "Transportes INSPIRE/CNIG"},
        "legal_checks": [
            {"title": "Catastro", "status": "ready", "detail": "OK"},
            {"title": "PGOU municipal", "status": "ready", "detail": "OK"},
        ],
    }


__all__ = [
    "PerformanceFinding",
    "PerformanceProbe",
    "PerformanceProfiler",
    "PerformanceReport",
]
