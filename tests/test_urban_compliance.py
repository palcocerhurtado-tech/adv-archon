from pathlib import Path
from types import SimpleNamespace

from adv_archon.core.pgou_store import PGOUStore
from adv_archon.tools.urban_compliance import ToolResult, UrbanComplianceTools


class _FakeLLM:
    pass


class _FakeGeoTools:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def site_compliance_context(self, latitude: float, longitude: float) -> object:
        return SimpleNamespace(
            payload={
                **self._payload,
                "latitude": latitude,
                "longitude": longitude,
            }
        )


def test_plan_compliance_check_by_coordinates_auto_fetches_when_needed(tmp_path: Path) -> None:
    tools = UrbanComplianceTools(
        PGOUStore(tmp_path / "pgou.db"),
        _FakeLLM(),  # type: ignore[arg-type]
        geo_tools=_FakeGeoTools(
            {
                "ok": True,
                "municipality": "Madrid",
                "province": "Madrid",
                "autonomous_community": "Comunidad de Madrid",
                "display_location": "Madrid, Comunidad de Madrid",
                "cadastral_ref": "1234567VK4713S0001AB",
                "cadastral_address": "Calle Mayor 1",
                "cadastral_use": "Residencial",
                "resolution": "nominatim",
                "confidence": "high",
                "pgou_indexed": False,
                "legal_readiness": "pgou-pending",
                "legal_summary": (
                    "La parcela ya está identificada, pero falta indexar "
                    "la normativa municipal."
                ),
                "legal_checks": [
                    {
                        "code": "pgou-municipal",
                        "title": "Normativa municipal aplicable",
                        "status": "pending_review",
                        "authority": "PGOU de Madrid",
                        "detail": "Falta indexar normativa.",
                        "recommended_action": "Descargar PGOU.",
                        "confidence": "high",
                    }
                ],
                "next_step": "Usa pgou_fetch primero.",
            }
        ),
    )

    tools.pgou_fetch = lambda municipality: ToolResult(  # type: ignore[method-assign]
        name="pgou_fetch",
        payload={"ok": True, "municipality": municipality},
    )
    tools.plan_compliance_check = lambda plan_path, municipality: ToolResult(  # type: ignore[method-assign]
        name="plan_compliance_check",
        payload={
            "ok": True,
            "plan": Path(plan_path).name,
            "municipality": municipality,
            "generated_at": "2026-05-01T09:00:00+00:00",
            "summary": "Resumen OK",
            "annotations": [],
            "full_analysis": "Análisis completo",
        },
    )

    result = tools.plan_compliance_check_by_coordinates(
        "/tmp/plano.pdf",
        40.4168,
        -3.7038,
    )

    assert result.payload["ok"] is True
    assert result.payload["municipality"] == "Madrid"
    assert result.payload["pgou_auto_fetched"] is True
    assert result.payload["site_context"]["cadastral_ref"] == "1234567VK4713S0001AB"
    assert result.payload["site_context"]["legal_readiness"] == "pgou-pending"
    assert result.payload["site_context"]["legal_checks"][0]["code"] == "pgou-municipal"
