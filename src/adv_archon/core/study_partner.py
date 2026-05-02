from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePath

DEFAULT_SUMMARY_SENTENCES = 3
DEFAULT_KEY_IDEA_LIMIT = 5
DEFAULT_REVIEW_QUESTION_LIMIT = 5
DEFAULT_STUDY_MINUTES = 20

FALLBACK_SUMMARY = "No hay contenido suficiente para generar un resumen."
FALLBACK_TITLE = "Study note"

__all__ = [
    "FALLBACK_SUMMARY",
    "ReviewQuestion",
    "StudyNote",
    "StudyPartnerGuide",
    "StudyPlanStep",
    "build_review_questions",
    "build_short_study_plan",
    "build_study_note",
    "build_study_packet",
    "build_study_partner_guide",
    "build_study_summary",
    "extract_key_ideas",
]

_WORD_RE = re.compile(r"[^\W_][\w'-]*", re.UNICODE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s*")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s*")
_STOPWORDS = frozenset(
    {
        "a",
        "al",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "con",
        "como",
        "de",
        "del",
        "despues",
        "do",
        "el",
        "en",
        "es",
        "esta",
        "este",
        "for",
        "from",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "la",
        "las",
        "lo",
        "los",
        "mas",
        "of",
        "or",
        "para",
        "por",
        "que",
        "se",
        "sin",
        "so",
        "su",
        "sus",
        "the",
        "their",
        "this",
        "to",
        "una",
        "uno",
        "un",
        "y",
    }
)
_COMMON_VERBS = frozenset(
    {
        "address",
        "allow",
        "allows",
        "ayuda",
        "ayudan",
        "can",
        "combina",
        "combine",
        "combines",
        "define",
        "defines",
        "debe",
        "deben",
        "describe",
        "describes",
        "enable",
        "enables",
        "explica",
        "explain",
        "explains",
        "helps",
        "improve",
        "improves",
        "include",
        "includes",
        "keep",
        "keeps",
        "measure",
        "measures",
        "need",
        "needs",
        "permite",
        "reduce",
        "reduces",
        "requiere",
        "show",
        "shows",
        "should",
        "support",
        "supports",
        "track",
        "tracks",
        "usa",
        "use",
        "uses",
    }
)


@dataclass(frozen=True, slots=True)
class ReviewQuestion:
    prompt: str
    answer_hint: str
    source_excerpt: str

    def as_payload(self) -> dict[str, str]:
        return {
            "prompt": self.prompt,
            "answer_hint": self.answer_hint,
            "source_excerpt": self.source_excerpt,
        }


@dataclass(frozen=True, slots=True)
class StudyPlanStep:
    title: str
    minutes: int
    instructions: str

    def as_payload(self) -> dict[str, object]:
        return {
            "title": self.title,
            "minutes": self.minutes,
            "instructions": self.instructions,
        }


