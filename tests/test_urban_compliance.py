from pathlib import Path
from types import SimpleNamespace

from adv_archon.core.pgou_store import PGOUStore
from adv_archon.tools.urban_compliance import (
    ToolResult,
    UrbanComplianceTools,
    _dynamic_num_ctx,
    _format_site_context,
    _static_context_hash,
)


class _FakeLLM:
    pass


class _FakeConfigLLM:
    def __init__(self, *, auto: bool = True) -> None:
        self._config = SimpleNamespace(
            ollama_num_ctx=4096,
            ollama_num_ctx_min=2048,
            ollama_num_ctx_max=8192,
            ollama_num_ctx_auto=auto,
        )


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
    tools.plan_compliance_check = lambda plan_path, municipality, **_kw: ToolResult(  # type: ignore[method-assign]
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


def test_format_site_context_includes_preliminary_parcel_zoning() -> None:
    text = _format_site_context(
        {
            "parcel_zoning": {
                "queried": True,
                "available": True,
                "classification": "Suelo urbano consolidado",
                "zoning": "Residencial colectiva",
                "ordinance": "Z-1 Residencial",
                "allowed_uses": ["residencial", "dotacional"],
                "buildability": "1,50 m2/m2",
                "occupancy": "60%",
                "height": "10 m",
                "setbacks": "según alineación oficial",
            }
        }
    )

    assert "Zonificación PGOU preliminar" in text
    assert "Z-1 Residencial" in text
    assert "Requiere confirmar en planos/visor municipal" in text


def test_static_context_hash_is_stable_and_content_sensitive() -> None:
    first = _static_context_hash(pgou_chunks_text="PGOU Madrid", site_context_text="Catastro A")
    second = _static_context_hash(pgou_chunks_text="PGOU Madrid", site_context_text="Catastro A")
    changed = _static_context_hash(pgou_chunks_text="PGOU Zaragoza", site_context_text="Catastro A")

    assert first == second
    assert first != changed
    assert len(first) == 16


def test_dynamic_num_ctx_scales_with_requested_tokens() -> None:
    llm = _FakeConfigLLM()

    assert _dynamic_num_ctx(llm, requested_input_tokens=500) == 2048  # type: ignore[arg-type]
    assert _dynamic_num_ctx(llm, requested_input_tokens=2000) == 4096  # type: ignore[arg-type]
    assert _dynamic_num_ctx(llm, requested_input_tokens=4000) == 8192  # type: ignore[arg-type]


def test_dynamic_num_ctx_respects_auto_disabled() -> None:
    llm = _FakeConfigLLM(auto=False)

    assert _dynamic_num_ctx(llm, requested_input_tokens=4000) == 4096  # type: ignore[arg-type]
