from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Literal

Priority = Literal["urgent", "today", "waiting", "low"]
GroupMode = Literal["auto", "thread", "sender", "none"]
GroupBy = Literal["thread", "sender", "message"]

_PRIORITY_RANK: dict[Priority, int] = {
    "urgent": 0,
    "today": 1,
    "waiting": 2,
    "low": 3,
}

_URGENT_KEYWORDS = (
    "urgent",
    "urgente",
    "asap",
    "critico",
    "critical",
    "bloqueado",
    "blocked",
    "hoy",
    "today",
    "eod",
    "end of day",
    "antes de",
)

_TODAY_KEYWORDS = (
    "manana",
    "tomorrow",
    "esta tarde",
    "this afternoon",
    "hoy",
    "today",
    "seguimiento",
    "follow up",
    "recordatorio",
    "reminder",
)

_ACTION_KEYWORDS = (
    "puedes",
    "podrias",
    "por favor",
    "please",
    "necesito",
    "need",
    "review",
    "revisar",
    "approve",
    "aprobar",
    "confirm",
    "confirma",
    "share",
    "enviar",
    "envia",
    "responde",
    "reply",
    "can you",
    "would you",
)

_WAITING_KEYWORDS = (
    "quedo atento",
    "quedo pendiente",
    "awaiting",
    "waiting",
    "let me know",
    "avisa",
    "avisame",
    "any update",
)

_LOW_PRIORITY_KEYWORDS = (
    "newsletter",
    "unsubscribe",
    "digest",
    "webinar",
    "promocion",
    "promotion",
    "oferta",
    "sale",
    "marketing",
    "noreply",
    "no-reply",
)

_MEETING_KEYWORDS = ("meet", "reunion", "call", "demo", "agenda", "calendar")
_REVIEW_KEYWORDS = ("review", "revisar", "feedback", "comentarios", "approve", "aprobar")


@dataclass(slots=True)
class GmailMessageTriage:
    message_id: str | None
    thread_id: str | None
    priority: Priority
    subject: str
    sender: str
    sender_name: str | None
    sender_email: str | None
    received_at: datetime | None
    due_at: datetime | None
    labels: list[str]
    summary: str
    reasons: list[str]
    next_steps: list[str]
    unread: bool
    from_me: bool
    has_question: bool
    action_requested: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "priority": self.priority,
            "subject": self.subject,
            "sender": self.sender,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "labels": list(self.labels),
            "summary": self.summary,
            "reasons": list(self.reasons),
            "next_steps": list(self.next_steps),
            "unread": self.unread,
            "from_me": self.from_me,
            "has_question": self.has_question,
            "action_requested": self.action_requested,
        }


@dataclass(slots=True)
class GmailThreadTriage:
    thread_id: str | None
    priority: Priority
    latest_subject: str
    message_count: int
    participants: list[str]
    reasons: list[str]
    next_steps: list[str]
    messages: list[GmailMessageTriage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "priority": self.priority,
            "latest_subject": self.latest_subject,
            "message_count": self.message_count,
            "participants": list(self.participants),
            "reasons": list(self.reasons),
            "next_steps": list(self.next_steps),
            "messages": [message.to_dict() for message in self.messages],
        }


@dataclass(slots=True)
class GmailGroupSummary:
    group_by: GroupBy
    key: str
    label: str
    priority: Priority
    message_ids: list[str]
    thread_ids: list[str]
    subjects: list[str]
    senders: list[str]
    reasons: list[str]
    next_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_by": self.group_by,
            "key": self.key,
            "label": self.label,
            "priority": self.priority,
            "message_ids": list(self.message_ids),
            "thread_ids": list(self.thread_ids),
            "subjects": list(self.subjects),
            "senders": list(self.senders),
            "reasons": list(self.reasons),
            "next_steps": list(self.next_steps),
        }


@dataclass(slots=True)
class GmailMailboxTriage:
    messages: list[GmailMessageTriage]
    groups: list[GmailGroupSummary]
    counts: dict[Priority, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": [message.to_dict() for message in self.messages],
            "groups": [group.to_dict() for group in self.groups],
            "counts": dict(self.counts),
        }