@dataclass(frozen=True, slots=True)
class StudyNote:
    title: str
    body: str
    format: str = "markdown"
    suggested_filename: str | None = None
    tags: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, object]:
        return {
            "title": self.title,
            "body": self.body,
            "format": self.format,
            "suggested_filename": self.suggested_filename,
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class StudyPartnerGuide:
    title: str
    objective: str | None
    word_count: int
    summary: str
    key_ideas: tuple[str, ...]
    review_questions: tuple[ReviewQuestion, ...]
    study_plan: tuple[StudyPlanStep, ...]
    note: StudyNote

    def render(self) -> str:
        lines = [f"Study partner guide | {self.title}"]
        if self.objective:
            lines.append(f"Objective: {self.objective}")
        lines.extend(["", "Resumen", self.summary, "", "Ideas clave"])
        if self.key_ideas:
            lines.extend(f"- {idea}" for idea in self.key_ideas)
        else:
            lines.append("- Sin ideas clave detectadas.")
        lines.extend(["", "Preguntas de repaso"])
        if self.review_questions:
            lines.extend(
                f"{index}. {question.prompt}\n   Pista: {question.answer_hint}"
                for index, question in enumerate(self.review_questions, start=1)
            )
        else:
            lines.append("1. No hay suficiente contenido para generar preguntas utiles.")
        lines.extend(["", "Plan corto"])
        if self.study_plan:
            lines.extend(
                f"- {step.minutes} min | {step.title}: {step.instructions}"
                for step in self.study_plan
            )
        else:
            lines.append("- Sin plan sugerido: hace falta mas contenido fuente.")
        lines.extend(["", "Nota lista para guardar", self.note.body])
        return "\n".join(lines)

    def as_payload(self) -> dict[str, object]:
        return {
            "title": self.title,
            "objective": self.objective,
            "word_count": self.word_count,
            "summary": self.summary,
            "key_ideas": list(self.key_ideas),
            "review_questions": [question.as_payload() for question in self.review_questions],
            "study_plan": [step.as_payload() for step in self.study_plan],
            "note": self.note.as_payload(),
        }


def build_study_summary(text: str, *, max_sentences: int = DEFAULT_SUMMARY_SENTENCES) -> str:
    cleaned_text = _normalize_text(text)
    if not cleaned_text:
        return FALLBACK_SUMMARY

    sentences = _candidate_sentences(cleaned_text)
    if not sentences:
        return _clip_text(cleaned_text, max_chars=240)

    limit = max(1, max_sentences)
    selected = _select_salient_sentences(sentences, limit=limit)
    if not selected:
        return _clip_text(cleaned_text, max_chars=240)
    return " ".join(selected)


def extract_key_ideas(text: str, *, limit: int = DEFAULT_KEY_IDEA_LIMIT) -> tuple[str, ...]:
    cleaned_text = _normalize_text(text)
    if not cleaned_text:
        return ()

    target = max(1, limit)
    bullet_ideas = _unique_items(_bullet_candidates(text))
    if bullet_ideas:
        return tuple(_clip_text(idea, max_chars=160) for idea in bullet_ideas[:target])

    sentences = _select_salient_sentences(_candidate_sentences(cleaned_text), limit=target * 2)
    ideas = [_clip_text(sentence, max_chars=160) for sentence in sentences]
    return tuple(_unique_items(ideas)[:target])


def build_review_questions(
    text: str,
    *,
    limit: int = DEFAULT_REVIEW_QUESTION_LIMIT,
) -> tuple[ReviewQuestion, ...]:
    cleaned_text = _normalize_text(text)
    if not cleaned_text:
        return ()

    target = max(1, limit)
    candidates = _bullet_candidates(text) or _select_salient_sentences(
        _candidate_sentences(cleaned_text),
        limit=target * 2,
    )

    questions: list[ReviewQuestion] = []
    seen_prompts: set[str] = set()
    for index, candidate in enumerate(candidates):
        topic = _topic_from_sentence(candidate)
        prompt = _question_prompt(topic, index)
        if prompt in seen_prompts:
            continue
        seen_prompts.add(prompt)
        questions.append(
            ReviewQuestion(
                prompt=prompt,
                answer_hint=_clip_text(candidate, max_chars=180),
                source_excerpt=_clip_text(candidate, max_chars=220),
            )
        )
        if len(questions) >= target:
            break
    return tuple(questions)


def build_short_study_plan(
    text: str,
    *,
    total_minutes: int = DEFAULT_STUDY_MINUTES,
    objective: str | None = None,
) -> tuple[StudyPlanStep, ...]:
    cleaned_text = _normalize_text(text)
    if not cleaned_text:
        return ()

    summary = build_study_summary(cleaned_text, max_sentences=2)
    key_ideas = extract_key_ideas(cleaned_text, limit=3)
    review_questions = build_review_questions(cleaned_text, limit=3)
    minutes = _allocate_minutes(max(8, total_minutes))
    key_focus = (
        "; ".join(key_ideas[:3]) if key_ideas else "repasa los conceptos repetidos en el texto"
    )
    question_focus = "; ".join(question.prompt for question in review_questions[:2])

    return (
        StudyPlanStep(
            title="Panorama",
            minutes=minutes[0],
            instructions=_append_objective(
                f"Lee el resumen y detecta la idea central: {summary}",
                objective,
            ),
        ),
        StudyPlanStep(
            title="Ideas clave",
            minutes=minutes[1],
            instructions=_append_objective(
                f"Repasa y conecta estas ideas: {key_focus}.",
                objective,
            ),
        ),
        StudyPlanStep(
            title="Autoevaluacion",
            minutes=minutes[2],
            instructions=(
                "Responde sin mirar el texto. "
                + (
                    f"Empieza por: {question_focus}"
                    if question_focus
                    else "Formula dos preguntas con tus palabras."
                )
            ),
        ),
        StudyPlanStep(
            title="Cierre",
            minutes=minutes[3],
            instructions=_append_objective(
                "Actualiza una nota final con 2 aprendizajes, 1 duda abierta y el proximo repaso.",
                objective,
            ),
        ),
    )


def build_study_note(
    text: str,
    *,
    title: str | None = None,
    objective: str | None = None,
    summary: str | None = None,
    key_ideas: tuple[str, ...] | None = None,
    review_questions: tuple[ReviewQuestion, ...] | None = None,
    study_plan: tuple[StudyPlanStep, ...] | None = None,
) -> StudyNote:
    resolved_title = _resolve_title(text, title=title, source_name=None)
    resolved_summary = summary or build_study_summary(text)
    resolved_key_ideas = key_ideas if key_ideas is not None else extract_key_ideas(text)
    resolved_questions = (
        review_questions if review_questions is not None else build_review_questions(text)
    )
    resolved_plan = (
        study_plan if study_plan is not None else build_short_study_plan(text, objective=objective)
    )
    tags = _derive_tags(text)

    note_lines = [f"# {resolved_title}", ""]
    if objective and objective.strip():
        note_lines.extend([f"Objective: {objective.strip()}", ""])

    note_lines.extend(["## Resumen", resolved_summary, "", "## Ideas clave"])
    if resolved_key_ideas:
        note_lines.extend(f"- {idea}" for idea in resolved_key_ideas)
    else:
        note_lines.append("- Sin ideas clave detectadas.")

    note_lines.extend(["", "## Preguntas de repaso"])
    if resolved_questions:
        note_lines.extend(
            f"{index}. {question.prompt}\n   Pista: {question.answer_hint}"
            for index, question in enumerate(resolved_questions, start=1)
        )
    else:
        note_lines.append("1. No hay suficiente contenido para generar preguntas utiles.")

    note_lines.extend(["", "## Plan corto"])
    if resolved_plan:
        note_lines.extend(
            f"- {step.minutes} min | {step.title}: {step.instructions}" for step in resolved_plan
        )
    else:
        note_lines.append("- Sin plan sugerido: hace falta mas contenido fuente.")

    return StudyNote(
        title=resolved_title,
        body="\n".join(note_lines).strip(),
        suggested_filename=f"study-{_slugify(resolved_title)}.md",
        tags=tags,
    )


def build_study_partner_guide(
    *,
    title: str,
    content: str,
    objective: str | None = None,
    total_minutes: int = DEFAULT_STUDY_MINUTES,
) -> StudyPartnerGuide:
    cleaned_text = _normalize_text(content)
    resolved_title = _resolve_title(cleaned_text, title=title, source_name=None)
    resolved_objective = _clean_fragment(objective or "") or None
    summary = build_study_summary(cleaned_text)
    key_ideas = extract_key_ideas(cleaned_text)
    review_questions = build_review_questions(cleaned_text)
    study_plan = build_short_study_plan(
        cleaned_text,
        total_minutes=total_minutes,
        objective=resolved_objective,
    )
    note = build_study_note(
        cleaned_text,
        title=resolved_title,
        objective=resolved_objective,
        summary=summary,
        key_ideas=key_ideas,
        review_questions=review_questions,
        study_plan=study_plan,
    )
    return StudyPartnerGuide(
        title=resolved_title,
        objective=resolved_objective,
        word_count=len(_tokenize(cleaned_text)),
        summary=summary,
        key_ideas=key_ideas,
        review_questions=review_questions,
        study_plan=study_plan,
        note=note,
    )


def build_study_packet(
    text: str,
    *,
    title: str | None = None,
    source_name: str | None = None,
    total_minutes: int = DEFAULT_STUDY_MINUTES,
) -> StudyPartnerGuide:
    guide_title = title or _resolve_title(text, title=None, source_name=source_name)
    return build_study_partner_guide(
        title=guide_title,
        content=text,
        objective=None,
        total_minutes=total_minutes,
    )


def _normalize_text(text: str) -> str:
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.split("\n")]
    return "\n".join(line for line in lines if line)


