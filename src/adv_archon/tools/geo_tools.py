"""Geolocation tools: resolve coordinates → municipality → normativa aplicable."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adv_archon.core.geo_store import GeoStore
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.core.site_context import LegalCheck, SiteContext
from adv_archon.integrations import catastro as _catastro
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
        legal_checks = self._build_legal_checks(
            payload,
            pgou_indexed=pgou_indexed,
            latitude=latitude,
            longitude=longitude,
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
    ) -> list[LegalCheck]:
        municipality = str(payload.get("municipality") or "").strip()
        province = str(payload.get("province") or "").strip()
        cadastral_ref = str(payload.get("cadastral_ref") or "").strip()
        cadastral_use = str(payload.get("cadastral_use") or "").strip()

        # ── Real data fetches (best-effort, degrade gracefully) ──────────────
        parcel_detail: dict[str, Any] = {}
        if cadastral_ref:
            try:
                parcel_detail = _catastro.get_parcel_by_ref(cadastral_ref)
            except Exception:
                parcel_detail = {}

        flood_data: dict[str, Any] = {"in_flood_zone": None, "periods": [], "error": "skipped"}
        if latitude and longitude:
            try:
                flood_data = _snczi.query_flood_zone(latitude, longitude)
            except Exception as exc:
                flood_data = {"in_flood_zone": None, "periods": [], "error": str(exc)[:120]}

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
                title="Patrimonio y protección ambiental",
                status="pending_review",
                authority="Comunidad autónoma / ayuntamiento",
                detail=(
                    "Falta revisar si el emplazamiento está dentro de un ámbito "
                    "protegido, entorno BIC, "
                    "catálogo patrimonial o espacio ambiental condicionado."
                ),
                recommended_action=(
                    "Consultar catálogos patrimoniales y ambientales del municipio "
                    "o de la comunidad autónoma."
                ),
                confidence="medium",
            ),
        ]

        if province in _COASTAL_PROVINCES:
            checks.append(
                LegalCheck(
                    code="coastal-domain",
                    title="Costas y servidumbre marítimo-terrestre",
                    status="conditional",
                    authority="Demarcación de Costas",
                    detail=(
                        f"La provincia de {province} tiene fachada litoral. Puede haber afecciones "
                        "de costas si la parcela se encuentra en franja litoral."
                    ),
                    recommended_action=(
                        "Verificar si la parcela entra en dominio público marítimo-terrestre "
                        "o en sus servidumbres."
                    ),
                    confidence="medium",
                )
            )

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