@dataclass(slots=True)
class GmailReplyDraft:
    to: list[str]
    cc: list[str]
    subject: str
    body: str
    priority_context: Priority
    language: str = "es"

    def to_dict(self) -> dict[str, Any]:
        return {
            "to": list(self.to),
            "cc": list(self.cc),
            "subject": self.subject,
            "body": self.body,
            "priority_context": self.priority_context,
            "language": self.language,
        }


@dataclass(slots=True)
class _MessageView:
    raw: Mapping[str, Any]
    message_id: str | None
    thread_id: str | None
    subject: str
    snippet: str
    body: str
    sender_display: str
    sender_name: str | None
    sender_email: str | None
    to_emails: list[str]
    received_at: datetime | None
    due_at: datetime | None
    labels: set[str]
    unread: bool
    important: bool
    from_me: bool
    has_question: bool
    action_requested: bool
    urgent_signal: bool
    today_signal: bool
    waiting_signal: bool
    low_signal: bool
    meeting_signal: bool
    review_signal: bool
    text: str


def triage_message(
    message: Mapping[str, Any],
    *,
    now: datetime | None = None,
    owner_emails: Sequence[str] | None = None,
) -> GmailMessageTriage:
    current_time = _ensure_timezone(now or datetime.now(UTC))
    view = _message_view(message, owner_emails=owner_emails)
    priority, reasons = _classify_view(view, now=current_time)
    next_steps = _build_next_steps(view=view, priority=priority, now=current_time)
    summary = _build_summary(view=view, priority=priority)
    return GmailMessageTriage(
        message_id=view.message_id,
        thread_id=view.thread_id,
        priority=priority,
        subject=view.subject,
        sender=view.sender_display,
        sender_name=view.sender_name,
        sender_email=view.sender_email,
        received_at=view.received_at,
        due_at=view.due_at,
        labels=sorted(view.labels),
        summary=summary,
        reasons=reasons,
        next_steps=next_steps,
        unread=view.unread,
        from_me=view.from_me,
        has_question=view.has_question,
        action_requested=view.action_requested,
    )


