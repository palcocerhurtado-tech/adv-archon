from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF

from adv_archon.core.expediente import Expediente, ExpedienteStore
from adv_archon.core.report_generator import generate_expediente_pdf

DEMO_TITLE = "DEMO - Cambio de uso local a vivienda"
DEMO_ADDRESS = "Calle Mayor 24, Madrid"
DEMO_NOTES = "ADV_ARCHON_DEMO_EXPEDIENTE"


def create_demo_expediente(
    store: ExpedienteStore,
    *,
    data_dir: Path,
) -> Expediente:
    """Create or refresh a fully offline demo expediente for sales/product demos."""
    demo_dir = data_dir / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    plan_path = demo_dir / "plano_demo_archon.pdf"
    report_path = demo_dir / "informe_demo_archon.pdf"
    _write_demo_plan(plan_path)

    existing = next((exp for exp in store.list_all() if exp.notes == DEMO_NOTES), None)
    exp = existing or store.create(
        title=DEMO_TITLE,
        address=DEMO_ADDRESS,
        municipality="Madrid",
        province="Madrid",
        latitude=40.415363,
        longitude=-3.707398,
        cadastral_ref="2807901VK4720G0001ZX",
        notes=DEMO_NOTES,
    )

    updated = replace(
        exp,
        title=DEMO_TITLE,
        address=DEMO_ADDRESS,
        municipality="Madrid",
        province="Madrid",
        latitude=40.415363,
        longitude=-3.707398,
        cadastral_ref="2807901VK4720G0001ZX",
        status="analizado",
        plan_path=str(plan_path),
        site_context=json.dumps(_demo_site_context(), ensure_ascii=False),
        analysis_result=json.dumps(_demo_analysis(), ensure_ascii=False),
        notes=DEMO_NOTES,
    )
    store.update(updated)

    refreshed = store.get(updated.id) or updated
    generate_expediente_pdf(refreshed, output_path=report_path)
    final = replace(refreshed, report_path=str(report_path), status="informe_listo")
    store.update(final)
    return store.get(final.id) or final


def _write_demo_plan(path: Path) -> None:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "PLANO DEMO - ADV ARCHON", align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        7,
        "Cambio de uso local a vivienda - pieza demostrativa sin validez tecnica",
        align="C",
    )
    pdf.ln(7)
    pdf.set_draw_color(40, 40, 40)
    pdf.set_line_width(0.4)
    x, y, w, h = 35, 35, 220, 120
    pdf.rect(x, y, w, h)
    pdf.line(x + 70, y, x + 70, y + h)
    pdf.line(x + 145, y, x + 145, y + h)
    pdf.line(x, y + 62, x + w, y + 62)
    pdf.set_font("Helvetica", "B", 11)
    pdf.text(x + 18, y + 30, "ESTAR / COCINA")
    pdf.text(x + 90, y + 30, "DORMITORIO")
    pdf.text(x + 162, y + 30, "BANO")
    pdf.text(x + 20, y + 92, "ACCESO")
    pdf.text(x + 88, y + 92, "PATIO")
    pdf.text(x + 160, y + 92, "INSTALACIONES")
    pdf.set_font("Helvetica", "", 8)
    pdf.text(35, 170, "Superficie util demo: 54,20 m2 | Escala grafica no vinculante")
    pdf.output(path)


