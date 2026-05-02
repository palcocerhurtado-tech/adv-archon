#!/usr/bin/env bash
# =============================================================================
# build_macos.sh — Build ADV ARCHON.app for macOS (free, no signing required)
#
# Requirements:
#   uv (https://github.com/astral-sh/uv)
#   PyInstaller  →  uv pip install pyinstaller
#   PySide6      →  uv pip install PySide6 (already in pyproject extras)
#
# Usage:
#   ./scripts/build_macos.sh              # standard build → dist/ADV ARCHON.app
#   ./scripts/build_macos.sh --universal  # universal2 (Intel + Apple Silicon)
#   ./scripts/build_macos.sh --sign       # ad-hoc sign (no Apple account needed)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

APP_NAME="ADV ARCHON"
DIST_DIR="${ROOT}/dist"
SPEC_FILE="${ROOT}/archon.spec"

UNIVERSAL=false
SIGN=false
for arg in "$@"; do
  case "$arg" in
    --universal) UNIVERSAL=true ;;
    --sign)      SIGN=true ;;
  esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ADV ARCHON — macOS build"
echo " Root : ${ROOT}"
echo " Dist : ${DIST_DIR}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Ensure PyInstaller is available ────────────────────────────────────────
if ! uv run python -c "import PyInstaller" 2>/dev/null; then
  echo "→ Instalando PyInstaller…"
  uv pip install pyinstaller
fi

# ── 2. Build ──────────────────────────────────────────────────────────────────
PYINSTALLER_ARGS=(
  --clean
  --noconfirm
  --distpath "${DIST_DIR}"
  --workpath "${ROOT}/build"
)

if $UNIVERSAL; then
  echo "→ Modo universal2 (Intel + Apple Silicon)"
  PYINSTALLER_ARGS+=(--target-arch universal2)
fi

echo "→ Ejecutando PyInstaller…"
uv run pyinstaller "${PYINSTALLER_ARGS[@]}" "${SPEC_FILE}"

APP_PATH="${DIST_DIR}/${APP_NAME}.app"

if [ ! -d "${APP_PATH}" ]; then
  echo "✗ Error: no se encontró ${APP_PATH}"
  exit 1
fi

# ── 3. Optional ad-hoc sign (no Apple Developer account needed) ───────────────
if $SIGN; then
  echo "→ Firmando ad-hoc (sin cuenta Apple)…"
  codesign --force --deep --sign - "${APP_PATH}" || true
fi

# ── 4. Size report ────────────────────────────────────────────────────────────
APP_SIZE=$(du -sh "${APP_PATH}" | cut -f1)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✓  ${APP_NAME}.app  —  ${APP_SIZE}"
echo " →  ${APP_PATH}"
echo ""
echo " Para instalar:"
echo "   cp -r \"${APP_PATH}\" ~/Applications/"
echo ""
echo " Para distribuir sin Gatekeeper:"
echo "   ./scripts/build_macos.sh --sign"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
