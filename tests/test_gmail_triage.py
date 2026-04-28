from __future__ import annotations

from datetime import UTC, datetime

from adv_archon.core.gmail_triage import (
    build_reply_draft,
    suggest_next_steps,
    triage_mailbox,
    triage_message,
    triage_thread,
)


def test_triage_message_marks_urgent_when_deadline_and_request_are_near() -> None:
    now = datetime(2026, 4, 27, 9, 0, tzinfo=UTC)
    message = {
        "id": "m-urgent",
        "thread_id": "t-urgent",
        "from": "Ana Cliente <ana@acme.com>",
        "subject": "URGENTE: contrato para hoy",
        "snippet": "Puedes confirmarlo antes de las 17:00?",
        "date": "2026-04-27T08:30:00+00:00",
        "deadline": "2026-04-27T17:00:00+00:00",
        "label_ids": ["INBOX", "UNREAD", "IMPORTANT"],
    }

    result = triage_message(message, now=now)

    assert result.priority == "urgent"
    assert result.sender_email == "ana@acme.com"
    assert any("24h" in reason for reason in result.reasons)
    assert any("menos de una hora" in step for step in result.next_steps)


def test_triage_message_marks_waiting_for_sent_follow_up() -> None:
    now = datetime(2026, 4, 27, 9, 0, tzinfo=UTC)
    message = {
        "id": "m-waiting",
        "thread_id": "t-waiting",
        "from": "Pablo <pablo@example.com>",
        "to": "cliente@acme.com",
        "subject": "Seguimiento propuesta",
        "body": "Te comparto la propuesta. Quedo atento a tu confirmacion.",
        "date": "2026-04-26T15:00:00+00:00",
        "label_ids": ["SENT"],
    }

    result = triage_message(message, now=now, owner_emails=["pablo@example.com"])

    assert result.priority == "waiting"
    assert result.from_me is True
    assert any("seguimiento" in step.lower() for step in result.next_steps)


def test_triage_thread_uses_waiting_when_latest_message_is_from_me() -> None:
    now = datetime(2026, 4, 27, 9, 0, tzinfo=UTC)
    thread = [
        {
            "id": "m-1",
            "thread_id": "thread-1",
            "from": "Ana Cliente <ana@acme.com>",
            "subject": "Revision contrato",
            "snippet": "Puedes revisar el ultimo borrador?",
            "date": "2026-04-25T09:00:00+00:00",
            "label_ids": ["INBOX"],
        },
        {
            "id": "m-2",
            "thread_id": "thread-1",
            "from": "Pablo <pablo@example.com>",
            "to": "ana@acme.com",
            "subject": "Re: Revision contrato",
            "body": "Lo reviso hoy y te mando version final. Quedo atento.",
            "date": "2026-04-25T10:00:00+00:00",
            "label_ids": ["SENT"],
        },
    ]

    result = triage_thread(thread, now=now, owner_emails=["pablo@example.com"])

    assert result.priority == "waiting"
    assert result.thread_id == "thread-1"
    assert result.message_count == 2
    assert "Ana Cliente" in result.participants


def test_triage_mailbox_auto_groups_by_thread_then_sender() -> None:
    now = datetime(2026, 4, 27, 9, 0, tzinfo=UTC)
    mailbox = [
        {
            "id": "m-1",
            "thread_id": "thread-1",
            "from": "Ana Cliente <ana@acme.com>",
            "subject": "Contrato",
            "snippet": "Puedes revisar esto hoy?",
            "date": "2026-04-27T08:00:00+00:00",
            "label_ids": ["UNREAD"],
        },
        {
            "id": "m-2",
            "thread_id": "thread-1",
            "from": "Pablo <pablo@example.com>",
            "to": "ana@acme.com",
            "subject": "Re: Contrato",
            "body": "Te respondo en breve.",
            "date": "2026-04-27T08:10:00+00:00",
            "label_ids": ["SENT"],
        },
        {
            "id": "m-3",
            "thread_id": "thread-2",
            "from": "Luis Ops <luis@acme.com>",
            "subject": "Checklist semanal",
            "snippet": "Te comparto el checklist actualizado",
            "date": "2026-04-26T12:00:00+00:00",
            "label_ids": ["INBOX"],
        },
        {
            "id": "m-4",
            "thread_id": "thread-3",
            "from": "Luis Ops <luis@acme.com>",
            "subject": "Nueva incidencia",
            "snippet": "Necesito respuesta hoy sobre el acceso",
            "date": "2026-04-27T07:00:00+00:00",
            "label_ids": ["UNREAD"],
        },
    ]

    result = triage_mailbox(mailbox, now=now, owner_emails=["pablo@example.com"])

    assert result.counts["waiting"] == 1
    assert result.counts["today"] >= 1
    assert result.groups[0].group_by == "thread"
    assert any(
        group.group_by == "sender" and group.key == "luis@acme.com" for group in result.groups
    )


def test_suggest_next_steps_accepts_thread_mapping() -> None:
    now = datetime(2026, 4, 27, 9, 0, tzinfo=UTC)
    thread = {
        "messages": [
            {
                "id": "m-1",
                "thread_id": "thread-9",
                "from": "Eva <eva@acme.com>",
                "subject": "Demo",
                "snippet": "Podemos cerrar una reunion hoy?",
                "date": "2026-04-27T06:30:00+00:00",
                "label_ids": ["UNREAD"],
            }
        ]
    }

    steps = suggest_next_steps(thread, now=now)

    assert any("Responder hoy" in step for step in steps)


def test_build_reply_draft_generates_spanish_reply_for_incoming_message() -> None:
    now = datetime(2026, 4, 27, 9, 0, tzinfo=UTC)
    message = {
        "id": "m-reply",
        "thread_id": "t-reply",
        "from": "Marta <marta@acme.com>",
        "subject": "Revision propuesta",
        "snippet": "Puedes revisar el documento y decirme si lo cerramos hoy?",
        "date": "2026-04-27T08:15:00+00:00",
        "label_ids": ["UNREAD"],
    }

    draft = build_reply_draft(message, now=now, owner_name="Pablo")

    assert draft.to == ["marta@acme.com"]
    assert draft.subject == "Re: Revision propuesta"
    assert "Hola Marta" in draft.body
    assert "Gracias por tu mensaje" in draft.body
    assert draft.priority_context in {"today", "urgent"}


def test_build_reply_draft_creates_follow_up_when_thread_is_waiting() -> None:
    now = datetime(2026, 4, 27, 9, 0, tzinfo=UTC)
    thread = [
        {
            "id": "m-a",
            "thread_id": "thread-follow-up",
            "from": "Sara <sara@acme.com>",
            "subject": "Aprobacion presupuesto",
            "snippet": "Puedes mandarme la ultima version?",
            "date": "2026-04-24T09:00:00+00:00",
            "label_ids": ["INBOX"],
        },
        {
            "id": "m-b",
            "thread_id": "thread-follow-up",
            "from": "Pablo <pablo@example.com>",
            "to": "sara@acme.com",
            "subject": "Re: Aprobacion presupuesto",
            "body": "Te paso la version final. Quedo atento.",
            "date": "2026-04-24T10:00:00+00:00",
            "label_ids": ["SENT"],
        },
    ]

    draft = build_reply_draft(
        thread,
        now=now,
        owner_name="Pablo",
        owner_emails=["pablo@example.com"],
    )

    assert draft.to == ["sara@acme.com"]
    assert "Retomo este hilo" in draft.body
    assert draft.priority_context == "waiting"
