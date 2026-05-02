from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from adv_archon.core.geo_store import GeoStore
from adv_archon.core.site_context import LocationResolution


@dataclass(frozen=True, slots=True)
class GoogleGeocodingClient:
    api_key: str
    timeout_seconds: float = 20.0

    def reverse_geocode(
        self,
        *,
        latitude: float,
        longitude: float,
        language: str = "es",
        region: str = "es",
    ) -> LocationResolution:
        response = httpx.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "latlng": f"{latitude},{longitude}",
                "key": self.api_key,
                "language": language,
                "region": region,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        status = str(payload.get("status", "UNKNOWN_ERROR"))
        if status != "OK":
            error_message = str(payload.get("error_message", "")).strip()
            detail = f"Google Geocoding devolvió {status}"
            if error_message:
                detail = f"{detail}: {error_message}"
            raise ValueError(detail)

        results = payload.get("results", [])
        if not isinstance(results, list) or not results:
            raise ValueError("No se pudo resolver ningún municipio para esas coordenadas.")

        best = _choose_best_result(results)
        municipality = _component(best, "locality") or _component(best, "postal_town")
        province = _component(best, "administrative_area_level_2")
        region_name = _component(best, "administrative_area_level_1")
        country_code = _component(best, "country", short=True)
        formatted_address = str(best.get("formatted_address", "")).strip()

        if not municipality:
            municipality = _extract_municipality_from_results(results)
        if not municipality:
            raise ValueError("Google no devolvió un municipio claro para esas coordenadas.")

        confidence = _confidence_for_result(best)
        return GeoStore.build_resolution(
            latitude=latitude,
            longitude=longitude,
            municipality=municipality,
            province=province or "",
            region=region_name or "",
            formatted_address=formatted_address,
            country_code=country_code or "",
            provider="google_geocoding",
            confidence=confidence,
            raw_payload_json=json.dumps(payload, ensure_ascii=False),
        )


def _choose_best_result(results: list[dict[str, Any]]) -> dict[str, Any]:
    preferred_types = (
        "street_address",
        "premise",
        "route",
        "locality",
        "administrative_area_level_2",
    )
    for preferred in preferred_types:
        for result in results:
            types = result.get("types", [])
            if isinstance(types, list) and preferred in types:
                return result
    return results[0]


def _component(result: dict[str, Any], target_type: str, *, short: bool = False) -> str | None:
    raw_components = result.get("address_components", [])
    if not isinstance(raw_components, list):
        return None
    for component in raw_components:
        if not isinstance(component, dict):
            continue
        types = component.get("types", [])
        if isinstance(types, list) and target_type in types:
            key = "short_name" if short else "long_name"
            value = component.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_municipality_from_results(results: list[dict[str, Any]]) -> str | None:
    for result in results:
        municipality = _component(result, "locality") or _component(result, "postal_town")
        if municipality:
            return municipality
    return None


def _confidence_for_result(result: dict[str, Any]) -> str:
    raw_types = result.get("types", [])
    result_types = set(raw_types) if isinstance(raw_types, list) else set()
    if {"street_address", "premise"} & result_types:
        return "high"
    if {"route", "neighborhood", "sublocality", "locality"} & result_types:
        return "medium"
    return "low"
