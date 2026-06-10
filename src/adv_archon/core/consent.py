"""First-run consent state — headless, PySide6-free.

Persists a JSON stamp at ``<data_dir>/consent.json`` when the user accepts
the legal terms.  Provides the shared truth consumed by both the CLI and the
desktop gate.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

_CONSENT_FILENAME = "consent.json"
_REQUIRED_VERSION = "2026.1"


def _consent_path(data_dir: Path) -> Path:
    return data_dir / _CONSENT_FILENAME


def is_consent_accepted(data_dir: Path) -> bool:
    """Return True if the user has already accepted the current legal version."""
    path = _consent_path(data_dir)
    if not path.exists():
        return False
    try:
        stamp = json.loads(path.read_text(encoding="utf-8"))
        return stamp.get("legal_version") == _REQUIRED_VERSION and bool(stamp.get("accepted"))
    except (OSError, json.JSONDecodeError, ValueError):
        return False


def mark_consent_accepted(data_dir: Path) -> None:
    """Persist acceptance of the current legal version with a UTC timestamp."""
    data_dir.mkdir(parents=True, exist_ok=True)
    stamp = {
        "accepted": True,
        "legal_version": _REQUIRED_VERSION,
        "accepted_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
    }
    _consent_path(data_dir).write_text(
        json.dumps(stamp, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def reset_consent(data_dir: Path) -> None:
    """Remove stored consent — triggers the gate again on next launch."""
    path = _consent_path(data_dir)
    if path.exists():
        path.unlink()
