from pathlib import Path

from adv_archon.desktop.compliance_session import (
    ComplianceSession,
    build_coordinate_compliance_prompt,
    extract_coordinate_hint,
)


def test_extract_coordinate_hint_parses_decimal_pair() -> None:
    result = extract_coordinate_hint(
        "La parcela está en las coordenadas 40.4168, -3.7038 para el análisis."
    )

    assert result == (40.4168, -3.7038)


def test_compliance_session_can_run_with_coordinates_only() -> None:
    session = ComplianceSession()
    session.attach_pdf(Path("/tmp/plano.pdf"))
    session.set_coordinates(40.4168, -3.7038)

    assert session.can_run is True


def test_build_coordinate_compliance_prompt_mentions_coordinate_tool() -> None:
    prompt = build_coordinate_compliance_prompt(
        Path("/tmp/plano.pdf"),
        40.4168,
        -3.7038,
    )

    assert "plan_compliance_check_by_coordinates" in prompt
    assert "40.4168" in prompt
    assert "-3.7038" in prompt
