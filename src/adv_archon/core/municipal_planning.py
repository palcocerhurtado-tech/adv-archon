"""Curated municipal planning packs used by ADV ARCHON Studio."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from adv_archon.core.pgou_store import PGOUStore

MOLINA_DE_ARAGON_ID = "molina-de-aragon"
MOLINA_DE_ARAGON_NAME = "Molina de Aragón"
MOLINA_DE_ARAGON_SOURCE_URL = "https://molinadearagon.es/ayuntamiento/urbanismo/"
MOLINA_DE_ARAGON_QUERY_DATE = "2026-10-12"


@dataclass(frozen=True, slots=True)
class MunicipalPlanningPack:
    municipio_id: str
    municipality: str
    province: str
    autonomous_community: str
    planning_type: str
    status: str
    source_url: str
    query_date: str
    version_label: str
    official_sources: tuple[str, ...]
    legal_warning: str
    indexed_text: str
    zoning: dict[str, Any]

    def catalog_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["official_sources"] = list(self.official_sources)
        return payload


MOLINA_DE_ARAGON_WARNING = (
    "Lectura preliminar basada en fuentes oficiales públicas del Ayuntamiento "
    "de Molina de Aragón y normativa autonómica. Molina de Aragón dispone de "
    "Normas Subsidiarias de Planeamiento, no de un PGOU municipal ordinario. "
    "La ordenanza exacta de una parcela requiere cruce con planos, fichas o "
    "visor municipal y validación técnica municipal antes de emitir un criterio "
    "profesional definitivo."
)


MOLINA_DE_ARAGON_INDEXED_TEXT = """
Normas Subsidiarias de Planeamiento de Molina de Aragón.
Versión de referencia municipal: documentación urbanística publicada por el
Ayuntamiento de Molina de Aragón en su sección Urbanismo. La documentación
municipal consultada identifica Normas Subsidiarias de Planeamiento, ordenanzas
urbanísticas y régimen de suelo urbano, con planos y fichas asociados.

Fuente oficial principal: Ayuntamiento de Molina de Aragón, Urbanismo:
https://molinadearagon.es/ayuntamiento/urbanismo/

Norma autonómica marco: Decreto Legislativo 1/2023, de 28 de febrero, por el que
se aprueba el texto refundido de la Ley de Ordenación del Territorio y de la
Actividad Urbanística de Castilla-La Mancha (LOTAU), publicado en el BOE.
Fuente oficial: https://www.boe.es/buscar/act.php?id=DOCM-q-2023-90054

Normativa urbanística autonómica de apoyo: portal de vivienda y urbanismo de la
Junta de Comunidades de Castilla-La Mancha.
Fuente oficial: https://vivienda.castillalamancha.es/node/397

Artículo / bloque: Ordenanzas urbanísticas.
Las Normas Subsidiarias municipales organizan el régimen del suelo urbano y las
condiciones de uso, volumen y edificación mediante ordenanzas de aplicación. La
identificación exacta de la ordenanza aplicable a una parcela no puede fijarse
solo con texto: debe cruzarse con plano de ordenación, ficha o criterio técnico
municipal.

Artículo / bloque: Régimen de suelo urbano.
La documentación municipal incluye régimen de suelo urbano y ordenanzas
urbanísticas. En el flujo de ADV ARCHON este material se usa como base textual
preliminar para detectar indicios de clasificación, calificación, uso permitido,
ocupación, altura, retranqueos y condiciones de edificación.

Artículo / bloque: Ordenanza 07 - Residencial Unifamiliar.
La documentación municipal publicada cita una ordenanza residencial unifamiliar.
ARCHON puede usarla como indicio textual para una consulta demo, pero no debe
presentarla como ordenanza jurídica exacta de una parcela sin cruce cartográfico.
Uso principal orientativo: residencial unifamiliar. Parámetros de edificabilidad,
ocupación, altura, alineaciones y retranqueos deben verificarse en la ficha y
plano municipal vigente.

