"""Geolocation tools: resolve coordinates → municipality → normativa aplicable."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adv_archon.core.geo_store import GeoStore
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.core.site_context import LegalCheck, SiteContext
from adv_archon.integrations import catastro as _catastro
from adv_archon.integrations import costas as _costas
from adv_archon.integrations import natura2000 as _natura2000
from adv_archon.integrations import nominatim as _nominatim
from adv_archon.integrations import snczi as _snczi

_COASTAL_PROVINCES = {
    "A Coruña",
    "Alacant",
    "Alicante",
    "Almería",
    "Asturias",
    "Baleares",
    "Barcelona",
    "Bizkaia",
    "Cádiz",
    "Cantabria",
    "Castelló",
    "Castellón",
    "Ceuta",
    "Gipuzkoa",
    "Girona",
    "Granada",
    "Huelva",
    "Illes Balears",
    "Las Palmas",
    "Lugo",
    "Málaga",
    "Melilla",
    "Murcia",
    "Pontevedra",
    "Santa Cruz de Tenerife",
    "Tarragona",
    "València",
    "Valencia",
}


@dataclass(slots=True)
class GeoToolResult:
    name: str
    payload: dict[str, Any]


class GeoTools:
    def __init__(self, geo_store: GeoStore, pgou_store: PGOUStore) -> None:
        self._geo = geo_store
        self._pgou = pgou_store

    # ------------------------------------------------------------------ #
    # Tool: resolve_coordinates                                            #
    # ------------------------------------------------------------------ #

    def resolve_coordinates(
        self,
        latitude: float,
        longitude: float,
        *,
        refresh: bool = False,
    ) -> GeoToolResult:
        """
        Given GPS coordinates, return the municipality, province,
        autonomous community, and cadastral reference (if available).
        Also reports whether PGOU normativa is already indexed for that municipality.
        """
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return GeoToolResult(
                name="resolve_coordinates",
                payload={"ok": False, "error": "Coordenadas fuera de rango."},
            )

        # Cache hit
        if not refresh:
            cached = self._geo.get_cached(latitude, longitude)
            if cached:
                return self._build_result(cached, from_cache=True)

        ctx = self._resolve(latitude, longitude)
        self._geo.store(ctx)
        return self._build_result(ctx, from_cache=False)

    # ------------------------------------------------------------------ #
    # Tool: site_compliance_context                                        #
    # ------------------------------------------------------------------ #

    def site_compliance_context(
        self,
        latitude: float,
        longitude: float,
    ) -> GeoToolResult:
        """
        Full site context for a compliance check:
        resolves coordinates, checks PGOU index status,
        and provides a ready-to-use summary for the architect.
        """
        geo_result = self.resolve_coordinates(latitude, longitude)
        if not geo_result.payload.get("ok"):
            return geo_result

        municipality = geo_result.payload["municipality"]
        pgou_indexed = self._pgou.get_municipality(municipality) is not None
        indexed_munis = [m.name for m in self._pgou.list_municipalities()]

        payload = {**geo_result.payload}
        payload["pgou_indexed"] = pgou_indexed
        payload["indexed_municipalities"] = indexed_munis

        # Fetch real parcel detail up-front so it's available for legal checks
        # and exposed as a structured field in the API response.
        cadastral_ref = str(payload.get("cadastral_ref") or "").strip()
        parcel_detail: dict[str, object] = {}
        if cadastral_ref:
            try:
                parcel_detail = _catastro.get_parcel_by_ref(cadastral_ref)
                if parcel_detail.get("error"):
                    parcel_detail = {}
            except Exception:
                parcel_detail = {}
        payload["parcel_detail"] = parcel_detail

        # Pre-fetch flood zone so the result is stored in payload for the API.
        flood_data: dict[str, Any] = {
            "queried": False, "in_flood_zone": None, "periods": [], "error": "skipped",
        }
        if latitude and longitude:
            try:
                raw = _snczi.query_flood_zone(latitude, longitude)
                flood_data = {
                    "queried": True,
                    "in_flood_zone": raw.get("in_flood_zone"),
                    "periods": raw.get("periods", []),
                    "source": raw.get("source", "SNCZI/CNIG"),
                    "error": raw.get("error", ""),
                }
            except Exception as exc:
                flood_data = {
                    "queried": True, "in_flood_zone": None,
                    "periods": [], "error": str(exc)[:120],
                }
        payload["flood_zone"] = flood_data

        # Pre-fetch Red Natura 2000 protected area data.
        natura_data: dict[str, Any] = {
            "queried": False, "in_protected_area": None, "zones": [], "error": "skipped",
        }
        if latitude and longitude:
            try:
                raw_n = _natura2000.query_protected_area(latitude, longitude)
                natura_data = {
                    "queried": True,
                    "in_protected_area": raw_n.get("in_protected_area"),
                    "zones": raw_n.get("zones", []),
                    "source": raw_n.get("source", "Red Natura 2000 / CNIG"),
                    "error": raw_n.get("error", ""),
                }
            except Exception as exc:
                natura_data = {
                    "queried": True, "in_protected_area": None,
                    "zones": [], "error": str(exc)[:120],
                }
        payload["natura2000"] = natura_data

        # Pre-fetch coastal zone data — only for provinces with sea frontage.
        province = str(payload.get("province") or "").strip()
        costas_data: dict[str, Any] = {
            "queried": False,
            "in_dpmt": None,
            "in_protection_zone": None,
            "in_influence_zone": None,
            "zones": [],
            "error": "skipped",
        }
        if latitude and longitude and province in _COASTAL_PROVINCES:
            try:
                raw_c = _costas.query_coastal_zone(latitude, longitude)
                costas_data = {
                    "queried": True,
                    "in_dpmt": raw_c.get("in_dpmt"),
                    "in_protection_zone": raw_c.get("in_protection_zone"),
                    "in_influence_zone": raw_c.get("in_influence_zone"),
                    "zones": raw_c.get("zones", []),
                    "source": raw_c.get("source", "SIGCOSTAS / MITECO"),
                    "error": raw_c.get("error", ""),
                }
            except Exception as exc:
                costas_data = {
                    "queried": True,
                    "in_dpmt": None,
                    "in_protection_zone": None,
                    "in_influence_zone": None,
                    "zones": [],
                    "error": str(exc)[:120],
                }
        payload["costas"] = costas_data

        legal_checks = self._build_legal_checks(
            payload,
            pgou_indexed=pgou_indexed,
            latitude=latitude,
            longitude=longitude,
            _parcel_detail=parcel_detail,
            _flood_data=flood_data,
            _natura_data=natura_data,
            _costas_data=costas_data,
        )
        payload["legal_checks"] = [check.to_dict() for check in legal_checks]
        payload["legal_readiness"] = self._legal_readiness(payload, pgou_indexed=pgou_indexed)
        payload["legal_summary"] = self._legal_summary(payload, pgou_indexed=pgou_indexed)
        payload["next_step"] = (
            f"La normativa PGOU de {municipality} ya está indexada. "
            "Puedes usar plan_compliance_check directamente, pero conviene revisar también "
            "las afecciones sectoriales y la ordenanza concreta de parcela."
            if pgou_indexed
            else
            f"La normativa de {municipality} no está indexada todavía. "
            f"Usa pgou_fetch con municipality='{municipality}' para descargarla, "
            "y después plan_compliance_check para el análisis y la revisión jurídica preliminar."
        )
        return GeoToolResult(name="site_compliance_context", payload=payload)

    # ------------------------------------------------------------------ #
    # Private                                                              #
    # ------------------------------------------------------------------ #

    def _resolve(self, lat: float, lon: float) -> SiteContext:
        reasons: list[str] = []

        # Step 1: Nominatim
        nominatim_data = _nominatim.reverse_geocode(lat, lon)
        municipality, province, autonomous_community = _nominatim.extract_municipality(
            nominatim_data
        )

        if municipality:
            reasons.append(f"Municipio resuelto por Nominatim: {municipality}")
            resolution = "nominatim"
            confidence: str = "high"
        else:
            reasons.append("Nominatim no devolvió municipio")
            resolution = "unknown"
            confidence = "low"

        # Step 2: Catastro (cadastral reference + possible municipality cross-check)
        catastro_data = _catastro.get_cadastral_data(lat, lon)
        cadastral_ref = catastro_data.get("cadastral_ref", "")
        cadastral_address = catastro_data.get("address", "")
        cadastral_use = catastro_data.get("use", "")

        if catastro_data.get("error"):
            reasons.append(f"Catastro: {catastro_data['error']}")
        elif cadastral_ref:
            reasons.append(f"Referencia catastral obtenida: {cadastral_ref}")
            confidence = "high"
            # If Nominatim failed, use Catastro municipality
            if not municipality and catastro_data.get("catastro_municipality"):
                municipality = catastro_data["catastro_municipality"]
                province = catastro_data.get("catastro_province", province)
                resolution = "catastro"
                reasons.append(f"Municipio resuelto por Catastro: {municipality}")

        return SiteContext(
            latitude=lat,
            longitude=lon,
            municipality=municipality,
            province=province,
            autonomous_community=autonomous_community,
            cadastral_ref=cadastral_ref,
            cadastral_address=cadastral_address,
            cadastral_use=cadastral_use,
            resolution=resolution,  # type: ignore[arg-type]
            confidence=confidence,  # type: ignore[arg-type]
            reasons=reasons,
            raw_nominatim=nominatim_data,
            raw_catastro=catastro_data.get("raw_xml", ""),
        )

    def _build_result(self, ctx: SiteContext, *, from_cache: bool) -> GeoToolResult:
        payload = ctx.to_dict()
        payload["ok"] = bool(ctx.municipality)
        payload["from_cache"] = from_cache
        if not ctx.municipality:
            payload["error"] = (
                "No se pudo resolver el municipio para estas coordenadas. "
                "Comprueba que las coordenadas son de España y están en formato decimal (lat, lon)."
            )
        return GeoToolResult(name="resolve_coordinates", payload=payload)

    def _build_legal_checks(
        self,
        payload: dict[str, Any],
        *,
        pgou_indexed: bool,
        latitude: float = 0.0,
        longitude: float = 0.0,
        _parcel_detail: dict[str, Any] | None = None,
        _flood_data: dict[str, Any] | None = None,
        _natura_data: dict[str, Any] | None = None,
        _costas_data: dict[str, Any] | None = None,
    ) -> list[LegalCheck]:
        municipality = str(payload.get("municipality") or "").strip()
        province = str(payload.get("province") or "").strip()
        cadastral_ref = str(payload.get("cadastral_ref") or "").strip()
        cadastral_use = str(payload.get("cadastral_use") or "").strip()

        # Use pre-fetched data — avoids duplicate HTTP calls.
        parcel_detail: dict[str, Any] = _parcel_detail or {}
        flood_data: dict[str, Any] = _flood_data or {
            "in_flood_zone": None, "periods": [], "error": "skipped",
        }
        natura_data: dict[str, Any] = _natura_data or {
            "in_protected_area": None, "zones": [], "error": "skipped",
        }
        costas_data: dict[str, Any] = _costas_data or {
            "in_dpmt": None, "in_protection_zone": None,
            "in_influence_zone": None, "zones": [], "error": "skipped",
        }

        # Build cadastral detail text from real parcel data
        _pd_parts: list[str] = []
        if parcel_detail and not parcel_detail.get("error"):
            if parcel_detail.get("surface_m2"):
                _pd_parts.append(f"Superficie construida: {parcel_detail['surface_m2']} m²")
            if parcel_detail.get("construction_year"):
                _pd_parts.append(f"Año construcción: {parcel_detail['construction_year']}")
            if parcel_detail.get("use_detail"):
                _pd_parts.append(f"Uso: {parcel_detail['use_detail']}")
            if parcel_detail.get("floors_above") is not None:
                _pd_parts.append(f"Plantas sobre rasante: {parcel_detail['floors_above']}")
        _cadastral_detail_extra = " | ".join(_pd_parts) if _pd_parts else ""

        # Build flood zone text from real SNCZI data
        _flood_status: str
        _flood_detail: str
        _flood_action: str
        _flood_conf: str
        if flood_data.get("error") == "skipped" or flood_data.get("in_flood_zone") is None:
            _flood_status = "pending_review"
            _flood_detail = (
                "No se ha podido consultar el SNCZI en este momento. "
                f"{flood_data.get('error', '')}"
            ).strip()
            _flood_action = "Revisar manualmente la cartografía del SNCZI (MITECO)."
            _flood_conf = "medium"
        elif flood_data["in_flood_zone"]:
            periods = ", ".join(flood_data.get("periods", []))
            _flood_status = "conditional"
            _flood_detail = (
                f"⚠️ La parcela INTERSECTA con zonas inundables SNCZI "
                f"(períodos de retorno: {periods or 'detectado'}). "
                "Fuente: MITECO/CNIG — datos oficiales."
            )
            _flood_action = (
                "Consultar con la Confederación Hidrográfica correspondiente. "
                "Puede haber restricciones de uso del suelo y condicionantes estructurales."
            )
            _flood_conf = "high"
        else:
            _flood_status = "ready"
            _flood_detail = (
                "La parcela NO aparece en zonas inundables SNCZI "
                "(T10, T100 y T500 consultados). "
                "Fuente: MITECO/CNIG — datos oficiales."
            )
            _flood_action = "Sin afección hidráulica detectada. Verificar en el PGOU local."
            _flood_conf = "high"

        # Build natura2000 / heritage status from real CNIG data
        _natura_status: str
        _natura_detail: str
        _natura_action: str
        _natura_conf: str
        in_natura = natura_data.get("in_protected_area")
        if natura_data.get("error") == "skipped" or in_natura is None:
            _natura_status = "pending_review"
            _natura_detail = (
                "No se ha podido consultar la Red Natura 2000 en este momento. "
                f"{natura_data.get('error', '')}"
            ).strip()
            _natura_action = (
                "Revisar manualmente el visor de Red Natura 2000 (MITECO) "
                "y catálogos de patrimonio de la comunidad autónoma."
            )
            _natura_conf = "medium"
        elif in_natura:
            zones = ", ".join(natura_data.get("zones") or [])
            _natura_status = "conditional"
            _natura_detail = (
                f"⚠️ La parcela INTERSECTA con espacios Red Natura 2000 "
                f"({zones or 'zona protegida detectada'}). "
                "Fuente: CNIG/MITECO — datos oficiales."
            )
            _natura_action = (
                "Obligatorio realizar Evaluación de Impacto Ambiental (EIA) "
                "o Evaluación de Repercusiones Ambientales antes de cualquier actuación."
            )
            _natura_conf = "high"
        else:
            _natura_status = "ready"
            _natura_detail = (
                "La parcela NO se encuentra dentro de espacios Red Natura 2000 "
                "(ZEC y ZEPA consultados). "
                "Fuente: CNIG/MITECO — datos oficiales."
            )
            _natura_action = (
                "Sin afección directa de Red Natura 2000. "
                "Verificar catálogos de patrimonio y espacios protegidos autonómicos."
            )
            _natura_conf = "high"

        # Build coastal domain status from real SIGCOSTAS data
        _costas_status: str
        _costas_detail: str
        _costas_action: str
        _costas_conf: str
        _costas_queried = costas_data.get("queried", False)
        _in_dpmt = costas_data.get("in_dpmt")
        _in_prot = costas_data.get("in_protection_zone")
        _in_infl = costas_data.get("in_influence_zone")

        if not _costas_queried:
            # Non-coastal province — check is not applicable
            _costas_status = "not_applicable"
            _costas_detail = (
                f"La provincia de {province} no tiene fachada litoral. "
                "No aplica la Ley de Costas."
            )
            _costas_action = "Sin afección de costas."
            _costas_conf = "high"
        elif costas_data.get("error") == "skipped" or (
            _in_dpmt is None and _in_prot is None and _in_infl is None
        ):
            _costas_status = "pending_review"
            _costas_detail = (
                f"La provincia de {province} tiene fachada litoral, pero no se ha podido "
                "consultar el SIGCOSTAS en este momento. "
                f"{costas_data.get('error', '')}"
            ).strip()
            _costas_action = (
                "Verificar manualmente en SIGCOSTAS (MITECO) si la parcela se encuentra "
                "en DPMT, servidumbre de protección (100 m) o zona de influencia (500 m)."
            )
            _costas_conf = "medium"
        elif _in_dpmt:
            _costas_status = "conditional"
            _costas_detail = (
                "⚠️ La parcela SE ENCUENTRA en el Dominio Público Marítimo-Terrestre (DPMT). "
                "Fuente: SIGCOSTAS/MITECO — datos oficiales. "
                "La edificación está absolutamente prohibida salvo concesión del Estado."
            )
            _costas_action = (
                "Consultar con la Demarcación de Costas correspondiente. "
                "Se requiere autorización o concesión de la Dirección General de la Costa y el Mar."
            )
            _costas_conf = "high"
        elif _in_prot:
            zones = ", ".join(costas_data.get("zones") or [])
            _costas_status = "conditional"
            _costas_detail = (
                f"⚠️ La parcela está en la SERVIDUMBRE DE PROTECCIÓN de costas "
                f"({zones or '100 m desde la ribera del mar'}). "
                "Fuente: SIGCOSTAS/MITECO — datos oficiales. "
                "Aplican restricciones significativas de edificabilidad (Ley 22/1988)."
            )
            _costas_action = (
                "Comprobar los usos permitidos en la zona de servidumbre de protección. "
                "Se requiere informe previo de la Demarcación de Costas para cualquier actuación."
            )
            _costas_conf = "high"
        elif _in_infl:
            _costas_status = "conditional"
            _costas_detail = (
                "⚠️ La parcela está en la ZONA DE INFLUENCIA de costas (500 m). "
                "Fuente: SIGCOSTAS/MITECO — datos oficiales. "
                "El planeamiento municipal debe respetar las exigencias de protección del litoral."
            )
            _costas_action = (
                "Verificar que el PGOU cumple con los criterios de ordenación del litoral. "
                "Consultar con la Demarcación de Costas si la actuación requiere informe."
            )
            _costas_conf = "high"
        else:
            _costas_status = "ready"
            _costas_detail = (
                "La parcela NO se encuentra en DPMT, servidumbre de protección "
                "ni zona de influencia de costas (SIGCOSTAS/MITECO — datos oficiales)."
            )
            _costas_action = "Sin afección de Ley de Costas detectada."
            _costas_conf = "high"

        checks: list[LegalCheck] = [
            LegalCheck(
                code="cadastral-identification",
                title="Identificación catastral",
                status="ready" if cadastral_ref else "missing",
                authority="Catastro OVC",
                detail=(
                    (
                        f"Referencia catastral: {cadastral_ref}."
                        + (f" {_cadastral_detail_extra}" if _cadastral_detail_extra else "")
                    )
                    if cadastral_ref
                    else "No se ha podido obtener una referencia catastral con estas coordenadas."
                ),
                recommended_action=(
                    "Usar esta referencia como base para el expediente y los cruces posteriores."
                    if cadastral_ref
                    else (
                        "Confirmar la parcela o la referencia catastral antes "
                        "del análisis jurídico detallado."
                    )
                ),
                confidence="high" if cadastral_ref else "medium",
            ),
            LegalCheck(
                code="pgou-municipal",
                title="Normativa municipal aplicable",
                status="ready" if pgou_indexed else "pending_review",
                authority=f"PGOU / normas urbanísticas de {municipality or 'municipio'}",
                detail=(
                    f"El PGOU de {municipality} ya está indexado para el análisis."
                    if pgou_indexed
                    else (
                        f"El PGOU de {municipality or 'este municipio'} "
                        "todavía no está indexado en ARCHON."
                    )
                ),
                recommended_action=(
                    "Lanzar el análisis del plano y contrastarlo con los artículos aplicables."
                    if pgou_indexed
                    else (
                        "Descargar o indexar primero la normativa municipal "
                        "antes de emitir criterio urbanístico."
                    )
                ),
                confidence="high",
            ),
            LegalCheck(
                code="parcel-zoning",
                title="Ordenanza y zona de parcela",
                status="pending_review",
                authority="Planeamiento municipal",
                detail=(
                    "La parcela ya está localizada, pero todavía no se ha identificado "
                    "de forma automática "
                    "la clasificación, calificación, ordenanza ni parámetros "
                    "edificatorios concretos."
                ),
                recommended_action=(
                    "Cruzar la parcela con los planos y fichas del PGOU para "
                    "confirmar uso, edificabilidad, "
                    "ocupación, altura, retranqueos y ordenanza."
                ),
                confidence="medium",
            ),
            LegalCheck(
                code="hydraulic-domain",
                title="Cauces, inundabilidad y dominio público hidráulico",
                status=_flood_status,  # type: ignore[arg-type]
                authority="SNCZI — MITECO / CNIG (datos oficiales)",
                detail=_flood_detail,
                recommended_action=_flood_action,
                confidence=_flood_conf,  # type: ignore[arg-type]
            ),
            LegalCheck(
                code="roads-servitudes",
                title="Carreteras y servidumbres",
                status="pending_review",
                authority="Ministerio / comunidad autónoma / red local",
                detail=(
                    "No se ha comprobado si existen afecciones por carreteras, "
                    "alineaciones, expropiaciones "
                    "o servidumbres de infraestructuras."
                ),
                recommended_action=(
                    "Contrastar la parcela con redes viarias y servidumbres "
                    "sectoriales antes del informe final."
                ),
                confidence="medium",
            ),
            LegalCheck(
                code="heritage-environment",
                title="Patrimonio y protección ambiental (Red Natura 2000)",
                status=_natura_status,  # type: ignore[arg-type]
                authority="Red Natura 2000 — CNIG/MITECO (datos oficiales)",
                detail=_natura_detail,
                recommended_action=_natura_action,
                confidence=_natura_conf,  # type: ignore[arg-type]
            ),
            LegalCheck(
                code="coastal-domain",
                title="Costas y servidumbre marítimo-terrestre (Ley 22/1988)",
                status=_costas_status,  # type: ignore[arg-type]
                authority="SIGCOSTAS — Demarcación de Costas / MITECO (datos oficiales)",
                detail=_costas_detail,
                recommended_action=_costas_action,
                confidence=_costas_conf,  # type: ignore[arg-type]
            ),
        ]

        if cadastral_use:
            checks.append(
                LegalCheck(
                    code="cadastral-use",
                    title="Uso catastral detectado",
                    status="ready",
                    authority="Catastro OVC",
                    detail=f"Catastro devuelve como uso principal: {cadastral_use}.",
                    recommended_action=(
                        "Comprobar que el uso catastral es coherente con el uso "
                        "urbanístico permitido por el PGOU."
                    ),
                    confidence="high",
                )
            )

        return checks

    def _legal_readiness(self, payload: dict[str, Any], *, pgou_indexed: bool) -> str:
        has_cadastral_ref = bool(str(payload.get("cadastral_ref") or "").strip())
        if has_cadastral_ref and pgou_indexed:
            return "preliminary-ready"
        if has_cadastral_ref and not pgou_indexed:
            return "pgou-pending"
        if not has_cadastral_ref and pgou_indexed:
            return "parcel-pending"
        return "early-stage"

    def _legal_summary(self, payload: dict[str, Any], *, pgou_indexed: bool) -> str:
        municipality = str(payload.get("municipality") or "el municipio").strip()
        cadastral_ref = str(payload.get("cadastral_ref") or "").strip()

        if cadastral_ref and pgou_indexed:
            return (
                f"Ya hay base suficiente para un análisis preliminar en {municipality}: "
                "la parcela está identificada y la normativa municipal está disponible. "
                "Aun así, faltan comprobaciones de ordenanza concreta y de afecciones sectoriales "
                "antes de considerar jurídicamente viable cualquier actuación."
            )
        if cadastral_ref and not pgou_indexed:
            return (
                f"La parcela ya está identificada en {municipality}, pero falta indexar o revisar "
                "la normativa municipal antes de emitir un criterio urbanístico fiable. "
                "Las afecciones sectoriales también siguen pendientes."
            )
        if not cadastral_ref and pgou_indexed:
            return (
                f"El marco municipal de {municipality} está disponible, pero todavía falta fijar "
                "con seguridad la parcela concreta. Sin esa identificación, el análisis jurídico "
                "solo puede considerarse orientativo."
            )
        return (
            f"El emplazamiento se ha localizado en {municipality}, pero todavía falta consolidar "
            "los dos prerrequisitos clave: la identificación catastral y la normativa municipal "
            "operativa. Cualquier conclusión debe tomarse como preliminar."
        )
