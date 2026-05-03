"""Unit tests for the official INSPIRE/CNIG road-geometry screening."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from adv_archon.integrations.carreteras import query_road_zone


def _resp(features: list[dict]) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"features": features, "numberReturned": len(features)}
    return response


def test_no_nearby_road_geometry() -> None:
    """Empty road and service-area layers return a clean negative screening."""
    with patch("adv_archon.integrations.carreteras.httpx.get", return_value=_resp([])):
        result = query_road_zone(40.0, -3.0)

    assert result["in_domain_zone"] is False
    assert result["in_servitude_zone"] is False
    assert result["in_affection_zone"] is False
    assert result["nearest_distance_m"] is None
    assert result["zones"] == []
    assert result["error"] == ""


def test_road_axis_domain_screening_hit() -> None:
    """A point on the official road axis marks all proximity bands as possible."""
    road = {
        "geometry": {
            "type": "LineString",
            "coordinates": [[-3.001, 40.0], [-2.999, 40.0]],
        }
    }

    def _side_effect(url, params=None, **kwargs):
        typename = (params or {}).get("TYPENAMES", "")
        return _resp([road]) if typename == "tn-ro:RoadLink" else _resp([])

    with patch("adv_archon.integrations.carreteras.httpx.get", side_effect=_side_effect):
        result = query_road_zone(40.0, -3.0)

    assert result["in_domain_zone"] is True
    assert result["in_servitude_zone"] is True
    assert result["in_affection_zone"] is True
    assert result["nearest_distance_m"] == 0.0
    assert "Posible zona de dominio público viario" in result["zones"]


def test_road_axis_affection_only_hit() -> None:
    """A road around 50 m away only marks the broader affection screening band."""
    road = {
        "geometry": {
            "type": "LineString",
            "coordinates": [[-2.9994, 39.999], [-2.9994, 40.001]],
        }
    }

    def _side_effect(url, params=None, **kwargs):
        typename = (params or {}).get("TYPENAMES", "")
        return _resp([road]) if typename == "tn-ro:RoadLink" else _resp([])

    with patch("adv_archon.integrations.carreteras.httpx.get", side_effect=_side_effect):
        result = query_road_zone(40.0, -3.0)

    assert result["in_domain_zone"] is False
    assert result["in_servitude_zone"] is False
    assert result["in_affection_zone"] is True
    assert 45 <= result["nearest_distance_m"] <= 55
    assert result["zones"] == ["Posible zona de afección viaria"]


def test_service_area_geometry_marks_condition() -> None:
    """A containing RoadServiceArea polygon is exposed as a road-related hit."""
    area = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-3.001, 39.999],
                    [-2.999, 39.999],
                    [-2.999, 40.001],
                    [-3.001, 40.001],
                    [-3.001, 39.999],
                ]
            ],
        }
    }

    def _side_effect(url, params=None, **kwargs):
        typename = (params or {}).get("TYPENAMES", "")
        return _resp([area]) if typename == "tn-ro:RoadServiceArea" else _resp([])

    with patch("adv_archon.integrations.carreteras.httpx.get", side_effect=_side_effect):
        result = query_road_zone(40.0, -3.0)

    assert result["in_domain_zone"] is False
    assert result["in_servitude_zone"] is False
    assert result["in_affection_zone"] is True
    assert "Área de servicio viaria" in result["zones"]


def test_all_layers_fail_returns_unavailable() -> None:
    """If the official WFS is down, status fields are unknown rather than false."""
    with patch(
        "adv_archon.integrations.carreteras.httpx.get",
        side_effect=Exception("WFS timeout"),
    ):
        result = query_road_zone(40.0, -3.0)

    assert result["in_domain_zone"] is None
    assert result["in_servitude_zone"] is None
    assert result["in_affection_zone"] is None
    assert "WFS timeout" in result["error"]


def test_road_axis_failure_is_not_reported_as_clear() -> None:
    """A failed RoadLink layer cannot be treated as absence of road servitudes."""
    def _side_effect(url, params=None, **kwargs):
        typename = (params or {}).get("TYPENAMES", "")
        if typename == "tn-ro:RoadLink":
            raise Exception("RoadLink layer down")
        return _resp([])

    with patch("adv_archon.integrations.carreteras.httpx.get", side_effect=_side_effect):
        result = query_road_zone(40.0, -3.0)

    assert result["in_domain_zone"] is None
    assert result["in_servitude_zone"] is None
    assert result["in_affection_zone"] is None
    assert "RoadLink layer down" in result["error"]
