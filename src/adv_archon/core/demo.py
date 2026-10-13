from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from fpdf import FPDF

from adv_archon.core.expediente import Expediente, ExpedienteStore
from adv_archon.core.municipal_planning import (
    MOLINA_DE_ARAGON_WARNING,
    MOLINA_DE_ARAGON_ZONING,
    molina_de_aragon_planning_payload,
    seed_molina_de_aragon_planning,
    write_molina_de_aragon_catalog,
)
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.core.report_generator import generate_expediente_pdf

DEMO_TITLE = "DEMO - Cambio de uso local a vivienda"
DEMO_ADDRESS = "Calle Mayor 24, Madrid"
DEMO_NOTES = "ADV_ARCHON_DEMO_EXPEDIENTE"
DEMO_NOTES_FLOOD = "ADV_ARCHON_DEMO_INUNDABILIDAD"
DEMO_NOTES_PGOU_PENDING = "ADV_ARCHON_DEMO_PGOU_PENDIENTE"
DEMO_NOTES_MOLINA = "ADV_ARCHON_DEMO_MOLINA_DE_ARAGON"


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
        {
            "notes": DEMO_NOTES_MOLINA,
            "title": "DEMO - Consulta urbanística — Molina de Aragón",
            "address": "Plaza de España 1, Molina de Aragón",
            "municipality": "Molina de Aragón",
            "province": "Guadalajara",
            "latitude": 40.8436,
            "longitude": -1.8876,
            "cadastral_ref": "19190A000000000000XX",
            "case_type": "vivienda_unifamiliar",
            "plan": demo_dir / "plano_demo_molina_de_aragon.pdf",
            "report": demo_dir / "informe_demo_molina_de_aragon.pdf",
            "site_context": _demo_site_context_molina(),
            "analysis": _demo_analysis_molina(),
        },
    ]
    return [_refresh_demo(store, spec) for spec in specs]


def create_molina_de_aragon_demo(
    store: ExpedienteStore,
    *,
    data_dir: Path,
    pgou_store: PGOUStore | None = None,
) -> Expediente:
    """Create the curated Molina de Aragón demo expediente and catalogue files."""
    write_molina_de_aragon_catalog(data_dir)
    if pgou_store is not None:
        seed_molina_de_aragon_planning(pgou_store)
    demo_dir = data_dir / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    return _refresh_demo(
        store,
        {
            "notes": DEMO_NOTES_MOLINA,
            "title": "DEMO - Consulta urbanística — Molina de Aragón",
            "address": "Plaza de España 1, Molina de Aragón",
            "municipality": "Molina de Aragón",
            "province": "Guadalajara",
            "latitude": 40.8436,
            "longitude": -1.8876,
            "cadastral_ref": "19190A000000000000XX",
            "case_type": "vivienda_unifamiliar",
            "plan": demo_dir / "plano_demo_molina_de_aragon.pdf",
            "report": demo_dir / "informe_demo_molina_de_aragon.pdf",
            "site_context": _demo_site_context_molina(),
            "analysis": _demo_analysis_molina(),
        },
    )


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
        _demo_pdf_text(
            f"{title} - {case_type} - pieza demostrativa sin validez tecnica"
        ),
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


