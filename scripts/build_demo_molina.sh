#!/usr/bin/env bash
# =============================================================================
# build_demo_molina.sh — paquete demo Molina de Aragón
#
# Genera:
#   dist/ADV_ARCHON_MOLINA_DE_ARAGON_DEMO.zip
#
# Contenido:
#   ADV_ARCHON_MOLINA_DE_ARAGON_DEMO/
#     ADV ARCHON Molina Demo.app
#     Instalar ADV ARCHON Molina.command
#     README_DEMO_MOLINA.txt
#     docs/
#     pgou/molina-de-aragon/
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

DIST_DIR="${ROOT}/dist"
WORK_DIR="${DIST_DIR}/molina-demo"
PAYLOAD_DIR="${WORK_DIR}/ADV_ARCHON_MOLINA_DE_ARAGON_DEMO"
ZIP_PATH="${DIST_DIR}/ADV_ARCHON_MOLINA_DE_ARAGON_DEMO.zip"
APP_NAME="ADV ARCHON Molina Demo"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ADV ARCHON — Demo Molina de Aragón"
echo " Root : ${ROOT}"
echo " Zip  : ${ZIP_PATH}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

rm -rf "${PAYLOAD_DIR}" "${ZIP_PATH}"
mkdir -p "${PAYLOAD_DIR}/docs"

echo "→ Generando .app demo con código fuente embebido…"
PYTHONPATH=src uv run python -c \
"from pathlib import Path
from adv_archon.desktop.bundle import create_macos_app_bundle
create_macos_app_bundle(
    destination_dir=Path('${PAYLOAD_DIR}'),
    app_name='${APP_NAME}',
    bundle_identifier='com.advarchon.desktop.molina-demo',
    project_root=Path('${ROOT}'),
    embed_project=True,
)"

PYTHONPATH=src uv run python -c \
"from pathlib import Path
launcher = Path('${PAYLOAD_DIR}/${APP_NAME}.app/Contents/Resources/launch-adv-archon.sh')
text = launcher.read_text(encoding='utf-8')
marker = 'export PYTHONPATH=\"\$PROJECT_ROOT/src:\$PYTHONPATH\"'
injection = 'export ADV_ARCHON_HOME=\"\$HOME/.adv-archon-molina-demo\"\\n' + marker
if 'ADV_ARCHON_HOME=\"\$HOME/.adv-archon-molina-demo\"' not in text:
    text = text.replace(marker, injection)
launcher.write_text(text, encoding='utf-8')
"

echo "→ Generando catálogo local y expediente demo Molina…"
PYTHONPATH=src uv run python -c \
"from pathlib import Path
from adv_archon.core.demo import create_molina_de_aragon_demo
from adv_archon.core.expediente import ExpedienteStore
from adv_archon.core.pgou_store import PGOUStore

payload = Path('${PAYLOAD_DIR}')
home = payload / 'ADV_ARCHON_HOME'
home.mkdir(parents=True, exist_ok=True)
pgou_store = PGOUStore(home / 'pgou.db')
exp_store = ExpedienteStore(home / 'expedientes.db')
create_molina_de_aragon_demo(exp_store, data_dir=home, pgou_store=pgou_store)
"

cp docs/demo-molina-de-aragon.md "${PAYLOAD_DIR}/docs/"
cp docs/pgou-molina-de-aragon.md "${PAYLOAD_DIR}/docs/"
cp -R "${PAYLOAD_DIR}/ADV_ARCHON_HOME/pgou" "${PAYLOAD_DIR}/pgou"

cat > "${PAYLOAD_DIR}/README_DEMO_MOLINA.txt" <<'README_EOF'
ADV ARCHON — Demo Molina de Aragón

Qué contiene
- ADV ARCHON Molina Demo.app
- Catálogo local preliminar de Molina de Aragón
- Expediente demo: Consulta urbanística — Molina de Aragón
- Documentación de demo y fuentes oficiales

Cómo abrir
1. Descomprime el ZIP completo.
2. Haz doble clic en “Instalar ADV ARCHON Molina.command”.
3. El instalador copiará la app a ~/Applications y preparará el acceso directo.

Qué enseñar
1. Abrir el expediente demo de Molina de Aragón.
2. Revisar el bloque de planeamiento aplicable.
3. Mostrar que ARCHON usa Normas Subsidiarias, no PGOU ordinario.
4. Exportar el informe y señalar la advertencia: la ordenanza exacta requiere cruce con planos o validación municipal.

