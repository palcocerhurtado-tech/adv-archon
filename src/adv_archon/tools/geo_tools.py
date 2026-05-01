"""Geolocation tools: resolve coordinates → municipality → normativa aplicable."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adv_archon.core.geo_store import GeoStore
from adv_archon.core.pgou_store import PGOUStore
from adv_archon.core.site_context import SiteContext
from adv_archon.integrations import catastro as _catastro
from adv_archon.integrations import nominatim as _nominatim


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
        payload["next_step"] = (
            f"La normativa PGOU de {municipality} ya está indexada. "
            "Puedes usar plan_compliance_check directamente."
            if pgou_indexed
            else
            f"La normativa de {municipality} no está indexada todavía. "
            f"Usa pgou_fetch con municipality='{municipality}' para descargarla, "
            "y después plan_compliance_check para el análisis."
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
