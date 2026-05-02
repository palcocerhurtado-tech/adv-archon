from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

_MAX_SOURCE_ITEMS = 3
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "about",
    "after",
    "algo",
    "and",
    "ante",
    "antes",
    "como",
    "con",
    "contra",
    "de",
    "del",
    "desde",
    "donde",
    "el",
    "ella",
    "ellos",
    "en",
    "entre",
    "esta",
    "este",
    "for",
    "from",
    "hacia",
    "hasta",
    "into",
    "la",
    "las",
    "los",
    "meeting",
    "para",
    "pero",
    "por",
    "que",
    "reunion",
    "sobre",
    "sync",
    "the",
    "una",
    "uno",
    "with",
    "y",
}
_GENERIC_TITLES = {"1:1", "1on1", "catchup", "checkin", "reunion", "retro", "sync", "weekly"}
_URGENCY_MARKERS = {
    "aprobacion",
    "approval",
    "asap",
    "blocker",
    "bloqueado",
    "bloqueo",
    "critico",
    "critical",
    "deadline",
    "escalar",
    "hoy",
    "pendiente",
    "riesgo",
    "risk",
    "urgente",
    "urgent",
    "vence",
}
_OWNER_GAP_MARKERS = {"owner", "responsable", "sin owner", "sinowner"}
_DECISION_MARKERS = {"acordar", "alinear", "aprobar", "cerrar", "decidir", "decision", "signoff"}
_TopItem = TypeVar("_TopItem")


@dataclass(slots=True)
class MeetingPrepBrief:
    meeting_title: str
    meeting_when: str | None
    project_name: str | None
    summary: list[str]
    context: list[str]
    priorities: list[str]
    risks: list[str]
    questions: list[str]
    sources: dict[str, list[dict[str, str]]]

    def render(self) -> str:
        lines = [
            "ADV ARCHON meeting prep",
            f"- Reunion: {self.meeting_title}",
            f"- Cuando: {self.meeting_when or 'sin fecha concreta'}",
            f"- Proyecto: {self.project_name or 'sin proyecto asociado'}",
            "",
            "Resumen:",
        ]
        lines.extend(_render_bullets(self.summary, empty_message="Sin resumen adicional."))
        lines.extend(
            [
                "",
                "Contexto:",
            ]
        )
        lines.extend(_render_bullets(self.context, empty_message="Sin contexto adicional."))
        lines.extend(
            [
                "",
                "Prioridades:",
            ]
        )
        lines.extend(
            _render_bullets(self.priorities, empty_message="No detecto prioridades especiales.")
        )
        lines.extend(
            [
                "",
                "Riesgos:",
            ]
        )
        lines.extend(
            _render_bullets(
                self.risks, empty_message="No veo riesgos claros con la informacion disponible."
            )
        )
        lines.extend(
            [
                "",
                "Preguntas sugeridas:",
            ]
        )
        lines.extend(
            _render_bullets(
                self.questions, empty_message="No hacen falta preguntas extra por ahora."
            )
        )
        lines.extend(
            [
                "",
                "Fuentes:",
                "- Calendar:",
            ]
        )
        lines.extend(
            _render_source_group(
                self.sources.get("calendar", []), empty_message="Sin evento enlazado."
            )
        )
        lines.append("- Gmail:")
        lines.extend(
            _render_source_group(
                self.sources.get("gmail", []), empty_message="Sin correos relacionados."
            )
        )
        lines.append("- Drive:")
        lines.extend(
            _render_source_group(
                self.sources.get("drive", []), empty_message="Sin archivos relacionados."
            )
        )
        lines.append("- Notes:")
        lines.extend(
            _render_source_group(
                self.sources.get("notes", []), empty_message="Sin notas relacionadas."
            )
        )
        lines.append("- Knowledge:")
        lines.extend(
            _render_source_group(
                self.sources.get("knowledge", []),
                empty_message="Sin conocimiento local relacionado.",
            )
        )
        return "\n".join(lines)


