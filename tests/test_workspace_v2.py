from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from adv_archon.core.workspace_v2 import (
    WorkspaceSnapshot,
    build_default_workspace_actions,
    build_workspace_snapshot,
    discover_generated_documents,
)


def _touch(path: Path, timestamp: float) -> Path:
    path.write_text("generated", encoding="utf-8")
    os.utime(path, (timestamp, timestamp))
    return path


def test_workspace_dataclasses_are_serializable() -> None:
    snapshot = WorkspaceSnapshot(
        actions=build_default_workspace_actions(),
        statuses=(),
        documents=(),
        recent_activity=("Sin actividad reciente",),
    )

    payload = snapshot.to_dict()

    assert asdict(snapshot)["actions"][0]["id"] == "new-expediente"
    assert payload["actions"][1]["title"] == "Research Workbench"
    assert payload["recent_activity"] == ["Sin actividad reciente"]


def test_discover_generated_documents_filters_and_orders_by_updated_at(
    tmp_path: Path,
) -> None:
    old_doc = _touch(tmp_path / "adv_archon_informe.docx", 1_700_000_000)
    new_doc = _touch(tmp_path / "memoria_proyecto.pdf", 1_800_000_000)
    _touch(tmp_path / "notes.txt", 1_900_000_000)
    _touch(tmp_path / "random_contract.pdf", 1_950_000_000)

    documents = discover_generated_documents((tmp_path,))

    assert [item.path for item in documents] == [str(new_doc.resolve()), str(old_doc.resolve())]
    assert [item.kind for item in documents] == ["pdf", "docx"]
    assert documents[0].updated_at > documents[1].updated_at


def test_discover_generated_documents_respects_limit_and_nested_dirs(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "exports"
    nested.mkdir()
    newest = _touch(nested / "adv_archon_final.xlsx", 1_800_000_000)
    _touch(tmp_path / "informe_previo.pdf", 1_700_000_000)

    documents = discover_generated_documents((tmp_path, tmp_path / "missing"), limit=1)

    assert len(documents) == 1
    assert documents[0].path == str(newest.resolve())
    assert documents[0].title == "adv archon final"


def test_discover_generated_documents_bounds_scan_depth(tmp_path: Path) -> None:
    shallow = tmp_path / "exports"
    shallow.mkdir()
    deep = shallow / "nested" / "too_deep"
    deep.mkdir(parents=True)
    _touch(shallow / "adv_archon_visible.pdf", 1_800_000_000)
    _touch(deep / "adv_archon_hidden.pdf", 1_900_000_000)

    documents = discover_generated_documents((tmp_path,), max_depth=1)

    assert [Path(item.path).name for item in documents] == ["adv_archon_visible.pdf"]


def test_build_workspace_snapshot_includes_status_documents_and_activity(
    tmp_path: Path,
) -> None:
    _touch(tmp_path / "adv_archon_expediente.pdf", 1_800_000_000)

    snapshot = build_workspace_snapshot(
        (tmp_path,),
        engine_status="Listo",
        ollama_model="qwen2.5:7b",
        last_expediente="Cambio de uso",
    )

    assert [action.id for action in snapshot.actions] == [
        "new-expediente",
        "research-workbench",
        "generated-documents",
        "system-status",
        "recent-activity",
        "quick-actions",
    ]
    assert snapshot.statuses[0].to_dict() == {
        "label": "Motor",
        "value": "Listo",
        "status": "ok",
    }
    assert snapshot.statuses[1].value == "qwen2.5:7b"
    assert snapshot.statuses[2].value == "1"
    assert snapshot.statuses[3].value == "Cambio de uso"
    assert snapshot.recent_activity[0] == "Expediente activo: Cambio de uso"
    assert snapshot.recent_activity[1].startswith("Documento actualizado:")