Fuentes oficiales principales
- Ayuntamiento de Molina de Aragón — Urbanismo:
  https://molinadearagon.es/ayuntamiento/urbanismo/
- LOTAU Castilla-La Mancha, Decreto Legislativo 1/2023:
  https://www.boe.es/buscar/act.php?id=DOCM-q-2023-90054
- Portal urbanístico Castilla-La Mancha:
  https://vivienda.castillalamancha.es/node/397

Aviso
Esta demo es preliminar, no vinculante y no sustituye revisión técnica municipal ni criterio profesional.
README_EOF

cat > "${PAYLOAD_DIR}/Instalar ADV ARCHON Molina.command" <<'INSTALLER_EOF'
#!/bin/zsh
set -e

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SRC="${PACKAGE_DIR}/ADV ARCHON Molina Demo.app"
INSTALL_DIR="${HOME}/Applications"
APP_DST="${INSTALL_DIR}/ADV ARCHON Molina Demo.app"
DEMO_HOME="${HOME}/.adv-archon-molina-demo"
MODEL="llama3.2:3b"
LOG_FILE="${DEMO_HOME}/install.log"

mkdir -p "${DEMO_HOME}"
exec > >(tee -a "$LOG_FILE") 2>&1

clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ADV ARCHON — instalador demo Molina de Aragón"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

fail_dialog() {
  osascript -e "display alert \"ADV ARCHON Molina\" message \"$1\" as critical" >/dev/null 2>&1 || true
  echo "ERROR: $1"
  echo "Log: $LOG_FILE"
  echo "Pulsa Enter para cerrar."
  read -r _
  exit 1
}

[ -d "$APP_SRC" ] || fail_dialog "No encuentro ADV ARCHON Molina Demo.app junto al instalador."

mkdir -p "$INSTALL_DIR"
rm -rf "$APP_DST"
ditto "$APP_SRC" "$APP_DST"
xattr -dr com.apple.quarantine "$APP_DST" 2>/dev/null || true

if [ -d "$PACKAGE_DIR/ADV_ARCHON_HOME" ]; then
  ditto "$PACKAGE_DIR/ADV_ARCHON_HOME" "$DEMO_HOME"
fi

for UV in "$HOME/.cargo/bin/uv" "/opt/homebrew/bin/uv" "/usr/local/bin/uv" "$(command -v uv 2>/dev/null)"; do
  [ -x "$UV" ] && break
done
if [ ! -x "$UV" ]; then
  fail_dialog "No se encontró uv. Instálalo con: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

PROJECT_ROOT="$APP_DST/Contents/Resources/adv-archon-source"
cd "$PROJECT_ROOT"
"$UV" sync --extra desktop --reinstall-package python-dotenv --reinstall-package PySide6 --reinstall-package PySide6-Addons --reinstall-package PySide6-Essentials --reinstall-package shiboken6

OLLAMA_BIN="$(command -v ollama 2>/dev/null || true)"
if [ -z "$OLLAMA_BIN" ] && [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]; then
  OLLAMA_BIN="/Applications/Ollama.app/Contents/Resources/ollama"
fi
if [ -n "$OLLAMA_BIN" ]; then
  open -a Ollama >/dev/null 2>&1 || true
  sleep 2
  if ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    "$OLLAMA_BIN" serve >/tmp/adv-archon-molina-ollama.log 2>&1 &
    sleep 3
  fi
  if curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    if ! "$OLLAMA_BIN" list | awk '{print $1}' | grep -qx "$MODEL"; then
      "$OLLAMA_BIN" pull "$MODEL"
    fi
  fi
fi

rm -rf "$HOME/Desktop/ADV ARCHON Molina Demo.app"
ln -s "$APP_DST" "$HOME/Desktop/ADV ARCHON Molina Demo.app"

echo "Instalación completada. Abriendo demo..."
ADV_ARCHON_HOME="$DEMO_HOME" open "$APP_DST"
INSTALLER_EOF
chmod +x "${PAYLOAD_DIR}/Instalar ADV ARCHON Molina.command"

echo "→ Empaquetando ZIP…"
mkdir -p "${DIST_DIR}"
(
  cd "${WORK_DIR}"
  zip -qr "${ZIP_PATH}" "ADV_ARCHON_MOLINA_DE_ARAGON_DEMO"
)

echo "✓ Demo generada: ${ZIP_PATH}"