@dataclass(slots=True)
class _PreparedEvent:
    title: str
    when_text: str | None
    when_dt: datetime | None
    description: str
    attendees: list[str]
    location: str | None

    def searchable_text(self) -> str:
        return " ".join(
            part for part in [self.title, self.description, " ".join(self.attendees)] if part
        )

    def as_source(self) -> dict[str, str]:
        return {
            "title": self.title,
            "when": self.when_text or "",
            "description": _compact(self.description, 140),
            "attendees": ", ".join(self.attendees),
            "location": self.location or "",
        }


@dataclass(slots=True)
class _PreparedMessage:
    subject: str
    sender: str
    snippet: str
    received_text: str | None
    received_dt: datetime | None

    def searchable_text(self) -> str:
        return " ".join(part for part in [self.subject, self.sender, self.snippet] if part)

    def as_source(self) -> dict[str, str]:
        return {
            "subject": self.subject,
            "from": self.sender,
            "snippet": _compact(self.snippet, 140),
            "received_at": self.received_text or "",
        }


@dataclass(slots=True)
class _PreparedDriveFile:
    name: str
    owner: str
    summary: str
    modified_text: str | None
    modified_dt: datetime | None

    def searchable_text(self) -> str:
        return " ".join(part for part in [self.name, self.owner, self.summary] if part)

    def as_source(self) -> dict[str, str]:
        return {
            "name": self.name,
            "owner": self.owner,
            "summary": _compact(self.summary, 140),
            "modified_at": self.modified_text or "",
        }


@dataclass(slots=True)
class _PreparedNote:
    title: str
    body: str
    path: str
    updated_text: str | None
    updated_dt: datetime | None

    def searchable_text(self) -> str:
        return " ".join(part for part in [self.title, self.body, self.path] if part)

    def as_source(self) -> dict[str, str]:
        return {
            "title": self.title,
            "snippet": _compact(self.body or self.title, 140),
            "path": self.path,
            "updated_at": self.updated_text or "",
        }


@dataclass(slots=True)
class _PreparedKnowledgeHit:
    title: str
    snippet: str
    path: str
    score: float

    def searchable_text(self) -> str:
        return " ".join(part for part in [self.title, self.snippet, self.path] if part)

    def as_source(self) -> dict[str, str]:
        return {
            "title": self.title,
            "snippet": _compact(self.snippet, 140),
            "path": self.path,
            "score": f"{self.score:.2f}" if self.score else "",
        }


