from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_desktop_app_import_avoids_llm_and_warmup_modules() -> None:
    script = """
import importlib
import json
import sys

importlib.import_module("adv_archon.desktop.app")
blocked = [
    "adv_archon.core.config",
    "adv_archon.core.llm",
    "adv_archon.desktop.warmup_agent",
    "adv_archon.integrations.gemini",
    "adv_archon.integrations.ollama",
    "httpx",
]
print(json.dumps({name: name in sys.modules for name in blocked}))
"""
    project_src = Path(__file__).resolve().parents[1] / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_src)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        env=env,
        text=True,
        check=True,
    )
    loaded = json.loads(completed.stdout)
    assert loaded == {
        "adv_archon.core.llm": False,
        "adv_archon.core.config": False,
        "adv_archon.desktop.warmup_agent": False,
        "adv_archon.integrations.gemini": False,
        "adv_archon.integrations.ollama": False,
        "httpx": False,
    }


def test_desktop_pgou_and_geo_nav_do_not_require_llm_prompt() -> None:
    source = Path("src/adv_archon/desktop/app.py").read_text(encoding="utf-8")
    assert "runtime.compliance_tools" not in source
    geo_block = source.split("def _send_geo_prompt", 1)[1].split(
        "# ── Mode / profile",
        1,
    )[0]
    assert "self._submit_prompt()" not in geo_block
    assert "self._add_message_bubble" in geo_block