def _demo_site_context() -> dict[str, object]:
    return {
        "ok": True,
        "demo": True,
        "municipality": "Madrid",
        "province": "Madrid",
        "autonomous_community": "Comunidad de Madrid",
        "latitude": 40.415363,
        "longitude": -3.707398,
        "cadastral_ref": "2807901VK4720G0001ZX",
        "cadastral_address": DEMO_ADDRESS,
        "pgou_indexed": True,
        "legal_readiness": "ready",
        "parcel_detail": {
            "surface_m2": 84,
            "construction_year": 1968,
            "floors_above": 5,
            "floors_below": 0,
            "use_detail": "Comercial / local en planta baja",
        },
        "parcel_zoning": {
            "status": "preliminary",
            "summary": "Lectura textual preliminar compatible con suelo urbano consolidado.",
            "confidence": "media",
        },
        "flood_zone": {
            "in_flood_zone": False,
            "zones": [],
            "source": "SNCZI/CNIG - demo",
        },
        "natura2000": {
            "in_protected_area": False,
            "zones": [],
            "source": "Red Natura 2000/CNIG - demo",
        },
        "costas": {
            "in_public_domain": False,
            "in_protection_servitude": False,
            "source": "SIGCOSTAS/MITECO - demo",
        },
        "carreteras": {
            "in_affection_zone": False,
            "method": "cribado geométrico demo",
            "source": "Transportes INSPIRE/CNIG - demo",
        },
        "legal_checks": [
            {
                "title": "Identificación catastral",
                "status": "ready",
                "detail": "Referencia demo localizada y coherente con dirección.",
                "recommended_action": "Usar como base de expediente preliminar.",
            },
            {
                "title": "PGOU municipal",
                "status": "ready",
                "detail": "Normativa municipal demo disponible para el análisis.",
                "recommended_action": "Contrastar siempre con visor municipal vigente.",
            },
            {
                "title": "Zonificación de parcela",
                "status": "conditional",
                "detail": "Zona/ordenanza inferida de forma textual preliminar.",
                "recommended_action": "Confirmar delimitación exacta en plano de ordenación.",
            },
            {
                "title": "Uso catastral",
                "status": "conditional",
                "detail": (
                    "Uso actual comercial; el cambio a residencial exige "
                    "comprobación urbanística."
                ),
                "recommended_action": (
                    "Revisar compatibilidad de cambio de uso y condiciones de vivienda."
                ),
            },
            {
                "title": "Dominio hidráulico",
                "status": "ready",
                "detail": "Sin afección de inundabilidad en el cribado demo.",
                "recommended_action": "Sin actuación sectorial inicial.",
            },
            {
                "title": "Costas",
                "status": "not_applicable",
                "detail": "Parcela interior sin afección litoral.",
                "recommended_action": "No aplica en este emplazamiento demo.",
            },
            {
                "title": "Carreteras y servidumbres",
                "status": "ready",
                "detail": "Sin proximidad relevante a viario estatal en cribado demo.",
                "recommended_action": "Confirmar si el expediente está junto a vía supramunicipal.",
            },
        ],
    }


def _demo_analysis() -> dict[str, object]:
    return {
        "verdict": "condicionado",
        "verdict_label": "CONDICIONADO",
        "confidence": "media",
        "summary": (
            "El expediente demo es viable como primera aproximación, pero queda "
            "condicionado a confirmar la ordenanza exacta, la compatibilidad del "
            "cambio de uso y las condiciones mínimas de habitabilidad."
        ),
        "annotations": [
            {
                "status": "warning",
                "description": (
                    "Cambio de uso comercial a residencial pendiente de "
                    "confirmación urbanística."
                ),
                "recommendation": (
                    "Comprobar ordenanza, dotaciones y condiciones de vivienda exterior."
                ),
            },
            {
                "status": "ok",
                "description": (
                    "No se detectan afecciones sectoriales demo de inundabilidad, "
                    "costas o Natura 2000."
                ),
                "recommendation": "Mantener verificación documental si el expediente avanza.",
            },
            {
                "status": "info",
                "description": "La zonificación se ha tratado como lectura preliminar textual.",
                "recommendation": (
                    "Confirmar sobre plano o visor municipal antes de presentar licencia."
                ),
            },
        ],
        "next_steps": [
            "Confirmar ordenanza exacta y grado de protección aplicable en visor municipal.",
            "Revisar condiciones de vivienda mínima, ventilación, iluminación y accesibilidad.",
            "Preparar consulta previa municipal si el cambio de uso presenta dudas.",
            "Sustituir datos demo por expediente real antes de cualquier decisión profesional.",
        ],
        "full_analysis": (
            "Este expediente demo muestra el flujo comercial de ADV ARCHON: "
            "resolución de parcela, checks sectoriales, lectura PGOU preliminar, "
            "veredicto ejecutivo y PDF de despacho. Los datos están marcados como demo."
        ),
        "generated_at": datetime.now(UTC).isoformat(timespec="minutes"),
    }


__all__ = ["DEMO_NOTES", "DEMO_TITLE", "create_demo_expediente"]
