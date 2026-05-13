from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from fpdf import FPDF

from adv_archon.core.expediente import Expediente, ExpedienteStore
from adv_archon.core.report_generator import generate_expediente_pdf

DEMO_TITLE = "DEMO - Cambio de uso local a vivienda"
DEMO_ADDRESS = "Calle Mayor 24, Madrid"
DEMO_NOTES = "ADV_ARCHON_DEMO_EXPEDIENTE"
DEMO_NOTES_FLOOD = "ADV_ARCHON_DEMO_INUNDABILIDAD"
DEMO_NOTES_PGOU_PENDING = "ADV_ARCHON_DEMO_PGOU_PENDIENTE"


def create_demo_expediente(
    store: ExpedienteStore,
    *,
    data_dir: Path,
) -> Expediente:
    """Create or refresh a fully offline demo expediente for sales/product demos."""
    return create_studio_demo_expedientes(store, data_dir=data_dir)[0]


def create_studio_demo_expedientes(
    store: ExpedienteStore,
    *,
    data_dir: Path,
) -> list[Expediente]:
    """Create or refresh the offline Studio Edition demo portfolio."""
    demo_dir = data_dir / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    specs = [
        {
            "notes": DEMO_NOTES,
            "title": DEMO_TITLE,
            "address": DEMO_ADDRESS,
            "municipality": "Madrid",
            "province": "Madrid",
            "latitude": 40.415363,
            "longitude": -3.707398,
            "cadastral_ref": "2807901VK4720G0001ZX",
            "case_type": "cambio_uso_vivienda",
            "plan": demo_dir / "plano_demo_archon.pdf",
            "report": demo_dir / "informe_demo_archon.pdf",
            "site_context": _demo_site_context(),
            "analysis": _demo_analysis(),
        },
        {
            "notes": DEMO_NOTES_FLOOD,
            "title": "DEMO - Parcela con riesgo de inundabilidad",
            "address": "Camino de la Ribera 8, Zaragoza",
            "municipality": "Zaragoza",
            "province": "Zaragoza",
            "latitude": 41.6561,
            "longitude": -0.8773,
            "cadastral_ref": "5029701XM7152H0001QT",
            "case_type": "vivienda_unifamiliar",
            "plan": demo_dir / "plano_demo_inundabilidad.pdf",
            "report": demo_dir / "informe_demo_inundabilidad.pdf",
            "site_context": _demo_site_context_flood(),
            "analysis": _demo_analysis_flood(),
        },
        {
            "notes": DEMO_NOTES_PGOU_PENDING,
            "title": "DEMO - Vivienda unifamiliar con PGOU pendiente",
            "address": "Urbanización Los Pinos 3, Valencia",
            "municipality": "Valencia",
            "province": "Valencia",
            "latitude": 39.4699,
            "longitude": -0.3763,
            "cadastral_ref": "4625001YJ2742C0001SA",
            "case_type": "obra_nueva",
            "plan": demo_dir / "plano_demo_pgou_pendiente.pdf",
            "report": demo_dir / "informe_demo_pgou_pendiente.pdf",
            "site_context": _demo_site_context_pgou_pending(),
            "analysis": _demo_analysis_pgou_pending(),
        },
    ]
    return [_refresh_demo(store, spec) for spec in specs]