def build_meeting_prep_brief(
    *,
    meeting_title: str,
    meeting_when: str | None = None,
    calendar_events: list[dict[str, object]] | None = None,
    gmail_messages: list[dict[str, object]] | None = None,
    drive_files: list[dict[str, object]] | None = None,
    notes: list[dict[str, object]] | None = None,
    knowledge_hits: list[dict[str, object]] | None = None,
    project_name: str | None = None,
) -> MeetingPrepBrief:
    prepared_events = [_prepare_event(item) for item in calendar_events or []]
    prepared_messages = [_prepare_message(item) for item in gmail_messages or []]
    prepared_files = [_prepare_drive_file(item) for item in drive_files or []]
    prepared_notes = [_prepare_note(item) for item in notes or []]
    prepared_knowledge = [_prepare_knowledge_hit(item) for item in knowledge_hits or []]

    focus_event = _pick_focus_event(
        meeting_title=meeting_title,
        meeting_when=meeting_when,
        events=prepared_events,
    )
    resolved_when = (focus_event.when_text if focus_event else None) or meeting_when
    focus_keywords = _extract_keywords(
        " ".join(
            fragment
            for fragment in [
                meeting_title,
                meeting_when or "",
                project_name or "",
                focus_event.searchable_text() if focus_event else "",
            ]
            if fragment
        )
    )
    if not focus_keywords:
        focus_keywords = _extract_keywords(meeting_title)

    relevant_messages = _select_relevant_messages(prepared_messages, focus_keywords, resolved_when)
    relevant_files = _select_relevant_files(prepared_files, focus_keywords, resolved_when)
    relevant_notes = _select_relevant_notes(prepared_notes, focus_keywords, resolved_when)
    relevant_knowledge = _select_relevant_knowledge(prepared_knowledge, focus_keywords)

    summary = _build_summary(
        meeting_title=meeting_title,
        project_name=project_name,
        focus_event=focus_event,
        messages=relevant_messages,
        drive_files=relevant_files,
        notes=relevant_notes,
        knowledge_hits=relevant_knowledge,
    )
    context = _build_context(
        project_name=project_name,
        focus_event=focus_event,
        notes=relevant_notes,
        knowledge_hits=relevant_knowledge,
    )
    priorities = _build_priorities(
        focus_event=focus_event,
        messages=relevant_messages,
        drive_files=relevant_files,
        notes=relevant_notes,
        knowledge_hits=relevant_knowledge,
    )
    risks = _build_risks(
        focus_event=focus_event,
        drive_files=relevant_files,
        notes=relevant_notes,
        knowledge_hits=relevant_knowledge,
    )
    questions = _build_questions(
        focus_event=focus_event,
        messages=relevant_messages,
        drive_files=relevant_files,
        notes=relevant_notes,
        knowledge_hits=relevant_knowledge,
        risks=risks,
    )
    sources = {
        "calendar": [focus_event.as_source()] if focus_event else [],
        "gmail": [item.as_source() for item in relevant_messages],
        "drive": [item.as_source() for item in relevant_files],
        "notes": [item.as_source() for item in relevant_notes],
        "knowledge": [item.as_source() for item in relevant_knowledge],
    }
    return MeetingPrepBrief(
        meeting_title=focus_event.title if focus_event else meeting_title,
        meeting_when=resolved_when,
        project_name=project_name,
        summary=summary,
        context=context,
        priorities=priorities,
        risks=risks,
        questions=questions,
        sources=sources,
    )


def _prepare_event(payload: dict[str, object]) -> _PreparedEvent:
    when_text, when_dt = _read_time(
        payload.get("start") or payload.get("start_at") or payload.get("when")
    )
    attendees = _coerce_people(
        payload.get("attendees") or payload.get("participants") or payload.get("guests")
    )
    return _PreparedEvent(
        title=_first_present_str(payload, "title", "summary", "name") or "Reunion sin titulo",
        when_text=when_text,
        when_dt=when_dt,
        description=_first_present_str(payload, "description", "notes", "body") or "",
        attendees=attendees,
        location=_first_present_str(payload, "location", "where"),
    )


def _prepare_message(payload: dict[str, object]) -> _PreparedMessage:
    received_text, received_dt = _read_time(
        payload.get("received_at") or payload.get("date") or payload.get("sent_at")
    )
    return _PreparedMessage(
        subject=_first_present_str(payload, "subject", "title") or "Sin asunto",
        sender=_first_present_str(payload, "from", "sender") or "Remitente desconocido",
        snippet=_first_present_str(payload, "snippet", "summary", "body") or "",
        received_text=received_text,
        received_dt=received_dt,
    )


def _prepare_drive_file(payload: dict[str, object]) -> _PreparedDriveFile:
    modified_text, modified_dt = _read_time(
        payload.get("modified_at") or payload.get("modified_time") or payload.get("updated_at")
    )
    return _PreparedDriveFile(
        name=_first_present_str(payload, "name", "title") or "Documento sin nombre",
        owner=_first_present_str(payload, "owner", "author") or "Owner desconocido",
        summary=_first_present_str(payload, "summary", "snippet", "description") or "",
        modified_text=modified_text,
        modified_dt=modified_dt,
    )


