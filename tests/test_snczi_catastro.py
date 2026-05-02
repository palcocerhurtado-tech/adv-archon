"""Tests for SNCZI flood zone integration and Catastro parcel detail."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from adv_archon.integrations.catastro import _parse_parcel_xml, get_parcel_by_ref
from adv_archon.integrations.snczi import _query_layer, query_flood_zone


# ── Catastro parcel detail ────────────────────────────────────────────────────


_SAMPLE_DNPRC_XML = """<?xml version="1.0" encoding="utf-8"?>
<consulta_dnprc>
  <control><cod>0</cod><des>OK</des></control>
  <bico>
    <bi>
      <idbi>
        <pc1>7537903</pc1><pc2>VK4873N0001OU</pc2>
        <ldt>CL MAYOR 3 ES:1 PT:2 28001 MADRID</ldt>
        <lmun>Madrid</lmun>
        <lprov>Madrid</lprov>
      </idbi>
      <dt>
        <luso>Residencial</luso>
        <sfc>120</sfc>
        <ant>1978</ant>
        <plt>4</plt>
        <pls>1</pls>
      </dt>
    </bi>
  </bico>
</consulta_dnprc>"""


def test_parse_parcel_xml_extracts_fields() -> None:
    base: dict[str, object] = {
        "ref": "7537903VK4873N0001OU",
        "surface_m2": None,
        "construction_year": None,
        "use_detail": "",
        "floors_above": None,
        "floors_below": None,
        "address": "",
        "municipality": "",
        "error": "",
    }
    result = _parse_parcel_xml(_SAMPLE_DNPRC_XML, base)
    assert result["surface_m2"] == 120
    assert result["construction_year"] == 1978
    assert result["use_detail"] == "Residencial"
    assert result["floors_above"] == 4
    assert result["floors_below"] == 1
    assert "MAYOR" in result["address"]
    assert result["municipality"] == "Madrid"
    assert result["error"] == ""


def test_get_parcel_by_ref_returns_error_on_empty_ref() -> None:
    result = get_parcel_by_ref("")
    assert result["error"] != ""
    assert result["surface_m2"] is None


def test_get_parcel_by_ref_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_resp = MagicMock()
    mock_resp.text = _SAMPLE_DNPRC_XML
    mock_resp.raise_for_status = MagicMock()

    with patch("adv_archon.integrations.catastro.httpx.get", return_value=mock_resp):
        result = get_parcel_by_ref("7537903VK4873N0001OU")

    assert result["surface_m2"] == 120
    assert result["construction_year"] == 1978
    assert result["error"] == ""


def test_get_parcel_by_ref_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch(
        "adv_archon.integrations.catastro.httpx.get",
        side_effect=Exception("timeout"),
    ):
        result = get_parcel_by_ref("7537903VK4873N0001OU")

    assert "timeout" in result["error"]
    assert result["surface_m2"] is None


# ── SNCZI flood zone ──────────────────────────────────────────────────────────


def _mock_wfs_response(features: list[dict]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"features": features, "numberReturned": len(features)}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def test_query_flood_zone_not_in_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch(
        "adv_archon.integrations.snczi.httpx.get",
        return_value=_mock_wfs_response([]),
    ):
        result = query_flood_zone(40.4168, -3.7038)

    assert result["in_flood_zone"] is False
    assert result["periods"] == []
    assert result["error"] == ""


def test_query_flood_zone_in_zone_t100(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = {"n": 0}

    def _side_effect(*args, **kwargs):
        call_count["n"] += 1
        # T10 → empty, T100 → hit, T500 → empty
        features = [{"id": "zone-1"}] if call_count["n"] == 2 else []
        return _mock_wfs_response(features)

    with patch("adv_archon.integrations.snczi.httpx.get", side_effect=_side_effect):
        result = query_flood_zone(37.3891, -5.9845)

    assert result["in_flood_zone"] is True
    assert "T100" in result["periods"]
    assert result["error"] == ""


def test_query_flood_zone_service_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch(
        "adv_archon.integrations.snczi.httpx.get",
        side_effect=Exception("connection refused"),
    ):
        result = query_flood_zone(40.0, -3.0)

    assert result["in_flood_zone"] is None
    assert "connection refused" in result["error"]


def test_query_flood_zone_partial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """T10 fails, T100 succeeds with no features, T500 fails — should not crash."""
    call_count = {"n": 0}

    def _side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] in (1, 3):
            raise Exception("timeout")
        return _mock_wfs_response([])

    with patch("adv_archon.integrations.snczi.httpx.get", side_effect=_side_effect):
        result = query_flood_zone(40.0, -3.0)

    # T100 returned no features so not in flood zone; errors are partial
    assert result["in_flood_zone"] is False
    assert result["error"] == ""  # partial errors logged but not surfaced
