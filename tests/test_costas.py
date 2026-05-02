"""Unit tests for the SIGCOSTAS coastal-domain WFS integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from adv_archon.integrations.costas import query_coastal_zone


def _resp(features: list) -> MagicMock:
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = {"features": features, "numberReturned": len(features)}
    return m


# ── query_coastal_zone ────────────────────────────────────────────────────────


def test_no_coastal_zone() -> None:
    """All layers return empty → not in any coastal zone."""
    with patch("adv_archon.integrations.costas.httpx.get", return_value=_resp([])):
        result = query_coastal_zone(40.4168, -3.7038)

    assert result["in_dpmt"] is False
    assert result["in_protection_zone"] is False
    assert result["in_influence_zone"] is False
    assert result["zones"] == []
    assert result["error"] == ""


def test_dpmt_hit() -> None:
    """DPMT layer returns a feature → in_dpmt True."""
    def _side_effect(url, params=None, **kwargs):
        typename = (params or {}).get("TYPENAMES", "")
        return _resp([{"id": "dpmt-1"}]) if "DPMT" in typename else _resp([])

    with patch("adv_archon.integrations.costas.httpx.get", side_effect=_side_effect):
        result = query_coastal_zone(36.5, -6.3)

    assert result["in_dpmt"] is True
    assert "DPMT (dominio público)" in result["zones"]


def test_protection_zone_hit_no_dpmt() -> None:
    """Parcel is outside DPMT but inside the 100 m protection servitude."""
    def _side_effect(url, params=None, **kwargs):
        typename = (params or {}).get("TYPENAMES", "")
        if "ServidumbreProteccion" in typename:
            return _resp([{"id": "prot-1"}])
        return _resp([])

    with patch("adv_archon.integrations.costas.httpx.get", side_effect=_side_effect):
        result = query_coastal_zone(36.5, -6.3)

    assert result["in_dpmt"] is False
    assert result["in_protection_zone"] is True
    assert "Servidumbre de protección" in result["zones"]


def test_influence_zone_only() -> None:
    """Parcel is only within the 500 m zone of influence."""
    def _side_effect(url, params=None, **kwargs):
        typename = (params or {}).get("TYPENAMES", "")
        if "ZonaInfluencia" in typename:
            return _resp([{"id": "infl-1"}])
        return _resp([])

    with patch("adv_archon.integrations.costas.httpx.get", side_effect=_side_effect):
        result = query_coastal_zone(36.5, -6.3)

    assert result["in_dpmt"] is False
    assert result["in_protection_zone"] is False
    assert result["in_influence_zone"] is True
    assert "Zona de influencia 500 m" in result["zones"]


def test_all_layers_fail_returns_none() -> None:
    """When all layers raise exceptions → all zone fields are None (service unavailable)."""
    with patch(
        "adv_archon.integrations.costas.httpx.get",
        side_effect=Exception("WFS timeout"),
    ):
        result = query_coastal_zone(36.5, -6.3)

    assert result["in_dpmt"] is None
    assert result["in_protection_zone"] is None
    assert result["in_influence_zone"] is None
    assert result["error"] != ""


def test_partial_failure_uses_available_data() -> None:
    """One layer down but others succeed → returns real answer from surviving layers."""
    def _side_effect(url, params=None, **kwargs):
        typename = (params or {}).get("TYPENAMES", "")
        if "DPMT" in typename and "Servidumbre" not in typename:
            raise Exception("DPMT layer unavailable")
        return _resp([])  # protection + influence: not in zone

    with patch("adv_archon.integrations.costas.httpx.get", side_effect=_side_effect):
        result = query_coastal_zone(36.5, -6.3)

    # Should not be None — we got real answers from the other two layers
    assert result["in_protection_zone"] is False
    assert result["in_influence_zone"] is False
    # DPMT failed — its value remains False (default), not None
    assert result["in_dpmt"] is False


def test_zones_list_reflects_all_hits() -> None:
    """When multiple layers match, all labels appear in zones list."""
    with patch(
        "adv_archon.integrations.costas.httpx.get",
        return_value=_resp([{"id": "hit"}]),
    ):
        result = query_coastal_zone(36.5, -6.3)

    assert result["in_dpmt"] is True
    assert result["in_protection_zone"] is True
    assert result["in_influence_zone"] is True
    assert len(result["zones"]) == 3