Advertencia técnica.
Este paquete se marca como PRELIMINAR. Sirve para demostración comercial, lectura
inicial de planeamiento y preparación de una consulta urbanística. No sustituye
informe urbanístico municipal, certificado de compatibilidad, consulta previa ni
validación por arquitecto o técnico municipal.
"""


MOLINA_DE_ARAGON_ZONING: dict[str, Any] = {
    "municipio_id": MOLINA_DE_ARAGON_ID,
    "municipality": MOLINA_DE_ARAGON_NAME,
    "status": "preliminar",
    "classification": "Suelo urbano, según documentación municipal consultada",
    "zoning": "Ordenanza residencial unifamiliar como indicio textual",
    "ordinance": "Ordenanza 07 - Residencial Unifamiliar",
    "allowed_uses": ["residencial unifamiliar"],
    "confidence": "low",
    "requires_map_crossing": True,
    "source": MOLINA_DE_ARAGON_SOURCE_URL,
    "warning": MOLINA_DE_ARAGON_WARNING,
}


MOLINA_DE_ARAGON_PACK = MunicipalPlanningPack(
    municipio_id=MOLINA_DE_ARAGON_ID,
    municipality=MOLINA_DE_ARAGON_NAME,
    province="Guadalajara",
    autonomous_community="Castilla-La Mancha",
    planning_type="normas_subsidiarias",
    status="preliminar",
    source_url=MOLINA_DE_ARAGON_SOURCE_URL,
    query_date=MOLINA_DE_ARAGON_QUERY_DATE,
    version_label="Normas Subsidiarias de Planeamiento - documentación municipal",
    official_sources=(
        MOLINA_DE_ARAGON_SOURCE_URL,
        "https://www.boe.es/buscar/act.php?id=DOCM-q-2023-90054",
        "https://vivienda.castillalamancha.es/node/397",
    ),
    legal_warning=MOLINA_DE_ARAGON_WARNING,
    indexed_text=MOLINA_DE_ARAGON_INDEXED_TEXT,
    zoning=MOLINA_DE_ARAGON_ZONING,
)


def seed_molina_de_aragon_planning(store: PGOUStore) -> int:
    """Index the curated offline Molina de Aragón planning pack."""
    return store.index_text(
        MOLINA_DE_ARAGON_PACK.indexed_text,
        municipality=MOLINA_DE_ARAGON_PACK.municipality,
        source=MOLINA_DE_ARAGON_PACK.source_url,
        planning_type=MOLINA_DE_ARAGON_PACK.planning_type,
        status=MOLINA_DE_ARAGON_PACK.status,
        province=MOLINA_DE_ARAGON_PACK.province,
        autonomous_community=MOLINA_DE_ARAGON_PACK.autonomous_community,
        source_url=MOLINA_DE_ARAGON_PACK.source_url,
    )


def write_molina_de_aragon_catalog(data_dir: Path) -> Path:
    """Write the local demo catalogue files for Molina de Aragón."""
    root = data_dir / "pgou" / MOLINA_DE_ARAGON_ID
    ordenanzas_dir = root / "ordenanzas"
    text_dir = root / "texto_extraido"
    ordenanzas_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    catalog_path = root / "catalogo.json"
    catalog_path.write_text(
        json.dumps(MOLINA_DE_ARAGON_PACK.catalog_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (text_dir / "normas_subsidiarias_preliminar.txt").write_text(
        MOLINA_DE_ARAGON_PACK.indexed_text.strip() + "\n",
        encoding="utf-8",
    )
    (root / "zonificacion.json").write_text(
        json.dumps(MOLINA_DE_ARAGON_PACK.zoning, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (ordenanzas_dir / "README.md").write_text(
        "# Ordenanzas Molina de Aragón\n\n"
        "Este paquete demo no redistribuye PDFs municipales completos. "
        "Guarda metadatos, extractos de trabajo y enlaces oficiales para que el "
        "despacho consulte la documentación vigente desde la fuente pública.\n\n"
        f"Fuente principal: {MOLINA_DE_ARAGON_SOURCE_URL}\n",
        encoding="utf-8",
    )
    return catalog_path


def molina_de_aragon_planning_payload() -> dict[str, Any]:
    """Return a JSON-ready payload for reports, demos and site_context."""
    return {
        "municipio_id": MOLINA_DE_ARAGON_PACK.municipio_id,
        "municipality": MOLINA_DE_ARAGON_PACK.municipality,
        "province": MOLINA_DE_ARAGON_PACK.province,
        "autonomous_community": MOLINA_DE_ARAGON_PACK.autonomous_community,
        "planning_type": MOLINA_DE_ARAGON_PACK.planning_type,
        "status": MOLINA_DE_ARAGON_PACK.status,
        "source_url": MOLINA_DE_ARAGON_PACK.source_url,
        "query_date": MOLINA_DE_ARAGON_PACK.query_date,
        "version_label": MOLINA_DE_ARAGON_PACK.version_label,
        "official_sources": list(MOLINA_DE_ARAGON_PACK.official_sources),
        "legal_warning": MOLINA_DE_ARAGON_PACK.legal_warning,
    }


__all__ = [
    "MOLINA_DE_ARAGON_ID",
    "MOLINA_DE_ARAGON_NAME",
    "MOLINA_DE_ARAGON_PACK",
    "MOLINA_DE_ARAGON_QUERY_DATE",
    "MOLINA_DE_ARAGON_SOURCE_URL",
    "MOLINA_DE_ARAGON_WARNING",
    "MOLINA_DE_ARAGON_ZONING",
    "molina_de_aragon_planning_payload",
    "seed_molina_de_aragon_planning",
    "write_molina_de_aragon_catalog",
]
