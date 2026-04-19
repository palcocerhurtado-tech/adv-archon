#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but was not found in PATH."
  exit 1
fi

uv tool uninstall adv-archon
echo "Removed adv-archon"

