from pathlib import Path

from adv_archon.core.attachments import (
    format_prompt_with_attachments,
    normalize_attachment_paths,
)


def test_normalize_attachment_paths_deduplicates_and_expands() -> None:
    normalized = normalize_attachment_paths(
        ["~/Desktop/demo.txt", "~/Desktop/demo.txt", Path("/tmp/readme.md")]
    )

    assert normalized[0] == Path.home() / "Desktop" / "demo.txt"
    assert normalized[1] == Path("/tmp/readme.md")
    assert len(normalized) == 2


def test_format_prompt_with_attachments_appends_block() -> None:
    prompt = format_prompt_with_attachments(
        "resume esto",
        ["~/Desktop/demo.txt", "/tmp/readme.md"],
    )

    assert prompt.startswith("resume esto")
    assert "Adjuntos disponibles:" in prompt
    assert str(Path.home() / "Desktop" / "demo.txt") in prompt
    assert "/tmp/readme.md" in prompt