def _refresh_demo(store: ExpedienteStore, spec: dict[str, object]) -> Expediente:
    plan_path = spec["plan"]
    report_path = spec["report"]
    if not isinstance(plan_path, Path) or not isinstance(report_path, Path):
        raise TypeError("Demo paths must be Path instances.")
    _write_demo_plan(plan_path, title=str(spec["title"]), case_type=str(spec["case_type"]))

    notes = str(spec["notes"])
    existing = next((exp for exp in store.list_all() if exp.notes == notes), None)
    exp = existing or store.create(
        title=str(spec["title"]),
        address=str(spec["address"]),
        municipality=str(spec["municipality"]),
        province=str(spec["province"]),
        latitude=float(cast(float, spec["latitude"])),
        longitude=float(cast(float, spec["longitude"])),
        cadastral_ref=str(spec["cadastral_ref"]),
        notes=notes,
        case_type=str(spec["case_type"]),
    )

    updated = replace(
        exp,
        title=str(spec["title"]),
        address=str(spec["address"]),
        municipality=str(spec["municipality"]),
        province=str(spec["province"]),
        latitude=float(cast(float, spec["latitude"])),
        longitude=float(cast(float, spec["longitude"])),
        cadastral_ref=str(spec["cadastral_ref"]),
        status="analizado",
        plan_path=str(plan_path),
        site_context=json.dumps(spec["site_context"], ensure_ascii=False),
        analysis_result=json.dumps(spec["analysis"], ensure_ascii=False),
        notes=notes,
        case_type=str(spec["case_type"]),
    )
    store.update(updated)

    refreshed = store.get(updated.id) or updated
    generate_expediente_pdf(refreshed, output_path=report_path)
    final = replace(refreshed, report_path=str(report_path), status="informe_listo")
    store.update(final)
    return store.get(final.id) or final


def _write_demo_plan(path: Path, *, title: str, case_type: str) -> None:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "PLANO DEMO STUDIO - ADV ARCHON", align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        7,
        f"{title} - {case_type} - pieza demostrativa sin validez tecnica",
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


def _demo_site_context_flood() -> dict[str, object]:
    ctx = deepcopy(_demo_site_context())
    ctx.update(
        {
            "demo": True,
            "municipality": "Zaragoza",
            "province": "Zaragoza",
            "autonomous_community": "Aragón",
            "latitude": 41.6561,
            "longitude": -0.8773,
            "cadastral_ref": "5029701XM7152H0001QT",
            "cadastral_address": "Camino de la Ribera 8, Zaragoza",
            "pgou_indexed": True,
            "legal_readiness": "sectorial-review",
            "parcel_detail": {
                "surface_m2": 520,
                "construction_year": 1992,
                "floors_above": 1,
                "floors_below": 0,
                "use_detail": "Residencial unifamiliar / parcela",
            },
            "parcel_zoning": {
                "status": "preliminary",
                "summary": "Parcela residencial con lectura PGOU preliminar.",
                "confidence": "media",
            },
            "flood_zone": {
                "in_flood_zone": True,
                "zones": ["T100", "T500"],
                "source": "SNCZI/CNIG - demo",
            },
        }
    )
    ctx["legal_checks"] = [
        {
            "title": "Identificación catastral",
            "status": "ready",
            "detail": "Referencia demo localizada.",
            "recommended_action": "Usar como base preliminar.",
        },
        {
            "title": "PGOU municipal",
            "status": "ready",
            "detail": "PGOU demo disponible.",
            "recommended_action": "Contrastar parámetros de parcela.",
        },
        {
            "title": "Zonificación de parcela",
            "status": "conditional",
            "detail": "Ordenanza residencial inferida de forma preliminar.",
            "recommended_action": "Confirmar ordenanza exacta en planos municipales.",
        },
        {
            "title": "Dominio hidráulico",
            "status": "conditional",
            "detail": "Cribado demo con posible afección T100/T500.",
            "recommended_action": "Solicitar contraste SNCZI y criterio hidráulico.",
        },
        {
            "title": "Carreteras y servidumbres",
            "status": "ready",
            "detail": "Sin proximidad relevante a viario estatal en cribado demo.",
            "recommended_action": "Sin actuación inicial.",
        },
        {
            "title": "Costas",
            "status": "not_applicable",
            "detail": "Parcela interior sin afección litoral.",
            "recommended_action": "No aplica.",
        },
    ]
    return ctx


