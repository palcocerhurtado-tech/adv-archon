"""Unit tests for the Red Natura 2000 INSPIRE WFS integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from adv_archon.integrations.natura2000 import query_protected_area


def _resp(features: list) -> MagicMock:
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = {"features": features, "numberReturned": len(features)}
    return m


def _err(msg: str = "connection refused"):
    raise Exception(msg)


# ── query_protected_area ──────────────────────────────────────────────────────


def test_no_protected_area() -> None:
    """Both layers return empty → in_protected_area is False."""
    with patch("adv_archon.integrations.natura2000.httpx.get", return_value=_resp([])):
        result = query_protected_area(40.4168, -3.7038)

    assert result["in_protected_area"] is False
    assert result["zones"] == []
    assert result["error"] == ""


def test_zec_hit() -> None:
    """ZEC layer returns a feature → in_protected_area True, zone label present."""
    call_count = 0

    def _side_effect(url, params=None, **kwargs):
        nonlocal call_count
        call_count += 1
        typename = (params or {}).get("TYPENAMES", "")
        # First call → ZEC hit; second → ZEPA miss
        return _resp([{"id": "zec-1"}]) if "ZEC" in typename else _resp([])

    with patch("adv_archon.integrations.natura2000.httpx.get", side_effect=_side_effect):
        result = query_protected_area(40.4168, -3.7038)

    assert result["in_protected_area"] is True
    assert "ZEC (hábitats)" in result["zones"]


def test_zepa_hit() -> None:
    """Only ZEPA layer returns a feature."""
    def _side_effect(url, params=None, **kwargs):
        typename = (params or {}).get("TYPENAMES", "")
        return _resp([{"id": "zepa-1"}]) if "ZEPA" in typename else _resp([])

    with patch("adv_archon.integrations.natura2000.httpx.get", side_effect=_side_effect):
        result = query_protected_area(40.4168, -3.7038)

    assert result["in_protected_area"] is True
    assert "ZEPA (aves)" in result["zones"]


def test_both_layers_hit() -> None:
    """Both ZEC and ZEPA return features → two zones in list."""
    with patch(
        "adv_archon.integrations.natura2000.httpx.get",
        return_value=_resp([{"id": "hit"}]),
    ):
        result = query_protected_area(40.4168, -3.7038)

    assert result["in_protected_area"] is True
    assert len(result["zones"]) == 2


def test_all_layers_fail_returns_none() -> None:
    """When all layers raise exceptions → in_protected_area is None, not False."""
    with patch(
        "adv_archon.integrations.natura2000.httpx.get",
        side_effect=Exception("WFS timeout"),
    ):
        result = query_protected_area(40.4168, -3.7038)

    assert result["in_protected_area"] is None
    assert result["error"] != ""


def test_partial_failure_uses_available_data() -> None:
    """One layer fails but the other succeeds → still returns real answer."""
    call_count = 0

    def _side_effect(url, params=None, **kwargs):
        nonlocal call_count
        call_count += 1
        typename = (params or {}).get("TYPENAMES", "")
        if "ZEC" in typename:
            raise Exception("ZEC layer down")
        return _resp([])  # ZEPA returns empty → not in protected area

    with patch("adv_archon.integrations.natura2000.httpx.get", side_effect=_side_effect):
        result = query_protected_area(40.4168, -3.7038)

    # Should not be None — we got a real answer from ZEPA
    assert result["in_protected_area"] is False
    assert result["zones"] == []
