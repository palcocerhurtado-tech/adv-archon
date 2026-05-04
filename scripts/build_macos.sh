#!/usr/bin/env bash
# =============================================================================
# build_macos.sh — Build ADV ARCHON.app + DMG for macOS (coste cero)
#
# Requisitos:
#   uv  (https://astral.sh/uv)
#
# No requiere:
#   - Apple Developer Program
#   - Notarización
#   - PyInstaller ni dependencias adicionales
#
# El .app se genera con el bundler nativo (bundle.py) que ya forma parte
# del propio paquete adv-archon. El DMG se crea con hdiutil, incluido en macOS.
#
# Uso:
#   ./scripts/build_macos.sh               # build estándar → dist/
#   ./scripts/build_macos.sh --sign        # firma ad-hoc (recomendado)
#   ./scripts/build_macos.sh --dmg         # crea también .dmg
#   ./scripts/build_macos.sh --sign --dmg  # firma + dmg
#   ./scripts/build_macos.sh --dmg --open  # abre el DMG al terminar
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

APP_NAME="ADV ARCHON"
DIST_DIR="${ROOT}/dist"
APP_PATH="${DIST_DIR}/${APP_NAME}.app"
DMG_PATH="${DIST_DIR}/${APP_NAME}.dmg"

SIGN=false
MAKE_DMG=false
OPEN_DMG=false
for arg in "$@"; do
  case "$arg" in
    --sign)    SIGN=true ;;
    --dmg)     MAKE_DMG=true ;;
    --open)    OPEN_DMG=true ;;
  esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ADV ARCHON — build macOS"
echo " Root : ${ROOT}"
echo " Dist : ${DIST_DIR}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mkdir -p "${DIST_DIR}"

# ── 1. Instalar el paquete en modo editable si es necesario ──────────────────
if ! uv run python -c "import adv_archon" 2>/dev/null; then
  echo "→ Instalando adv-archon…"
  uv pip install -e ".[desktop]"
fi

# ── 2. Generar ADV ARCHON.app con el bundler nativo ──────────────────────────
echo "→ Generando ${APP_NAME}.app…"
uv run adv-archon desktop-bundle "${DIST_DIR}"

if [ ! -d "${APP_PATH}" ]; then
  echo "✗ Error: no se generó ${APP_PATH}"
  exit 1
fi

# ── 3. Quitar cuarentena (permite abrir desde Finder sin aviso xattr) ─────────
echo "→ Eliminando atributos de cuarentena…"
xattr -cr "${APP_PATH}" 2>/dev/null || true

# ── 4. Firma ad-hoc (no requiere cuenta Apple) ───────────────────────────────
if $SIGN; then
  if command -v codesign &>/dev/null; then
    echo "→ Firmando con firma ad-hoc (codesign -s -)…"
    codesign --force --deep --sign - "${APP_PATH}" && \
      echo "  ✓ Firmado ad-hoc correctamente." || \
      echo "  ⚠ codesign falló — la app funciona igual, pero Gatekeeper puede avisar."
  else
    echo "  ⚠ codesign no disponible — omitiendo firma."
  fi
fi

# ── 5. Crear DMG con hdiutil (incluido en macOS) ─────────────────────────────
if $MAKE_DMG; then
  echo "→ Creando ${APP_NAME}.dmg…"

  STAGING="$(mktemp -d)"
  trap 'rm -rf "${STAGING}"' EXIT

  cp -r "${APP_PATH}" "${STAGING}/"
  ln -sf /Applications "${STAGING}/Aplicaciones"

  hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "${STAGING}" \
    -ov \
    -format UDZO \
    "${DMG_PATH}" \
    -quiet

  echo "  ✓ DMG creado: ${DMG_PATH}"

  if $OPEN_DMG; then
    open "${DMG_PATH}"
  fi
fi

# ── 6. Resumen final ──────────────────────────────────────────────────────────
APP_SIZE=$(du -sh "${APP_PATH}" 2>/dev/null | cut -f1 || echo "?")
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✓  ${APP_NAME}.app  —  ${APP_SIZE}"
echo " →  ${APP_PATH}"
if $MAKE_DMG && [ -f "${DMG_PATH}" ]; then
  DMG_SIZE=$(du -sh "${DMG_PATH}" 2>/dev/null | cut -f1 || echo "?")
  echo " ✓  ${APP_NAME}.dmg  —  ${DMG_SIZE}"
  echo " →  ${DMG_PATH}"
fi
echo ""
echo " Cómo distribuir:"
echo "   - Envía el .dmg al arquitecto"
echo "   - Instrúyele que arrastre la app a Aplicaciones o Escritorio"
echo "   - Si macOS bloquea: Ajustes → Privacidad → Abrir de todos modos"
echo "   - O por terminal: xattr -dr com.apple.quarantine \"${APP_PATH}\""
echo ""
echo " Leer docs/DISTRIBUCION_MACOS.md para la guía completa."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