def _demo_analysis_flood() -> dict[str, object]:
    return {
        "verdict": "condicionado",
        "verdict_label": "CONDICIONADO",
        "confidence": "media",
        "summary": (
            "La parcela demo es urbanísticamente interesante, pero el cribado detecta "
            "riesgo hidráulico. El despacho debe resolver esta afección antes de "
            "prometer viabilidad al cliente."
        ),
        "annotations": [
            {
                "status": "warning",
                "description": "Posible afección de inundabilidad T100/T500.",
                "recommendation": "Contrastar con SNCZI y administración hidráulica.",
            },
            {
                "status": "warning",
                "description": "Ordenanza residencial pendiente de confirmación gráfica.",
                "recommendation": "Verificar plano de ordenación municipal.",
            },
        ],
        "next_steps": [
            "Contrastar la afección hidráulica antes de redactar anteproyecto.",
            "Confirmar parámetros de edificabilidad y retranqueos.",
            "Preparar nota al cliente con riesgo sectorial y decisión condicionada.",
        ],
        "full_analysis": (
            "Demo diseñada para mostrar que ADV ARCHON no solo genera informes: "
            "detecta riesgos que pueden cambiar la decisión comercial del despacho."
        ),
        "generated_at": datetime.now(UTC).isoformat(timespec="minutes"),
    }


def _demo_site_context_pgou_pending() -> dict[str, object]:
    ctx = deepcopy(_demo_site_context())
    ctx.update(
        {
            "demo": True,
            "municipality": "Valencia",
            "province": "Valencia",
            "autonomous_community": "Comunitat Valenciana",
            "latitude": 39.4699,
            "longitude": -0.3763,
            "cadastral_ref": "4625001YJ2742C0001SA",
            "cadastral_address": "Urbanización Los Pinos 3, Valencia",
            "pgou_indexed": False,
            "legal_readiness": "pgou-pending",
            "parcel_detail": {
                "surface_m2": 970,
                "construction_year": "",
                "floors_above": 0,
                "floors_below": 0,
                "use_detail": "Solar / parcela sin edificar",
            },
            "parcel_zoning": {
                "status": "pending",
                "summary": "Zonificación pendiente hasta cargar PGOU validado.",
                "confidence": "baja",
            },
        }
    )
    ctx["legal_checks"] = [
        {
            "title": "Identificación catastral",
            "status": "ready",
            "detail": "Referencia demo localizada.",
            "recommended_action": "Usar como punto de partida.",
        },
        {
            "title": "PGOU municipal",
            "status": "pending_review",
            "detail": "Paquete normativo municipal pendiente de validación Studio.",
            "recommended_action": "Cargar y validar PGOU antes de emitir criterio.",
        },
        {
            "title": "Zonificación de parcela",
            "status": "missing",
            "detail": "No puede fijarse zona/ordenanza sin PGOU o visor municipal.",
            "recommended_action": "Resolver ordenanza exacta como primer hito.",
        },
        {
            "title": "Dominio hidráulico",
            "status": "ready",
            "detail": "Sin alerta sectorial demo en cribado inicial.",
            "recommended_action": "Revisar de nuevo al completar PGOU.",
        },
    ]
    return ctx


def _demo_analysis_pgou_pending() -> dict[str, object]:
    return {
        "verdict": "revisar",
        "verdict_label": "FALTA INFORMACIÓN",
        "confidence": "baja",
        "summary": (
            "La vivienda unifamiliar demo no debe venderse como viable hasta cargar "
            "y validar el paquete PGOU municipal. ADV ARCHON fuerza una decisión "
            "prudente: falta información normativa crítica."
        ),
        "annotations": [
            {
                "status": "info",
                "description": "Catastro y parcela están identificados.",
                "recommendation": "Completar paquete normativo municipal.",
            },
            {
                "status": "violation",
                "description": "No existe ordenanza validada para confirmar edificabilidad.",
                "recommendation": "No prometer viabilidad hasta revisar PGOU o visor.",
            },
        ],
        "next_steps": [
            "Cargar PGOU municipal o enlazar visor de planeamiento.",
            "Confirmar zona, edificabilidad, ocupación, retranqueos y parcela mínima.",
            "Emitir informe actualizado solo cuando el paquete esté al menos preliminar.",
        ],
        "full_analysis": (
            "Demo diseñada para vender confianza: ARCHON no inventa viabilidad cuando "
            "faltan datos normativos críticos."
        ),
        "generated_at": datetime.now(UTC).isoformat(timespec="minutes"),
    }


__all__ = [
    "DEMO_NOTES",
    "DEMO_TITLE",
    "create_demo_expediente",
    "create_studio_demo_expedientes",
]
