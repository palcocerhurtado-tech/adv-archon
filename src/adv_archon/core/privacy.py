from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b", re.IGNORECASE)
SPANISH_ID_RE = re.compile(r"\b(?:\d{8}[A-Z]|[XYZ]\d{7}[A-Z])\b", re.IGNORECASE)


@dataclass(slots=True)
class RedactionResult:
    text: str
    replacements: dict[str, str]
    items: int


class PIIRedactor:
    def __init__(self) -> None:
        self._patterns = (
            ("EMAIL", EMAIL_RE),
            ("PHONE", PHONE_RE),
            ("IBAN", IBAN_RE),
            ("SPANISH_ID", SPANISH_ID_RE),
        )

    def redact_text(self, text: str) -> RedactionResult:
        session = PIIRedactionSession(self)
        redacted = session.redact(text)
        return RedactionResult(
            text=redacted,
            replacements=dict(session.replacements),
            items=len(session.replacements),
        )

    def restore_text(self, text: str, replacements: dict[str, str]) -> str:
        restored = text
        for placeholder, original in replacements.items():
            restored = restored.replace(placeholder, original)
        return restored


class PIIRedactionSession:
    def __init__(self, redactor: PIIRedactor) -> None:
        self._redactor = redactor
        self.replacements: dict[str, str] = {}
        self._reverse_lookup: dict[str, str] = {}
        self._counters = {label: 0 for label, _ in redactor._patterns}

    def redact(self, text: str) -> str:
        redacted = text
        for label, pattern in self._redactor._patterns:
            redacted = pattern.sub(self._build_replacer(label), redacted)
        return redacted

    def restore(self, text: str) -> str:
        return self._redactor.restore_text(text, self.replacements)

    def _build_replacer(self, label: str) -> Callable[[re.Match[str]], str]:
        def replacer(match: re.Match[str]) -> str:
            original = match.group(0)
            if original in self._reverse_lookup:
                return self._reverse_lookup[original]
            self._counters[label] += 1
            placeholder = f"__PII_{label}_{self._counters[label]}__"
            self._reverse_lookup[original] = placeholder
            self.replacements[placeholder] = original
            return placeholder

        return replacer
