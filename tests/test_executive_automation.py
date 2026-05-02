from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from adv_archon.core.executive_automation import (
    build_executive_automation_bundle,
    install_executive_automation,
    list_executive_automation_presets,
)
from adv_archon.core.tasks import TaskStore


def test_executive_automation_bundle_contains_expected_workflows() -> None:
    bundle = build_executive_automation_bundle(study_focus="grimorios")

    assert bundle.key == "executive_assistant"
    assert [workflow.key for workflow in bundle.launch_workflows] == [
        "morning_briefing",
        "meeting_prep",
        "gmail_triage",
        "nightly_review",
    ]
    assert [template.key for template in bundle.task_templates] == ["study_review"]
    assert "grimorios" in bundle.task_templates[0].prompt


def test_install_executive_automation_materializes_launch_agents_and_task(tmp_path: Path) -> None:
    store = TaskStore(
        tmp_path / "tasks.db",
        timezone_name="Europe/Madrid",
        notifications_enabled=False,
    )
    bundle = build_executive_automation_bundle(
        morning_time="07:30",
        triage_times=("09:15", "17:45"),
        study_time="20:00",
        nightly_review_time="22:10",
        study_focus="simbolismo",
        meeting_prep_window_minutes=60,
        meeting_prep_poll_minutes=20,
    )

    installed = install_executive_automation(
        store=store,
        adv_command="/Users/pabloalcocer/.local/bin/adv",
        bundle=bundle,
        launch_agents_dir=tmp_path / "LaunchAgents",
        logs_dir=tmp_path / "logs",
        reference_time=datetime(2026, 4, 28, 8, 0, tzinfo=UTC),
        load_launch_agents=False,
    )

    assert len(installed.launch_agents) == 4
    assert len(installed.tasks) == 1
    assert installed.tasks[0].category == "study"
    assert installed.tasks[0].source == "automation:executive_assistant:study_review"
    assert installed.tasks[0].metadata == {
        "bundle": "executive_assistant",
        "preset": "study_review",
        "focus": "simbolismo",
        "kind": "study_review",
    }
    assert installed.launch_agents[1].start_interval == 20 * 60
    assert installed.launch_agents[0].plist_path.exists()
    assert installed.launch_agents[2].stdout_path is not None


def test_list_executive_automation_presets_renders_summary() -> None:
    presets = list_executive_automation_presets()

    assert len(presets) == 1
    assert presets[0]["bundle_key"] == "executive_assistant"
    assert presets[0]["launch_workflows"][0]["key"] == "morning_briefing"
