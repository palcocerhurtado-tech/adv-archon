#!/bin/bash
cd "$(dirname "$0")"
uv sync --extra desktop -q 2>/dev/null || true
export PYTHONPATH="$(pwd)/src"
export QT_QPA_PLATFORM_PLUGIN_PATH="$(uv run python -c "import PySide6, os; print(os.path.join(os.path.dirname(PySide6.__file__), 'Qt', 'plugins', 'platforms'))" 2>/dev/null)"
PYTHONPATH="$(pwd)/src" uv run adv-archon-desktop
