from adv_archon.core.meeting_prep import MeetingPrepBrief, build_meeting_prep_brief


def test_build_meeting_prep_brief_prioritizes_matching_sources() -> None:
    brief = build_meeting_prep_brief(
        meeting_title="Seguimiento ACME pricing",
        meeting_when="2026-05-03T10:00:00",
        project_name="Cuenta ACME",
        calendar_events=[
            {
                "title": "Sync interno",
                "start": "2026-05-03T09:00:00",
            },
            {
                "summary": "Seguimiento ACME pricing",
                "start": "2026-05-03T10:00:00",
                "description": "Revisar pricing final, descuento pendiente y decision comercial.",
                "attendees": ["Marta", "cliente@acme.com"],
                "location": "Google Meet",
            },
        ],
        gmail_messages=[
            {
                "subject": "ACME necesita respuesta hoy",
                "from": "cliente@acme.com",
                "snippet": (
                    "Seguimos bloqueados por pricing "
                    "y necesitamos una respuesta urgente hoy."
                ),
                "received_at": "2026-05-02T18:00:00",
            }
        ],
        drive_files=[
            {
                "name": "Propuesta ACME v3",
                "owner": "Pablo",
                "summary": "Version final con pricing actualizado.",
                "modified_time": "2026-05-02T20:00:00",
            }
        ],
        notes=[
            {
                "title": "Call prep ACME",
                "body": "Legal aun no aprueba el descuento. Decision pendiente.",
                "path": "notes/acme.md",
            }
        ],
        knowledge_hits=[
            {
                "title": "Decision log ACME",
                "snippet": "El cliente prioriza cerrar pricing esta semana.",
                "path": "docs/acme-pricing.md",
                "score": 0.93,
            }
        ],
    )

    assert brief.meeting_title == "Seguimiento ACME pricing"
    assert brief.meeting_when == "2026-05-03T10:00:00"
    assert any("pricing" in item.lower() for item in brief.summary)
    assert any(
        "respuesta" in item.lower() or "urgente" in item.lower() for item in brief.priorities
    )
    assert any("Propuesta ACME v3" in item for item in brief.priorities)
    assert any("Marta" in item for item in brief.context)
    assert brief.sources["gmail"][0]["subject"] == "ACME necesita respuesta hoy"
    assert brief.sources["knowledge"][0]["path"] == "docs/acme-pricing.md"


def test_build_meeting_prep_brief_surfaces_risks_and_questions_when_context_is_thin() -> None:
    brief = build_meeting_prep_brief(
        meeting_title="Sync cliente Beta",
        meeting_when="2026-06-01T12:00:00",
        calendar_events=[
            {
                "title": "Sync cliente Beta",
                "start": "2026-06-01T12:00:00",
            }
        ],
        notes=[
            {
                "title": "Pendientes Beta",
                "body": "Decision pendiente y sin owner para el siguiente paso.",
            }
        ],
    )

    assert any("agenda" in item.lower() for item in brief.risks)
    assert any("participantes" in item.lower() for item in brief.risks)
    assert any("material base" in item.lower() for item in brief.risks)
    assert any("owner" in item.lower() for item in brief.risks)
    assert any("decision concreta" in item.lower() for item in brief.questions)
    assert any("owner" in item.lower() for item in brief.questions)
    assert any(
        "desbloquear" in item.lower() or "alinear objetivo" in item.lower()
        for item in brief.priorities
    )


def test_meeting_prep_brief_render_exposes_sections_and_source_fallbacks() -> None:
    brief = build_meeting_prep_brief(
        meeting_title="Retro interna ADV ARCHON",
        project_name="ADV ARCHON",
    )

    assert isinstance(brief, MeetingPrepBrief)

    rendered = brief.render()

    assert "ADV ARCHON meeting prep" in rendered
    assert "Resumen:" in rendered
    assert "Contexto:" in rendered
    assert "Prioridades:" in rendered
    assert "Riesgos:" in rendered
    assert "Preguntas sugeridas:" in rendered
    assert "Fuentes:" in rendered
    assert "Sin evento enlazado." in rendered
    assert "Sin correos relacionados." in rendered
