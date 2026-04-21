#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but was not found in PATH."
  exit 1
fi

cd "${PROJECT_DIR}"
uv tool install . --reinstall

echo "Installed adv-archon from ${PROJECT_DIR}"
echo "For browser automation, run once: uv run playwright install chromium"