def triage_thread(
    messages: Sequence[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    owner_emails: Sequence[str] | None = None,
) -> GmailThreadTriage:
    ordered = _coerce_messages(messages)
    if not ordered:
        raise ValueError("triage_thread requires at least one message")

    current_time = _ensure_timezone(now or datetime.now(UTC))
    triaged_pairs = [
        (
            _message_view(message, owner_emails=owner_emails),
            triage_message(message, now=current_time, owner_emails=owner_emails),
        )
        for message in ordered
    ]
    triaged_pairs.sort(key=lambda pair: _view_sort_key(pair[0]))
    views = [pair[0] for pair in triaged_pairs]
    results = [pair[1] for pair in triaged_pairs]
    latest_view = views[-1]
    latest_result = results[-1]

    if latest_view.from_me and len(results) > 1:
        priority: Priority = "waiting"
        reasons = _unique(
            [
                "El ultimo mensaje del hilo salio de tu bandeja.",
                *latest_result.reasons,
            ]
        )
        next_steps = _build_next_steps(view=latest_view, priority="waiting", now=current_time)
    else:
        priority = latest_result.priority
        reasons = list(latest_result.reasons)
        next_steps = list(latest_result.next_steps)

    participants = _unique(
        [
            view.sender_name or view.sender_email or view.sender_display
            for view in views
            if view.sender_name or view.sender_email or view.sender_display
        ]
    )
    thread_id = next((view.thread_id for view in views if view.thread_id), None)
    latest_subject = next((view.subject for view in reversed(views) if view.subject), "")
    return GmailThreadTriage(
        thread_id=thread_id,
        priority=priority,
        latest_subject=latest_subject,
        message_count=len(results),
        participants=participants,
        reasons=reasons,
        next_steps=next_steps,
        messages=results,
    )


def triage_mailbox(
    messages: Sequence[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    owner_emails: Sequence[str] | None = None,
    group_mode: GroupMode = "auto",
) -> GmailMailboxTriage:
    current_time = _ensure_timezone(now or datetime.now(UTC))
    results = [
        triage_message(message, now=current_time, owner_emails=owner_emails) for message in messages
    ]
    ordered_results = sorted(results, key=_result_sort_key)
    groups = _build_groups(ordered_results, group_mode=group_mode)
    counts = _priority_counts(ordered_results)
    return GmailMailboxTriage(messages=ordered_results, groups=groups, counts=counts)


def suggest_next_steps(
    item: GmailMessageTriage
    | GmailThreadTriage
    | GmailMailboxTriage
    | Mapping[str, Any]
    | Sequence[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    owner_emails: Sequence[str] | None = None,
) -> list[str]:
    if isinstance(item, GmailMessageTriage):
        return list(item.next_steps)
    if isinstance(item, GmailThreadTriage):
        return list(item.next_steps)
    if isinstance(item, GmailMailboxTriage):
        return _unique(step for result in item.messages for step in result.next_steps)

    messages = _coerce_item_messages(item)
    if len(messages) == 1:
        return triage_message(messages[0], now=now, owner_emails=owner_emails).next_steps
    return triage_thread(messages, now=now, owner_emails=owner_emails).next_steps


def build_reply_draft(
    item: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    owner_name: str = "ADV ARCHON",
    owner_signature: str | None = None,
    owner_emails: Sequence[str] | None = None,
    now: datetime | None = None,
) -> GmailReplyDraft:
    messages = _coerce_item_messages(item)
    if not messages:
        raise ValueError("build_reply_draft requires at least one message")

    current_time = _ensure_timezone(now or datetime.now(UTC))
    ordered_views = _sort_views(
        [_message_view(message, owner_emails=owner_emails) for message in messages]
    )
    thread = triage_thread(messages, now=current_time, owner_emails=owner_emails)
    latest_view = ordered_views[-1]
    signature = owner_signature or owner_name

    if thread.priority == "waiting" and latest_view.from_me:
        target_view = _latest_external_view(ordered_views) or latest_view
        recipients = latest_view.to_emails or (
            [target_view.sender_email] if target_view.sender_email else []
        )
        greeting = _greeting_name(target_view)
        topic = _draft_topic(target_view.subject)
        body = (
            f"Hola {greeting},\n\n"
            f"Retomo este hilo sobre {topic} por si has tenido oportunidad de revisarlo. "
            "Quedo pendiente de tu confirmacion o de cualquier ajuste que haga falta.\n\n"
            "Si te viene mejor, puedo resumir los puntos clave en un solo mensaje.\n\n"
            f"Un saludo,\n{signature}"
        )
        return GmailReplyDraft(
            to=_unique(recipient for recipient in recipients if recipient),
            cc=[],
            subject=_ensure_reply_subject(latest_view.subject or thread.latest_subject),
            body=body,
            priority_context=thread.priority,
        )

    target_view = _latest_external_view(ordered_views) or latest_view
    recipients = [target_view.sender_email] if target_view.sender_email else []
    greeting = _greeting_name(target_view)
    topic = _draft_topic(target_view.subject)
    action_line = _draft_action_line(
        target_view=target_view, priority=thread.priority, now=current_time
    )
    body = (
        f"Hola {greeting},\n\n"
        f"Gracias por tu mensaje sobre {topic}. {action_line}\n\n"
        "Si hay algun matiz importante o una fecha limite concreta, "
        "dímelo y lo incorporo en la respuesta.\n\n"
        f"Un saludo,\n{signature}"
    )
    return GmailReplyDraft(
        to=recipients,
        cc=[],
        subject=_ensure_reply_subject(target_view.subject or thread.latest_subject),
        body=body,
        priority_context=thread.priority,
    )


def _classify_view(view: _MessageView, *, now: datetime) -> tuple[Priority, list[str]]:
    reasons: list[str] = []

    urgent_score = 0
    today_score = 0
    waiting_score = 0
    low_score = 0

    if "SPAM" in view.labels or "TRASH" in view.labels:
        return "low", ["Esta etiquetado como spam o papelera."]

    if view.due_at:
        if view.due_at <= now + timedelta(hours=24):
            urgent_score += 5
            reasons.append("Tiene una fecha limite dentro de las proximas 24h.")
        elif view.due_at.date() <= (now + timedelta(days=2)).date():
            today_score += 3
            reasons.append("Tiene una fecha objetivo cercana.")

    if view.urgent_signal:
        urgent_score += 4
        reasons.append("El lenguaje del mensaje indica urgencia.")
    if view.important:
        urgent_score += 1
        reasons.append("Gmail lo marca como importante.")
    if view.unread:
        urgent_score += 1
        today_score += 1
        reasons.append("Sigue sin leer o sin procesar.")
    if view.action_requested or view.has_question:
        today_score += 3
        reasons.append("Contiene una peticion directa o una pregunta.")
    if view.today_signal:
        today_score += 2
        reasons.append("Habla de una accion para hoy o muy proxima.")
    if view.waiting_signal:
        waiting_score += 2
    if view.from_me:
        waiting_score += 4
        reasons.append("El ultimo movimiento fue un envio tuyo.")
    if view.low_signal:
        low_score += 4
        reasons.append("Parece contenido informativo o promocional.")
    if any(label.startswith("CATEGORY_") for label in view.labels) and {
        "CATEGORY_PROMOTIONS",
        "CATEGORY_FORUMS",
        "CATEGORY_SOCIAL",
    } & view.labels:
        low_score += 3
        reasons.append("Llega en una categoria normalmente no prioritaria.")
    if view.received_at and view.received_at.date() == now.date():
        today_score += 1
    if view.received_at and view.received_at < now - timedelta(days=7) and not view.unread:
        low_score += 2

    if view.from_me and waiting_score >= 4 and urgent_score < 6:
        return "waiting", _finalize_reasons(
            reasons, fallback="Estas esperando una respuesta del otro lado."
        )
    if urgent_score >= max(today_score + 1, 5):
        return "urgent", _finalize_reasons(reasons, fallback="Requiere atencion inmediata.")
    if today_score >= max(low_score + 1, 3):
        return "today", _finalize_reasons(reasons, fallback="Conviene resolverlo hoy.")
    if waiting_score >= max(low_score + 1, 4):
        return "waiting", _finalize_reasons(reasons, fallback="Queda a la espera de respuesta.")
    return "low", _finalize_reasons(reasons, fallback="No necesita foco inmediato.")


def _build_next_steps(view: _MessageView, *, priority: Priority, now: datetime) -> list[str]:
    steps: list[str] = []
    if priority == "urgent":
        steps.append("Responder en menos de una hora con el siguiente paso concreto.")
        if view.review_signal:
            steps.append("Revisar el material adjunto y confirmar decision hoy.")
        elif view.meeting_signal:
            steps.append("Confirmar horario o proponer una alternativa cerrada.")
        elif view.action_requested or view.has_question:
            steps.append("Contestar primero al bloqueo o pregunta principal.")
        if view.due_at:
            due_text = view.due_at.astimezone(now.tzinfo or UTC).strftime("%Y-%m-%d %H:%M")
            steps.append(f"Dejar claro el compromiso antes de {due_text}.")
    elif priority == "today":
        steps.append("Responder hoy y convertirlo en una tarea concreta si aplica.")
        if view.review_signal:
            steps.append("Reservar un bloque corto para revisar y devolver feedback.")
        elif view.meeting_signal:
            steps.append("Confirmar disponibilidad o pedir dos opciones de horario.")
        elif view.action_requested or view.has_question:
            steps.append("Responder con la informacion minima necesaria para desbloquear.")
        if view.unread:
            steps.append("Marcarlo como procesado solo despues de responder o delegar.")
    elif priority == "waiting":
        steps.append("No responder de nuevo todavia; deja espacio para contestacion.")
        steps.append("Programar seguimiento en 1-2 dias laborables si no responden.")
        if view.due_at:
            steps.append("Si vence el plazo, reenviar el contexto en el follow-up.")
    else:
        steps.append("Archivar o dejar fuera de la bandeja prioritaria por ahora.")
        if view.low_signal:
            steps.append("Cancelar la suscripcion si no aporta valor recurrente.")
        elif view.has_question or view.action_requested:
            steps.append("Moverlo a revision semanal si no bloquea nada hoy.")
    return _unique(steps)[:3]


def _build_summary(view: _MessageView, *, priority: Priority) -> str:
    if priority == "urgent":
        return f"{view.subject or 'Mensaje'} requiere respuesta inmediata."
    if priority == "today":
        return f"{view.subject or 'Mensaje'} conviene resolverlo hoy."
    if priority == "waiting":
        return f"{view.subject or 'Mensaje'} queda a la espera de respuesta."
    return f"{view.subject or 'Mensaje'} puede ir a cola de baja prioridad."


def _build_groups(
    results: Sequence[GmailMessageTriage],
    *,
    group_mode: GroupMode,
) -> list[GmailGroupSummary]:
    indexed_results = list(enumerate(results))
    if not indexed_results:
        return []

    if group_mode == "none":
        return [_single_message_group(index, result) for index, result in indexed_results]
    if group_mode == "thread":
        buckets: dict[tuple[str, str], list[GmailMessageTriage]] = defaultdict(list)
        for index, result in indexed_results:
            key = result.thread_id or result.message_id or f"message:{index}"
            buckets[("thread", key)].append(result)
        return _sorted_groups(
            [
                _summarize_bucket(group_by="thread", key=key, items=items)
                for (_, key), items in buckets.items()
            ]
        )
    if group_mode == "sender":
        buckets = defaultdict(list)
        for index, result in indexed_results:
            key = result.sender_email or result.sender or result.message_id or f"message:{index}"
            buckets[("sender", key)].append(result)
        return _sorted_groups(
            [
                _summarize_bucket(group_by="sender", key=key, items=items)
                for (_, key), items in buckets.items()
            ]
        )

    grouped_ids: set[str] = set()
    groups: list[GmailGroupSummary] = []

    thread_buckets: dict[str, list[GmailMessageTriage]] = defaultdict(list)
    for result in results:
        if result.thread_id:
            thread_buckets[result.thread_id].append(result)
    for thread_id, items in thread_buckets.items():
        if len(items) > 1:
            groups.append(_summarize_bucket(group_by="thread", key=thread_id, items=items))
            grouped_ids.update(message_id for message_id in _result_ids(items))

    sender_buckets: dict[str, list[GmailMessageTriage]] = defaultdict(list)
    for result in results:
        if result.message_id and result.message_id in grouped_ids:
            continue
        sender_key = result.sender_email or result.sender
        if sender_key:
            sender_buckets[sender_key].append(result)
    for sender_key, items in sender_buckets.items():
        if len(items) > 1:
            groups.append(_summarize_bucket(group_by="sender", key=sender_key, items=items))
            grouped_ids.update(message_id for message_id in _result_ids(items))

    for index, result in indexed_results:
        if result.message_id and result.message_id in grouped_ids:
            continue
        groups.append(_single_message_group(index, result))
    return _sorted_groups(groups)


def _summarize_bucket(
    *,
    group_by: GroupBy,
    key: str,
    items: Sequence[GmailMessageTriage],
) -> GmailGroupSummary:
    ordered = sorted(items, key=_result_sort_key)
    if group_by == "thread" and ordered and ordered[0].from_me and len(ordered) > 1:
        priority: Priority = "waiting"
    else:
        priority = min(
            (item.priority for item in items),
            key=lambda item_priority: _PRIORITY_RANK[item_priority],
        )
    latest_subject = next((item.subject for item in ordered if item.subject), key)
    sender_label = next((item.sender for item in ordered if item.sender), key)
    label = latest_subject if group_by == "thread" else sender_label
    return GmailGroupSummary(
        group_by=group_by,
        key=key,
        label=label,
        priority=priority,
        message_ids=_result_ids(items),
        thread_ids=_unique(item.thread_id for item in items if item.thread_id),
        subjects=_unique(item.subject for item in items if item.subject),
        senders=_unique(item.sender for item in items if item.sender),
        reasons=_unique(reason for item in items for reason in item.reasons)[:4],
        next_steps=_unique(step for item in items for step in item.next_steps)[:4],
    )


def _single_message_group(index: int, result: GmailMessageTriage) -> GmailGroupSummary:
    key = result.message_id or f"message:{index}"
    label = result.subject or result.sender or key
    return GmailGroupSummary(
        group_by="message",
        key=key,
        label=label,
        priority=result.priority,
        message_ids=[message_id for message_id in [result.message_id] if message_id],
        thread_ids=[thread_id for thread_id in [result.thread_id] if thread_id],
        subjects=[result.subject] if result.subject else [],
        senders=[result.sender] if result.sender else [],
        reasons=list(result.reasons),
        next_steps=list(result.next_steps),
    )


def _priority_counts(results: Sequence[GmailMessageTriage]) -> dict[Priority, int]:
    counter: Counter[Priority] = Counter(result.priority for result in results)
    return {
        "urgent": counter.get("urgent", 0),
        "today": counter.get("today", 0),
        "waiting": counter.get("waiting", 0),
        "low": counter.get("low", 0),
    }


def _coerce_item_messages(
    item: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(item, Mapping):
        nested = item.get("messages")
        if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes, bytearray)):
            return _coerce_messages(nested)
        return [item]
    return _coerce_messages(item)


def _coerce_messages(messages: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [message for message in messages if isinstance(message, Mapping)]


def _message_view(
    message: Mapping[str, Any],
    *,
    owner_emails: Sequence[str] | None,
) -> _MessageView:
    labels = {
        str(label).strip().upper()
        for label in (message.get("label_ids") or message.get("labels") or [])
        if str(label).strip()
    }
    sender_display = _coerce_text(message.get("from") or message.get("sender"))
    sender_name, sender_email = _parse_person(sender_display)
    subject = _coerce_text(message.get("subject"))
    snippet = _coerce_text(message.get("snippet") or message.get("summary"))
    body = _coerce_text(message.get("body") or message.get("body_excerpt") or message.get("text"))
    text = "\n".join(part for part in [subject, snippet, body] if part).lower()
    received_at = _parse_datetime(
        message.get("received_at")
        or message.get("internal_date")
        or message.get("internalDate")
        or message.get("date")
    )
    due_at = _parse_datetime(
        message.get("due_at") or message.get("deadline") or message.get("reply_by")
    )
    owner_email_set = {
        str(email).strip().lower() for email in owner_emails or [] if str(email).strip()
    }
    from_me = bool(message.get("from_me") or message.get("is_sent")) or "SENT" in labels
    if sender_email and sender_email.lower() in owner_email_set:
        from_me = True

    to_emails = _parse_recipients(_coerce_text(message.get("to")))
    unread = bool(message.get("is_unread") or message.get("unread")) or "UNREAD" in labels
    important = (
        bool(message.get("is_important") or message.get("important")) or "IMPORTANT" in labels
    )

    return _MessageView(
        raw=message,
        message_id=_coerce_optional_text(message.get("id") or message.get("message_id")),
        thread_id=_coerce_optional_text(message.get("thread_id") or message.get("threadId")),
        subject=subject,
        snippet=snippet,
        body=body,
        sender_display=sender_display or sender_email or "",
        sender_name=sender_name,
        sender_email=sender_email,
        to_emails=to_emails,
        received_at=received_at,
        due_at=due_at,
        labels=labels,
        unread=unread,
        important=important,
        from_me=from_me,
        has_question="?" in text,
        action_requested=_contains_keyword(text, _ACTION_KEYWORDS),
        urgent_signal=_contains_keyword(text, _URGENT_KEYWORDS),
        today_signal=_contains_keyword(text, _TODAY_KEYWORDS),
        waiting_signal=_contains_keyword(text, _WAITING_KEYWORDS),
        low_signal=_contains_keyword(text, _LOW_PRIORITY_KEYWORDS),
        meeting_signal=_contains_keyword(text, _MEETING_KEYWORDS),
        review_signal=_contains_keyword(text, _REVIEW_KEYWORDS),
        text=text,
    )


def _parse_person(value: str) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    match = re.search(r"<([^>]+)>", value)
    if match:
        email = match.group(1).strip()
        name = value[: match.start()].strip().strip('"')
        return (name or _name_from_email(email), email.lower())
    if "@" in value and " " not in value:
        return _name_from_email(value), value.lower()
    return value.strip(), None


def _name_from_email(email: str) -> str:
    local_part = email.split("@", 1)[0]
    words = [chunk for chunk in re.split(r"[._-]+", local_part) if chunk]
    if not words:
        return local_part
    return " ".join(word.capitalize() for word in words)


def _parse_recipients(value: str) -> list[str]:
    if not value:
        return []
    recipients: list[str] = []
    for chunk in re.split(r"[;,]", value):
        _, email = _parse_person(chunk.strip())
        if email:
            recipients.append(email)
    return _unique(recipients)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _ensure_timezone(value)
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp = timestamp / 1000.0
        return datetime.fromtimestamp(timestamp, tz=UTC)

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        timestamp = float(text)
        if timestamp > 1_000_000_000_000:
            timestamp = timestamp / 1000.0
        return datetime.fromtimestamp(timestamp, tz=UTC)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return _ensure_timezone(parsed)
    except ValueError:
        pass
    try:
        return _ensure_timezone(parsedate_to_datetime(text))
    except (TypeError, ValueError, IndexError):
        return None


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _result_sort_key(result: GmailMessageTriage) -> tuple[int, int, float]:
    received_at = result.received_at or datetime(1970, 1, 1, tzinfo=UTC)
    return (
        _PRIORITY_RANK[result.priority],
        0 if result.unread else 1,
        -received_at.timestamp(),
    )


def _view_sort_key(view: _MessageView) -> tuple[float, str]:
    received_at = view.received_at or datetime(1970, 1, 1, tzinfo=UTC)
    return (received_at.timestamp(), view.message_id or "")


def _sort_views(views: Sequence[_MessageView]) -> list[_MessageView]:
    return sorted(views, key=_view_sort_key)


def _latest_external_view(views: Sequence[_MessageView]) -> _MessageView | None:
    for view in reversed(_sort_views(views)):
        if not view.from_me:
            return view
    return None


def _sorted_groups(groups: Sequence[GmailGroupSummary]) -> list[GmailGroupSummary]:
    group_rank = {"thread": 0, "sender": 1, "message": 2}
    return sorted(
        list(groups),
        key=lambda group: (
            _PRIORITY_RANK[group.priority],
            group_rank.get(group.group_by, 9),
            group.label.lower(),
        ),
    )


def _result_ids(items: Sequence[GmailMessageTriage]) -> list[str]:
    return _unique(item.message_id for item in items if item.message_id)


def _finalize_reasons(reasons: Sequence[str], *, fallback: str) -> list[str]:
    unique_reasons = _unique(reasons)
    if unique_reasons:
        return unique_reasons[:4]
    return [fallback]


def _contains_keyword(text: str, keywords: Sequence[str]) -> bool:
    normalized = text.lower()
    return any(keyword in normalized for keyword in keywords)


def _draft_topic(subject: str) -> str:
    base = _strip_reply_prefix(subject).strip()
    return base or "tu mensaje"


def _draft_action_line(*, target_view: _MessageView, priority: Priority, now: datetime) -> str:
    if priority == "urgent":
        return "Lo priorizo ahora mismo y te respondo con una propuesta cerrada hoy."
    if target_view.review_signal:
        return "Lo reviso y te devuelvo feedback hoy mismo."
    if target_view.meeting_signal:
        return "Reviso agenda y te confirmo una opcion concreta hoy."
    if target_view.action_requested or target_view.has_question:
        return "Te respondo con el siguiente paso concreto hoy."
    if target_view.due_at and target_view.due_at <= now + timedelta(days=2):
        return "Lo tomo ahora para llegar a tiempo con la fecha objetivo."
    return "Lo reviso y vuelvo contigo en cuanto tenga el siguiente paso claro."


def _greeting_name(view: _MessageView) -> str:
    if view.sender_name:
        return view.sender_name.split()[0]
    if view.sender_email:
        return _name_from_email(view.sender_email).split()[0]
    return "equipo"


def _ensure_reply_subject(subject: str) -> str:
    cleaned = subject.strip() or "Seguimiento"
    if re.match(r"(?i)^re:\s*", cleaned):
        return cleaned
    return f"Re: {cleaned}"


def _strip_reply_prefix(subject: str) -> str:
    return re.sub(r"(?i)^(re|fwd?):\s*", "", subject).strip()


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_optional_text(value: Any) -> str | None:
    text = _coerce_text(value)
    return text or None


def _unique(values: Sequence[str] | Any) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


__all__ = [
    "GmailGroupSummary",
    "GmailMailboxTriage",
    "GmailMessageTriage",
    "GmailReplyDraft",
    "GmailThreadTriage",
    "build_reply_draft",
    "suggest_next_steps",
    "triage_mailbox",
    "triage_message",
    "triage_thread",
]