def _candidate_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in text.splitlines():
        if not line:
            continue
        if _looks_like_heading(line):
            continue
        normalized_line = _BULLET_RE.sub("", line).strip()
        parts = _SENTENCE_RE.split(normalized_line)
        for part in parts:
            sentence = _clean_fragment(part)
            if sentence:
                sentences.append(sentence)
    return sentences


def _select_salient_sentences(sentences: list[str], *, limit: int) -> list[str]:
    if not sentences:
        return []
    frequencies = Counter(_meaningful_tokens(" ".join(sentences)))
    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        tokens = _meaningful_tokens(sentence)
        if not tokens:
            continue
        unique_tokens = tuple(dict.fromkeys(tokens))
        keyword_score = sum(frequencies[token] for token in unique_tokens) / len(unique_tokens)
        length = len(sentence.split())
        length_bonus = 0.2 if 7 <= length <= 30 else 0.0
        position_bonus = max(0.0, 0.35 - (index * 0.05))
        punctuation_bonus = 0.1 if ":" in sentence else 0.0
        score = keyword_score + length_bonus + position_bonus + punctuation_bonus
        scored.append((score, index, sentence))
    if not scored:
        return sentences[:limit]

    top_items = sorted(scored, key=lambda item: (-item[0], item[1]))[: max(1, limit)]
    selected_indexes = {index for _score, index, _sentence in top_items}
    ordered = [sentences[index] for index in range(len(sentences)) if index in selected_indexes]
    return _unique_items(ordered)[:limit]


