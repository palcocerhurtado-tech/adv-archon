#!/usr/bin/env python3
"""
Test launcher for ADV ARCHON v2 redesigned UI.

Runs with synthetic data — no ArchonRuntime required.

Usage:
    uv run python scripts/test_redesign.py
    uv run python scripts/test_redesign.py --dark
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make sure the src package is importable when running from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from adv_archon.desktop.redesigned_main_window import RedesignedMainWindow

# ── Fake expediente data ───────────────────────────────────────────────────
DEMO_EXPEDIENTES = [
    {
        "id": "demo-001",
        "title": "Vivienda unifamiliar · PGOU pendiente",
        "municipality": "Valencia",
        "address": "Calle Mayor 12, Valencia",
        "province": "Valencia",
        "case_type": "Obra nueva",
        "status": "en_revision",
        "extracted_params": '{"uso_principal": "residencial", "edificabilidad_m2m2": 1.5, "altura_maxima_m": 10.5, "num_plantas": 3, "ocupacion_pct": 60, "confianza": "media"}',  # noqa: E501
        "site_context": '{"legal_checks": ["Sin riesgo de inundación (T500)", "Fuera dominio público marítimo", "Catastro consultado: ref. 5523AB001"]}',  # noqa: E501
    },
    {
        "id": "demo-002",
        "title": "Parcela con riesgo de inundabilidad",
        "municipality": "Zaragoza",
        "address": "Polígono Industrial Sur, Zaragoza",
        "province": "Zaragoza",
        "case_type": "Obra nueva industrial",
        "status": "analizado",
        "extracted_params": '{"uso_principal": "industrial", "edificabilidad_m2m2": 0.8, "altura_maxima_m": 8.0, "num_plantas": 1, "ocupacion_pct": 70, "confianza": "alta"}',  # noqa: E501
        "site_context": '{"legal_checks": ["⚠ Riesgo inundación T100 (SNCZI)", "Fuera dominio público costas", "Natura 2000: no afecta"]}',  # noqa: E501
    },
    {
        "id": "demo-003",
        "title": "Cambio de uso local a vivienda",
        "municipality": "Madrid",
        "address": "Calle Gran Vía 45, Madrid",
        "province": "Madrid",
        "case_type": "Cambio de uso",
        "status": "borrador",
        "extracted_params": '{"uso_principal": "residencial", "edificabilidad_m2m2": 2.0, "altura_maxima_m": 15.0, "num_plantas": 5, "ocupacion_pct": 80, "confianza": "alta"}',  # noqa: E501
        "site_context": '{"legal_checks": ["Sin riesgo inundación", "Zona urbana consolidada", "PGOU Madrid 2020 indexado ✓"]}',  # noqa: E501
    },
]


def run_demo(window: RedesignedMainWindow) -> None:
    """Inject demo data and simulate agent activity."""
    # Load expediente list
    window.set_expediente_list(DEMO_EXPEDIENTES)
    window.set_model("llama3.1:8b")
    window.set_mode("local")

    t = 0

    def after(ms: int, fn):
        QTimer.singleShot(t + ms, fn)

    # Simulate activating first expediente
    after(600, lambda: window.set_expediente(DEMO_EXPEDIENTES[0]))

    # Simulate a tool call (opens right panel automatically)
    after(1200, lambda: window.receive_tool_call("resolve_coordinates"))
    after(1600, lambda: window.receive_tool_call("plan_compliance_check"))
    after(2000, lambda: window.receive_source("Art. 23.1 PGOU Valencia · Zona residencial plurifamiliar"))  # noqa: E501
    after(2200, lambda: window.receive_source("Catastro OVC · ref 5523AB001 consultada"))

    # Simulate streaming response
    DEMO_RESPONSE = (
        "He analizado el expediente **Vivienda unifamiliar · PGOU pendiente** "
        "en Valencia.\n\n"
        "### Resultado del análisis\n\n"
        "| Parámetro | Plan | PGOU | Estado |\n"
        "|---|---|---|---|\n"
        "| Altura | 10.5 m | 10.5 m | ✅ Cumple |\n"
        "| Edificabilidad | 1.5 m²/m² | 1.5 m²/m² | ✅ Cumple |\n"
        "| Ocupación | 60 % | 60 % | ✅ Cumple |\n"
        "| PGOU | — | **Pendiente** | ⚠ Sin validar |\n\n"
        "**Veredicto preliminar:** CONDICIONADO — pendiente de validar el PGOU municipal.\n\n"
        "Puedo generar el informe PDF con los datos actuales o esperar a que "
        "se indexe el PGOU de Valencia. Escribe `exportar PDF` o pulsa **⌘E**."
    )

    after(2800, window._chat.start_stream)

    chunk_delay = 2800 + 200
    chunk_size = 6
    for i in range(0, len(DEMO_RESPONSE), chunk_size):
        chunk = DEMO_RESPONSE[i:i + chunk_size]
        QTimer.singleShot(chunk_delay, lambda c=chunk: window.receive_chunk(c))
        chunk_delay += 28

    QTimer.singleShot(chunk_delay + 100, window.receive_final)
    QTimer.singleShot(chunk_delay + 200, lambda: window._composer.set_enabled_input(True))


def main() -> None:
    dark = "--dark" in sys.argv

    app = QApplication(sys.argv)
    app.setApplicationName("ADV ARCHON")
    app.setOrganizationName("ADV")

    if dark:
        from PySide6.QtGui import QColor, QPalette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1c1c1e"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#eeeeee"))
        app.setPalette(palette)

    window = RedesignedMainWindow()
    window.show()

    # Wire the command_triggered signal to a simple printer for testing
    window.command_triggered.connect(
        lambda cid: print(f"[COMMAND] {cid}")
    )
    window.prompt_submitted.connect(
        lambda text, atts: print(f"[PROMPT] '{text}' atts={[str(a) for a in atts]}")
    )

    # Run demo after window is shown
    QTimer.singleShot(300, lambda: run_demo(window))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