def _prepare_note(payload: dict[str, object]) -> _PreparedNote:
    updated_text, updated_dt = _read_time(payload.get("updated_at") or payload.get("date"))
    body = _first_present_str(payload, "body", "text") or ""
    title = _first_present_str(payload, "title") or _title_from_text(body)
    return _PreparedNote(
        title=title or "Nota local",
        body=body,
        path=_first_present_str(payload, "path", "file") or "",
        updated_text=updated_text,
        updated_dt=updated_dt,
    )


def _prepare_knowledge_hit(payload: dict[str, object]) -> _PreparedKnowledgeHit:
    raw_score = payload.get("score")
    score = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0
    return _PreparedKnowledgeHit(
        title=_first_present_str(payload, "title", "name") or "Knowledge hit",
        snippet=_first_present_str(payload, "snippet", "summary", "body", "text") or "",
        path=_first_present_str(payload, "path", "source") or "",
        score=score,
    )


def _pick_focus_event(
    *,
    meeting_title: str,
    meeting_when: str | None,
    events: list[_PreparedEvent],
) -> _PreparedEvent | None:
    if not events:
        return None
    target_keywords = set(_extract_keywords(meeting_title))

    def score(event: _PreparedEvent) -> tuple[int, int]:
        event_keywords = set(_extract_keywords(event.searchable_text()))
        keyword_overlap = len(event_keywords & target_keywords)
        phrase_bonus = 6 if _contains_phrase(event.title, meeting_title) else 0
        when_bonus = _when_match_score(meeting_when, event.when_text)
        info_bonus = 1 if event.attendees else 0
        info_bonus += 1 if _has_agenda(event) else 0
        generic_penalty = -1 if _is_generic_title(event.title) else 0
        return phrase_bonus + keyword_overlap * 4 + when_bonus + info_bonus + generic_penalty, len(
            event.attendees
        )

    ranked = sorted(events, key=score, reverse=True)
    best = ranked[0]
    return best if score(best)[0] > 0 else None


def _select_relevant_messages(
    messages: list[_PreparedMessage],
    focus_keywords: list[str],
    meeting_when: str | None,
) -> list[_PreparedMessage]:
    return _take_top(
        messages,
        scorer=lambda item: (
            _overlap_score(item.searchable_text(), focus_keywords)
            + _urgency_score(item.searchable_text())
            + _time_relevance_score(item.received_text, meeting_when)
        ),
    )


def _select_relevant_files(
    drive_files: list[_PreparedDriveFile],
    focus_keywords: list[str],
    meeting_when: str | None,
) -> list[_PreparedDriveFile]:
    return _take_top(
        drive_files,
        scorer=lambda item: (
            _overlap_score(item.searchable_text(), focus_keywords)
            + _fresh_document_score(item.name, item.modified_text, meeting_when)
        ),
    )


def _select_relevant_notes(
    notes: list[_PreparedNote],
    focus_keywords: list[str],
    meeting_when: str | None,
) -> list[_PreparedNote]:
    return _take_top(
        notes,
        scorer=lambda item: (
            _overlap_score(item.searchable_text(), focus_keywords)
            + _urgency_score(item.searchable_text())
            + _time_relevance_score(item.updated_text, meeting_when)
        ),
    )


def _select_relevant_knowledge(
    knowledge_hits: list[_PreparedKnowledgeHit],
    focus_keywords: list[str],
) -> list[_PreparedKnowledgeHit]:
    return _take_top(
        knowledge_hits,
        scorer=lambda item: (
            _overlap_score(item.searchable_text(), focus_keywords) + int(item.score * 3)
        ),
    )


def _take_top(items: list[_TopItem], *, scorer: Callable[[_TopItem], int]) -> list[_TopItem]:
    ranked = sorted(items, key=scorer, reverse=True)
    return [item for item in ranked if scorer(item) > 0][:_MAX_SOURCE_ITEMS]