def _bullet_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for line in text.splitlines():
        if not _BULLET_RE.match(line):
            continue
        cleaned = _clean_fragment(_BULLET_RE.sub("", line))
        if cleaned:
            candidates.append(cleaned)
    return candidates


def _question_prompt(topic: str, index: int) -> str:
    templates = (
        "Que debes recordar sobre {topic}?",
        "Como explicarias {topic} con tus palabras?",
        "Por que importa {topic} dentro del material?",
        "Que problema o necesidad aborda {topic}?",
        "Como se conecta {topic} con el resto del documento?",
    )
    return templates[index % len(templates)].format(topic=topic)


def _topic_from_sentence(sentence: str) -> str:
    meaningful = [
        token
        for token in _tokenize(sentence)
        if _normalize_token(token) not in _STOPWORDS
        and _normalize_token(token) not in _COMMON_VERBS
    ]
    if meaningful:
        return " ".join(meaningful[:4])
    fallback = _tokenize(sentence)
    if fallback:
        return " ".join(fallback[:4])
    return "este material"


def _resolve_title(text: str, *, title: str | None, source_name: str | None) -> str:
    if title and title.strip():
        return _clip_text(title.strip(), max_chars=80)
    if source_name and source_name.strip():
        source_title = (
            PurePath(source_name.strip()).stem.replace("_", " ").replace("-", " ").strip()
        )
        if source_title:
            return _clip_text(source_title, max_chars=80)
    for line in _normalize_text(text).splitlines():
        if _looks_like_heading(line):
            candidate = _clean_fragment(_HEADING_RE.sub("", line))
            if candidate:
                return _clip_text(candidate, max_chars=80)
        if 3 <= len(line.split()) <= 10:
            return _clip_text(_clean_fragment(line), max_chars=80)
    return FALLBACK_TITLE


def _derive_tags(text: str, *, limit: int = 4) -> tuple[str, ...]:
    counts = Counter(_meaningful_tokens(text))
    if not counts:
        return ()
    tags = [token for token, _count in counts.most_common(limit)]
    return tuple(tags)


def _allocate_minutes(total_minutes: int) -> tuple[int, int, int, int]:
    weights = (0.2, 0.4, 0.25, 0.15)
    raw = [total_minutes * weight for weight in weights]
    minutes = [max(1, int(value)) for value in raw]
    assigned = sum(minutes)
    order = sorted(
        range(len(raw)),
        key=lambda index: (raw[index] - int(raw[index]), -index),
        reverse=True,
    )
    order_index = 0
    while assigned < total_minutes:
        slot = order[order_index % len(order)]
        minutes[slot] += 1
        assigned += 1
        order_index += 1
    while assigned > total_minutes:
        for slot in reversed(order):
            if minutes[slot] > 1:
                minutes[slot] -= 1
                assigned -= 1
                if assigned == total_minutes:
                    break
    return minutes[0], minutes[1], minutes[2], minutes[3]


def _meaningful_tokens(text: str) -> list[str]:
    tokens = []
    for token in _tokenize(text):
        normalized = _normalize_token(token)
        if normalized in _STOPWORDS or len(normalized) <= 2:
            continue
        tokens.append(normalized)
    return tokens


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _normalize_token(token: str) -> str:
    decomposed = unicodedata.normalize("NFKD", token.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _clean_fragment(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip(" -:;\t")
    return compact.strip()


def _clip_text(text: str, *, max_chars: int) -> str:
    cleaned = _clean_fragment(text)
    if len(cleaned) <= max_chars:
        return cleaned
    clipped = cleaned[: max_chars - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return f"{clipped}..."


def _slugify(text: str) -> str:
    normalized = _normalize_token(text)
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or "study-note"


def _append_objective(text: str, objective: str | None) -> str:
    base = text.rstrip()
    if not objective or not objective.strip():
        return base
    needs_stop = not base.endswith((".", "!", "?"))
    separator = "." if needs_stop else ""
    return f"{base}{separator} Conecta todo con este objetivo: {objective.strip()}."


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _HEADING_RE.match(stripped):
        return True
    return len(stripped.split()) <= 8 and not stripped.endswith((".", "!", "?"))


def _unique_items(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = _normalize_token(re.sub(r"[^0-9A-Za-z]+", " ", item))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
