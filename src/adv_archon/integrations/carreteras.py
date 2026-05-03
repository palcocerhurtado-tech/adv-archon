"""
Red viaria oficial — INSPIRE Transportes (CNIG / IDEE).

Free, official Spanish government data. No API key required.

Important:
This WFS exposes official road geometry, but it does not publish explicit legal
buffer polygons for dominio público / servidumbre / afección. Because of that,
this module performs a conservative geometric screening based on the distance
from the coordinate point to the nearest official road axis.
"""
from __future__ import annotations

import logging
import math
from typing import Any

import httpx

log = logging.getLogger(__name__)

_WFS_BASE = "https://servicios.idee.es/wfs-inspire/transportes"
_TIMEOUT = 12.0
_UA = "adv-archon-urban-compliance/1.0"
_SEARCH_RADIUS_M = 150.0

_DOMAIN_M = 8.0
_SERVITUDE_M = 25.0
_AFFECTION_M = 100.0

_LAYERS: dict[str, tuple[str, str]] = {
    "tn-ro:RoadLink": ("Eje viario oficial", "road_axis"),
    "tn-ro:RoadServiceArea": ("Área de servicio viaria", "service_area"),
}


def query_road_zone(lat: float, lon: float) -> dict[str, Any]:
    """
    Screen whether (lat, lon) is close to official road geometry.

    Returns::

        {
          "in_domain_zone": bool | None,
          "in_servitude_zone": bool | None,
          "in_affection_zone": bool | None,
          "zones": ["Posible zona de afección viaria"],
          "source": "Transportes INSPIRE / CNIG",
          "method": "cribado geométrico por proximidad a eje viario oficial",
          "nearest_distance_m": 42.7,
          "error": ""
        }
    """
    result: dict[str, Any] = {
        "in_domain_zone": False,
        "in_servitude_zone": False,
        "in_affection_zone": False,
        "zones": [],
        "source": "Transportes INSPIRE / CNIG",
        "method": "cribado geométrico por proximidad a eje viario oficial",
        "nearest_distance_m": None,
        "error": "",
    }
    matched: list[str] = []
    errors: list[str] = []
    any_success = False
    road_axis_success = False
    nearest_distance_m: float | None = None
    service_area_hit = False

    for typename, (label, kind) in _LAYERS.items():
        try:
            features = _query_layer(typename, lat=lat, lon=lon)
            any_success = True
            if kind == "road_axis":
                road_axis_success = True
                distance = _nearest_distance_to_features(features, lat=lat, lon=lon)
                if distance is not None and (
                    nearest_distance_m is None or distance < nearest_distance_m
                ):
                    nearest_distance_m = distance
            elif kind == "service_area":
                distance = _nearest_distance_to_features(features, lat=lat, lon=lon)
                if distance is not None and distance <= 1.0:
                    service_area_hit = True
                    matched.append(label)
        except Exception as exc:
            errors.append(f"{typename}: {exc}")

    if errors and not any_success:
        result["in_domain_zone"] = None
        result["in_servitude_zone"] = None
        result["in_affection_zone"] = None
        result["error"] = "; ".join(errors[:2])
        return result

    if not road_axis_success and not service_area_hit:
        result["in_domain_zone"] = None
        result["in_servitude_zone"] = None
        result["in_affection_zone"] = None
        result["error"] = "; ".join(errors[:2])
        return result

    if nearest_distance_m is not None:
        rounded = round(nearest_distance_m, 1)
        result["nearest_distance_m"] = rounded
        if nearest_distance_m <= _DOMAIN_M:
            result["in_domain_zone"] = True
            result["in_servitude_zone"] = True
            result["in_affection_zone"] = True
            matched.extend(
                [
                    "Posible zona de dominio público viario",
                    "Posible zona de servidumbre viaria",
                    "Posible zona de afección viaria",
                ]
            )
        elif nearest_distance_m <= _SERVITUDE_M:
            result["in_servitude_zone"] = True
            result["in_affection_zone"] = True
            matched.extend(
                [
                    "Posible zona de servidumbre viaria",
                    "Posible zona de afección viaria",
                ]
            )
        elif nearest_distance_m <= _AFFECTION_M:
            result["in_affection_zone"] = True
            matched.append("Posible zona de afección viaria")

    if service_area_hit:
        if "Área de servicio viaria" not in matched:
            matched.append("Área de servicio viaria")
        result["in_affection_zone"] = True

    result["zones"] = matched
    if errors:
        log.debug("Carreteras partial errors: %s", errors)
    return result