def _build_summary(
    *,
    meeting_title: str,
    project_name: str | None,
    focus_event: _PreparedEvent | None,
    messages: list[_PreparedMessage],
    drive_files: list[_PreparedDriveFile],
    notes: list[_PreparedNote],
    knowledge_hits: list[_PreparedKnowledgeHit],
) -> list[str]:
    summary: list[str] = []
    objective_basis = _objective_basis(
        focus_event, drive_files, notes, knowledge_hits, meeting_title
    )
    summary.append(f"Objetivo sugerido: {objective_basis}.")
    if project_name:
        summary.append(f"Contexto principal: reunion asociada a {project_name}.")
    if messages:
        message = messages[0]
        summary.append(
            "Presion externa: "
            f'{message.sender} espera respuesta sobre "{_compact(message.subject, 70)}".'
        )
    if drive_files:
        summary.append(f'Material base: revisar "{drive_files[0].name}" antes de decidir.')
    return _unique(summary)


def _build_context(
    *,
    project_name: str | None,
    focus_event: _PreparedEvent | None,
    notes: list[_PreparedNote],
    knowledge_hits: list[_PreparedKnowledgeHit],
) -> list[str]:
    context: list[str] = []
    if project_name:
        context.append(f"Proyecto: {project_name}.")
    if focus_event and focus_event.attendees:
        context.append(f"Participantes detectados: {', '.join(focus_event.attendees)}.")
    if focus_event and _has_agenda(focus_event):
        context.append(f"Agenda detectada: {_first_sentence(focus_event.description)}.")
    elif focus_event:
        context.append("El evento de calendario no trae agenda explicita.")
    else:
        context.append(
            "No encontre un evento claro en calendario "
            "y el brief se construyo desde el titulo dado."
        )
    if notes:
        context.append(f"Nota local: {_compact(notes[0].body or notes[0].title, 120)}.")
    if knowledge_hits:
        context.append(
            "Knowledge local: "
            f"{_compact(knowledge_hits[0].snippet or knowledge_hits[0].title, 120)}."
        )
    return _unique(context)


def _build_priorities(
    *,
    focus_event: _PreparedEvent | None,
    messages: list[_PreparedMessage],
    drive_files: list[_PreparedDriveFile],
    notes: list[_PreparedNote],
    knowledge_hits: list[_PreparedKnowledgeHit],
) -> list[str]:
    priorities: list[str] = []
    urgent_signal = _first_urgent_signal(messages, notes, knowledge_hits)
    if urgent_signal:
        priorities.append(f"Responder el frente urgente detectado: {urgent_signal}.")
    if drive_files:
        priorities.append(
            f'Validar que "{drive_files[0].name}" sea la version correcta para la conversacion.'
        )
    blocker = _first_blocker(notes, knowledge_hits)
    if blocker:
        priorities.append(f"Desbloquear {blocker} durante la reunion.")
    if focus_event and not _has_agenda(focus_event):
        priorities.append("Alinear objetivo y decision esperada en los primeros minutos.")
    if not priorities:
        priorities.append("Salir con decisiones y siguientes pasos concretos.")
    return _unique(priorities)


def _build_risks(
    *,
    focus_event: _PreparedEvent | None,
    drive_files: list[_PreparedDriveFile],
    notes: list[_PreparedNote],
    knowledge_hits: list[_PreparedKnowledgeHit],
) -> list[str]:
    risks: list[str] = []
    if focus_event is None:
        risks.append("No hay evento de calendario claramente asociado a la reunion.")
    elif not _has_agenda(focus_event):
        risks.append("La invitacion no deja clara la agenda ni la decision esperada.")
    if focus_event and not focus_event.attendees:
        risks.append(
            "No aparecen participantes claros y puede faltar alguien con capacidad de decision."
        )
    if not drive_files and not knowledge_hits:
        risks.append("Falta material base claro para llegar a acuerdos rapidos.")
    blocker = _first_blocker(notes, knowledge_hits)
    if blocker:
        risks.append(f"Sigue abierto un bloqueo relevante: {blocker}.")
    if _has_owner_gap(notes, knowledge_hits):
        risks.append("No esta claro quien queda owner de los siguientes pasos.")
    return _unique(risks)


