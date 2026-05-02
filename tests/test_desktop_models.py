from __future__ import annotations

from pathlib import Path

from adv_archon.desktop.models import DesktopChatRequest, collect_attachments, format_bytes


def test_collect_attachments_deduplicates_paths(tmp_path: Path) -> None:
    report = tmp_path / "report.pdf"
    report.write_bytes(b"pdf-data")

    attachments = collect_attachments([report, report, Path(str(report))])

    assert len(attachments) == 1
    assert attachments[0].display_name == "report.pdf"
    assert attachments[0].kind == "document"


def test_attachment_summary_includes_size_for_files(tmp_path: Path) -> None:
    image = tmp_path / "diagram.png"
    image.write_bytes(b"1234567890")

    attachment = collect_attachments([image])[0]

    assert attachment.kind == "image"
    assert "10 B" in attachment.summary()


def test_chat_request_flags_empty_state() -> None:
    empty_request = DesktopChatRequest(prompt="   ")
    populated_request = DesktopChatRequest(prompt="", attachments=tuple())
    attachment_request = DesktopChatRequest(
        prompt="",
        attachments=tuple(collect_attachments([Path("/tmp/non-existent.txt")])),
    )

    assert empty_request.is_empty is True
    assert populated_request.is_empty is True
    assert attachment_request.is_empty is False


def test_format_bytes_scales_large_values() -> None:
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(5 * 1024 * 1024) == "5.0 MB"
