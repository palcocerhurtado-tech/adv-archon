from __future__ import annotations


def parse_live_turns(text: str, *, default: int = 3, maximum: int = 20) -> int | None:
    """Return the number of voice turns requested by a desktop /live command."""
    parts = text.strip().split()
    if not parts or parts[0].casefold() != "/live":
        return None
    if len(parts) == 1:
        return default
    if len(parts) > 2:
        raise ValueError("Uso: /live [número_de_turnos]")
    try:
        requested = int(parts[1])
    except ValueError as exc:
        raise ValueError("Uso: /live [número_de_turnos]") from exc
    return max(1, min(maximum, requested))