def _build_questions(
    *,
    focus_event: _PreparedEvent | None,
    messages: list[_PreparedMessage],
    drive_files: list[_PreparedDriveFile],
    notes: list[_PreparedNote],
    knowledge_hits: list[_PreparedKnowledgeHit],
    risks: list[str],
) -> list[str]:
    questions: list[str] = []
    if focus_event is None or not _has_agenda(focus_event):
        questions.append("¿Que decision concreta tiene que salir hoy?")
    if messages and _urgency_score(messages[0].searchable_text()) > 0:
        questions.append("¿Que respuesta exacta espera la otra parte y para cuando?")
    if drive_files:
        questions.append(f'¿Confirmamos que "{drive_files[0].name}" es el documento base?')
    if _first_blocker(notes, knowledge_hits):
        questions.append("¿Que dependencia impide avanzar y quien la desbloquea?")
    if _has_owner_gap(notes, knowledge_hits) or risks:
        questions.append("¿Quien sale owner de cada siguiente paso y con que fecha?")
    return _unique(questions)[:5]


def _objective_basis(
    focus_event: _PreparedEvent | None,
    drive_files: list[_PreparedDriveFile],
    notes: list[_PreparedNote],
    knowledge_hits: list[_PreparedKnowledgeHit],
    meeting_title: str,
) -> str:
    if focus_event and _has_agenda(focus_event):
        return _first_sentence(focus_event.description)
    if drive_files:
        return f"revisar {drive_files[0].name} y cerrar decisiones relacionadas"
    if notes:
        return f"despejar el pendiente principal: {_compact(notes[0].title, 70)}"
    if knowledge_hits:
        return (
            "usar el contexto conocido sobre "
            f"{_compact(knowledge_hits[0].title, 70)} para acordar siguientes pasos"
        )
    return f"salir de {meeting_title} con decisiones y responsables claros"


def _first_urgent_signal(
    messages: list[_PreparedMessage],
    notes: list[_PreparedNote],
    knowledge_hits: list[_PreparedKnowledgeHit],
) -> str | None:
    for message in messages:
        text = message.searchable_text()
        if _urgency_score(text) > 0:
            return _compact(text, 90)
    for note in notes:
        text = note.searchable_text()
        if _urgency_score(text) > 0:
            return _compact(text, 90)
    for knowledge_hit in knowledge_hits:
        text = knowledge_hit.searchable_text()
        if _urgency_score(text) > 0:
            return _compact(text, 90)
    return None


def _first_blocker(
    notes: list[_PreparedNote], knowledge_hits: list[_PreparedKnowledgeHit]
) -> str | None:
    for note in notes:
        text = note.searchable_text()
        normalized = _normalize(text)
        if any(marker in normalized for marker in _URGENCY_MARKERS | _DECISION_MARKERS):
            return _compact(text, 90)
    for knowledge_hit in knowledge_hits:
        text = knowledge_hit.searchable_text()
        normalized = _normalize(text)
        if any(marker in normalized for marker in _URGENCY_MARKERS | _DECISION_MARKERS):
            return _compact(text, 90)
    return None


def _has_owner_gap(notes: list[_PreparedNote], knowledge_hits: list[_PreparedKnowledgeHit]) -> bool:
    combined = " ".join(
        [item.searchable_text() for item in notes]
        + [item.searchable_text() for item in knowledge_hits]
    )
    normalized = _normalize(combined)
    return any(marker in normalized for marker in _OWNER_GAP_MARKERS)


def _overlap_score(text: str, focus_keywords: list[str]) -> int:
    return len(set(_extract_keywords(text)) & set(focus_keywords)) * 4


def _urgency_score(text: str) -> int:
    normalized = _normalize(text)
    return 3 if any(marker in normalized for marker in _URGENCY_MARKERS) else 0