def _query_layer(typename: str, *, lat: float, lon: float) -> list[dict[str, Any]]:
    """Return nearby features from the official transport WFS."""
    bbox = _bbox_from_radius(lat=lat, lon=lon, radius_m=_SEARCH_RADIUS_M)
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": typename,
        "SRSNAME": "EPSG:4326",
        "BBOX": bbox,
        "COUNT": "25",
        "OUTPUTFORMAT": "application/json",
    }
    resp = httpx.get(
        _WFS_BASE,
        params=params,
        headers={"User-Agent": _UA, "Accept": "application/json"},
        timeout=_TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    features = data.get("features")
    return features if isinstance(features, list) else []


def _bbox_from_radius(*, lat: float, lon: float, radius_m: float) -> str:
    lat_delta = radius_m / 111_320.0
    cos_lat = max(abs(math.cos(math.radians(lat))), 0.2)
    lon_delta = radius_m / (111_320.0 * cos_lat)
    return f"{lon - lon_delta},{lat - lat_delta},{lon + lon_delta},{lat + lat_delta},EPSG:4326"


def _nearest_distance_to_features(
    features: list[dict[str, Any]],
    *,
    lat: float,
    lon: float,
) -> float | None:
    nearest: float | None = None
    for feature in features:
        geometry = feature.get("geometry")
        distance = _geometry_distance_m(geometry, lat=lat, lon=lon)
        if distance is None:
            continue
        if nearest is None or distance < nearest:
            nearest = distance
    return nearest


def _geometry_distance_m(
    geometry: dict[str, Any] | None,
    *,
    lat: float,
    lon: float,
) -> float | None:
    if not isinstance(geometry, dict):
        return None
    geo_type = str(geometry.get("type") or "")
    coords = geometry.get("coordinates")
    if geo_type == "Point":
        return _distance_to_point(coords, lat=lat, lon=lon)
    if geo_type == "MultiPoint":
        distances = [
            _distance_to_point(item, lat=lat, lon=lon)
            for item in (coords or [])
        ]
        return _min_distance(distances)
    if geo_type == "LineString":
        return _distance_to_line(coords, lat=lat, lon=lon)
    if geo_type == "MultiLineString":
        distances = [
            _distance_to_line(item, lat=lat, lon=lon)
            for item in (coords or [])
        ]
        return _min_distance(distances)
    if geo_type == "Polygon":
        return _distance_to_polygon(coords, lat=lat, lon=lon)
    if geo_type == "MultiPolygon":
        distances = [
            _distance_to_polygon(item, lat=lat, lon=lon)
            for item in (coords or [])
        ]
        return _min_distance(distances)
    return None


def _distance_to_point(coords: Any, *, lat: float, lon: float) -> float | None:
    point = _as_lon_lat(coords)
    if point is None:
        return None
    return _distance_m(lon, lat, point[0], point[1], ref_lat=lat)


def _distance_to_line(coords: Any, *, lat: float, lon: float) -> float | None:
    points = _as_positions(coords)
    if len(points) == 1:
        return _distance_m(lon, lat, points[0][0], points[0][1], ref_lat=lat)
    if len(points) < 2:
        return None
    px, py = _project(lon, lat, ref_lat=lat)
    best: float | None = None
    for start, end in zip(points, points[1:], strict=False):
        ax, ay = _project(start[0], start[1], ref_lat=lat)
        bx, by = _project(end[0], end[1], ref_lat=lat)
        distance = _point_segment_distance(px, py, ax, ay, bx, by)
        if best is None or distance < best:
            best = distance
    return best


def _distance_to_polygon(coords: Any, *, lat: float, lon: float) -> float | None:
    rings = coords if isinstance(coords, list) else []
    if not rings:
        return None
    exterior = _as_positions(rings[0])
    if len(exterior) < 3:
        return None
    if _point_in_ring(lon, lat, exterior):
        return 0.0
    distances = [_distance_to_line(ring, lat=lat, lon=lon) for ring in rings]
    return _min_distance(distances)


def _point_in_ring(lon: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_segment_distance(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _distance_m(
    lon_a: float,
    lat_a: float,
    lon_b: float,
    lat_b: float,
    *,
    ref_lat: float,
) -> float:
    ax, ay = _project(lon_a, lat_a, ref_lat=ref_lat)
    bx, by = _project(lon_b, lat_b, ref_lat=ref_lat)
    return math.hypot(ax - bx, ay - by)


def _project(lon: float, lat: float, *, ref_lat: float) -> tuple[float, float]:
    cos_lat = math.cos(math.radians(ref_lat))
    x = lon * 111_320.0 * cos_lat
    y = lat * 111_320.0
    return (x, y)


def _as_positions(coords: Any) -> list[tuple[float, float]]:
    if not isinstance(coords, list):
        return []
    positions: list[tuple[float, float]] = []
    for item in coords:
        point = _as_lon_lat(item)
        if point is not None:
            positions.append(point)
    return positions


def _as_lon_lat(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        lon = float(value[0])
        lat = float(value[1])
    except (TypeError, ValueError):
        return None
    return (lon, lat)


def _min_distance(values: list[float | None]) -> float | None:
    cleaned = [value for value in values if value is not None]
    return min(cleaned) if cleaned else None