def _demo_pdf_text(text: str) -> str:
    replacements = {
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


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


def _demo_site_context_molina() -> dict[str, object]:
    planning = molina_de_aragon_planning_payload()
    zoning = dict(MOLINA_DE_ARAGON_ZONING)
    zoning.update(
        {
            "queried": True,
            "available": True,
            "source": planning["source_url"],
            "method": "búsqueda textual preliminar en Normas Subsidiarias indexadas",
            "excerpts": [
                {
                    "article_ref": "Ordenanza 07",
                    "title": "Residencial unifamiliar",
                    "text": (
                        "La documentación municipal cita una ordenanza residencial "
                        "unifamiliar. La adscripción exacta debe confirmarse sobre plano."
                    ),
                    "source": planning["source_url"],
                }
            ],
        }
    )
    return {
        "ok": True,
        "demo": True,
        "municipality": "Molina de Aragón",
        "province": "Guadalajara",
        "autonomous_community": "Castilla-La Mancha",
        "latitude": 40.8436,
        "longitude": -1.8876,
        "cadastral_ref": "19190A000000000000XX",
        "cadastral_address": "Plaza de España 1, Molina de Aragón",
        "pgou_indexed": True,
        "legal_readiness": "preliminary-ready",
        "planning": planning,
        "parcel_detail": {
            "surface_m2": 118,
            "construction_year": 1950,
            "floors_above": 2,
            "floors_below": 0,
            "use_detail": "Residencial / núcleo urbano histórico",
        },
        "parcel_zoning": zoning,
        "flood_zone": {
            "queried": True,
            "in_flood_zone": False,
            "periods": [],
            "source": "SNCZI/CNIG - demo",
        },
        "natura2000": {
            "queried": True,
            "in_protected_area": False,
            "zones": [],
            "source": "Red Natura 2000/CNIG - demo",
        },
        "costas": {
            "queried": False,
            "in_public_domain": False,
            "in_protection_servitude": False,
            "source": "SIGCOSTAS/MITECO - no aplicable",
        },
        "carreteras": {
            "queried": True,
            "in_affection_zone": False,
            "method": "cribado geométrico demo sobre viario oficial",
            "source": "Transportes INSPIRE/CNIG - demo",
        },
        "legal_checks": [
            {
                "code": "cadastral-identification",
                "title": "Identificación catastral",
                "status": "ready",
                "authority": "Catastro OVC",
                "detail": "Referencia demo fijada para mostrar el flujo de consulta.",
                "recommended_action": "Sustituir por referencia real del expediente.",
                "confidence": "medium",
            },
            {
                "code": "pgou-municipal",
                "title": "Planeamiento municipal aplicable",
                "status": "ready",
                "authority": "Ayuntamiento de Molina de Aragón",
                "detail": (
                    "Paquete preliminar de Normas Subsidiarias indexado con fuente "
                    "municipal oficial."
                ),
                "recommended_action": "Consultar el PDF municipal vigente antes de firmar.",
                "confidence": "medium",
            },
            {
                "code": "parcel-zoning",
                "title": "Ordenanza y zona de parcela",
                "status": "conditional",
                "authority": "Normas Subsidiarias de Molina de Aragón",
                "detail": (
                    "Indicio textual de Ordenanza 07 residencial unifamiliar. "
                    "No hay cruce cartográfico exacto en esta demo."
                ),
                "recommended_action": (
                    "Confirmar ordenanza en plano, ficha o consulta técnica municipal."
                ),
                "confidence": "low",
            },
            {
                "code": "heritage-environment",
                "title": "Patrimonio y entorno histórico",
                "status": "pending_review",
                "authority": "Ayuntamiento / Castilla-La Mancha",
                "detail": (
                    "Molina de Aragón tiene un carácter histórico relevante. "
                    "El expediente debe revisar catálogo patrimonial y protección local."
                ),
                "recommended_action": "Pedir contraste de protección patrimonial municipal.",
                "confidence": "medium",
            },
            {
                "code": "hydraulic-domain",
                "title": "Cauces, inundabilidad y dominio público hidráulico",
                "status": "ready",
                "authority": "SNCZI/CNIG",
                "detail": "Sin afección hidráulica en el cribado demo.",
                "recommended_action": "Revisar SNCZI con coordenadas reales si avanza.",
                "confidence": "medium",
            },
            {
                "code": "coastal-domain",
                "title": "Costas",
                "status": "not_applicable",
                "authority": "SIGCOSTAS/MITECO",
                "detail": "Guadalajara no tiene fachada litoral.",
                "recommended_action": "No aplica.",
                "confidence": "high",
            },
            {
                "code": "roads-servitudes",
                "title": "Carreteras y servidumbres",
                "status": "ready",
                "authority": "Transportes INSPIRE/CNIG",
                "detail": "Sin proximidad viaria relevante en el cribado demo.",
                "recommended_action": (
                    "Contrastar manualmente si la parcela real linda con carretera."
                ),
                "confidence": "medium",
            },
        ],
        "planning_warning": MOLINA_DE_ARAGON_WARNING,
    }


def _demo_analysis_molina() -> dict[str, object]:
    return {
        "verdict": "condicionado",
        "verdict_label": "CONDICIONADO",
        "confidence": "media-baja",
        "summary": (
            "La consulta demo de Molina de Aragón puede avanzar como lectura "
            "preliminar, pero la viabilidad queda condicionada a confirmar la "
            "ordenanza exacta en planos municipales y a revisar patrimonio."
        ),
        "annotations": [
            {
                "status": "warning",
                "description": (
                    "Molina de Aragón opera con Normas Subsidiarias, no con PGOU "
                    "ordinario."
                ),
                "recommendation": (
                    "Citar siempre la fuente municipal y validar la versión vigente."
                ),
            },
            {
                "status": "warning",
                "description": (
                    "Ordenanza residencial unifamiliar detectada solo como indicio textual."
                ),
                "recommendation": "Cruzar con plano de ordenación o consulta técnica.",
            },
            {
                "status": "info",
                "description": "Costas no aplica por ubicación interior en Guadalajara.",
                "recommendation": "Mantener la comprobación sectorial como trazabilidad.",
            },
        ],
        "next_steps": [
            "Abrir la documentación oficial del Ayuntamiento y confirmar versión.",
            "Cruzar la parcela real con plano o ficha de ordenación.",
            "Revisar si hay protección patrimonial o entorno histórico afectado.",
            "Emitir informe solo como preliminar hasta validación técnica municipal.",
        ],
        "full_analysis": (
            "Este demo posiciona ADV ARCHON como copiloto de consulta urbanística "
            "municipal: identifica fuente aplicable, separa dato oficial de inferencia "
            "preliminar y no inventa parámetros sin plano."
        ),
        "generated_at": datetime.now(UTC).isoformat(timespec="minutes"),
    }


__all__ = [
    "DEMO_NOTES",
    "DEMO_NOTES_MOLINA",
    "DEMO_TITLE",
    "create_demo_expediente",
    "create_molina_de_aragon_demo",
    "create_studio_demo_expedientes",
]