def _fresh_document_score(name: str, modified_text: str | None, meeting_when: str | None) -> int:
    score = 2 if any(character.isdigit() for character in name) else 0
    return score + _time_relevance_score(modified_text, meeting_when)


def _time_relevance_score(source_time: str | None, meeting_when: str | None) -> int:
    source_dt = _parse_datetime(source_time)
    meeting_dt = _parse_datetime(meeting_when)
    if source_dt is None or meeting_dt is None:
        return 0
    delta_hours = abs(_timestamp(meeting_dt) - _timestamp(source_dt)) / 3600
    if delta_hours <= 48:
        return 2
    if delta_hours <= 168:
        return 1
    return 0


def _when_match_score(meeting_when: str | None, event_when: str | None) -> int:
    if not meeting_when or not event_when:
        return 0
    target_dt = _parse_datetime(meeting_when)
    event_dt = _parse_datetime(event_when)
    if target_dt and event_dt:
        delta_minutes = abs(_timestamp(target_dt) - _timestamp(event_dt)) / 60
        if delta_minutes <= 5:
            return 5
        if delta_minutes <= 180:
            return 3
        if target_dt.date() == event_dt.date():
            return 1
    normalized_target = _normalize(meeting_when)
    normalized_event = _normalize(event_when)
    if normalized_target in normalized_event or normalized_event in normalized_target:
        return 2
    return 0


def _is_generic_title(title: str) -> bool:
    normalized = _normalize(title).replace(" ", "")
    return any(marker in normalized for marker in _GENERIC_TITLES)


def _has_agenda(event: _PreparedEvent) -> bool:
    return len(event.description.strip()) >= 18


def _render_bullets(items: list[str], *, empty_message: str) -> list[str]:
    if not items:
        return [f"- {empty_message}"]
    return [f"- {item}" for item in items]


def _render_source_group(items: list[dict[str, str]], *, empty_message: str) -> list[str]:
    if not items:
        return [f"  - {empty_message}"]
    lines: list[str] = []
    for item in items:
        rendered = " | ".join(value for value in item.values() if value)
        lines.append(f"  - {rendered}")
    return lines


def _extract_keywords(text: str) -> list[str]:
    normalized = _normalize(text)
    tokens = _TOKEN_PATTERN.findall(normalized)
    return [
        token
        for token in tokens
        if token not in _STOPWORDS
        and (len(token) >= 3 or any(character.isdigit() for character in token))
    ]


def _contains_phrase(text: str, expected: str) -> bool:
    normalized_text = _normalize(text)
    normalized_expected = _normalize(expected)
    return normalized_expected in normalized_text or normalized_text in normalized_expected


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    ).lower()


def _read_time(raw: object) -> tuple[str | None, datetime | None]:
    if isinstance(raw, datetime):
        return raw.isoformat(), raw
    if isinstance(raw, str):
        stripped = raw.strip()
        return (stripped or None, _parse_datetime(stripped))
    return None, None


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _first_present_str(payload: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _coerce_people(raw: object) -> list[str]:
    if isinstance(raw, str):
        return [part.strip() for part in re.split(r"[;,]", raw) if part.strip()]
    if isinstance(raw, list):
        people: list[str] = []
        for item in raw:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    people.append(stripped)
            elif isinstance(item, dict):
                value = item.get("name") or item.get("email")
                if isinstance(value, str) and value.strip():
                    people.append(value.strip())
        return people
    return []


def _title_from_text(text: str) -> str:
    first_sentence = _first_sentence(text)
    return _compact(first_sentence or "Nota local", 60)


def _first_sentence(text: str) -> str:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", cleaned)[0]
    return sentence.rstrip(".!?")


def _compact(text: str, limit: int) -> str:
    cleaned = " ".join(text.split()).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _timestamp(value: datetime) -> float:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).timestamp()
    return value.timestamp()


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        stripped = item.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        unique_items.append(stripped)
    return unique_items
