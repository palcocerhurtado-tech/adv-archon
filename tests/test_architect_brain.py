from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from adv_archon.core.architect_brain import (
    build_architect_brain_section,
    build_expediente_brain_brief,
)
from adv_archon.core.expediente import ExpedienteStore
from adv_archon.desktop.voice_commands import build_voice_system_prompt


def _load_context_builder() -> Any:
    module_path = Path(__file__).resolve().parents[1] / "personality" / "context_builder.py"
    spec = importlib.util.spec_from_file_location("personality_context_builder", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_architect_brain_contract_is_source_disciplined() -> None:
    section = build_architect_brain_section()

    assert "Architect Brain" in section
    assert "gestor de expediente" in section
    assert "dato oficial" in section
    assert "inferencia preliminar" in section
    assert "inventar normativa" in section
    assert "Requires confirmation" in section


def test_expediente_brain_brief_summarizes_active_dossier(tmp_path: Path) -> None:
    store = ExpedienteStore(tmp_path / "expedientes.db")
    expediente = store.create(
        title="Cambio de uso",
        address="Calle Mayor 24",
        municipality="Madrid",
        province="Madrid",
        latitude=40.415363,
        longitude=-3.707398,
        cadastral_ref="2807901VK4720G0001ZX",
        case_type="cambio_uso_vivienda",
    )
    site_context = {
        "cadastral_ref": "2807901VK4720G0001ZX",
        "flood_zone": {"in_flood_zone": False},
        "natura2000": {"in_protected_area": False},
        "costas": {"in_public_domain": False},
        "carreteras": {"in_affection_zone": True},
        "legal_checks": [
            {"title": "PGOU municipal", "status": "pending_review"},
            {"title": "Carreteras", "status": "conditional"},
        ],
    }
    expediente = replace(
        expediente,
        site_context=json.dumps(site_context),
        analysis_result=json.dumps(
            {
                "verdict": "condicionado",
                "summary": "Viabilidad condicionada a validar ordenanza exacta.",
            }
        ),
        quality_score=78,
        quality_result=json.dumps({"verdict": "APTO"}),
        agent_step_reviews=json.dumps({"pgou-normativa": {"status": "validated"}}),
        agent_history=json.dumps(
            [
                {
                    "title": "Autopilot de expediente",
                    "status": "in_progress",
                    "message": "Siguiente paso: validar advertencias.",
                }
            ]
        ),
    )

    brief = build_expediente_brain_brief(expediente)

    assert "Active Expediente Briefing" in brief
    assert "Cambio de uso" in brief
    assert "Madrid" in brief
    assert "2807901VK4720G0001ZX" in brief
    assert "Carreteras=affected" in brief
    assert "PGOU municipal=pending_review" in brief
    assert "78/100" in brief
    assert "validated=1" in brief


def test_personality_prompt_includes_architect_brain_with_empty_identity(
    tmp_path: Path,
) -> None:
    context_builder = _load_context_builder()
    core_identity = tmp_path / "core_identity.json"
    core_identity.write_text(
        json.dumps(
            {
                "name": "",
                "tone_baseline": "",
                "values": [],
                "hard_nos": [],
                "self_reference": "",
                "version": 1,
            }
        ),
        encoding="utf-8",
    )

    prompt = context_builder.build_system_prompt(
        "Base system",
        paths=context_builder.PersonalityPaths(
            core_identity_path=core_identity,
            state_db_path=tmp_path / "adaptive_state.sqlite",
        ),
    )

    assert prompt.startswith("Base system")
    assert "## Architect Brain" in prompt
    assert "## Agentic Studio" in prompt
    assert "gestor de expediente" in prompt


def test_voice_prompt_uses_architect_brain_contract() -> None:
    prompt = build_voice_system_prompt("Expediente activo: Madrid")

    assert "VOZ:" in prompt
    assert "DETALLE:" in prompt
    assert "## Architect Brain" in prompt
    assert "Expediente activo: Madrid" in prompt
