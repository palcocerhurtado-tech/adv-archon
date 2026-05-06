#!/usr/bin/env bash
# =============================================================================
# build_beta_package.sh — paquete beta coste 0 para testers no técnicos
#
# Genera:
#   dist/ADV_ARCHON_BETA.zip
#
# Contenido del ZIP:
#   ADV_ARCHON_BETA/
#     ADV ARCHON.app
#     Instalar ADV ARCHON.command
#     README_PROBADORES.pdf
#     README_PROBADORES.txt
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

APP_NAME="ADV ARCHON"
BETA_NAME="ADV_ARCHON_BETA"
DIST_DIR="${ROOT}/dist"
WORK_DIR="${DIST_DIR}/beta"
PAYLOAD_DIR="${WORK_DIR}/${BETA_NAME}"
ZIP_PATH="${DIST_DIR}/${BETA_NAME}.zip"
README_TXT="${PAYLOAD_DIR}/README_PROBADORES.txt"
README_PDF="${PAYLOAD_DIR}/README_PROBADORES.pdf"
INSTALLER="${PAYLOAD_DIR}/Instalar ADV ARCHON.command"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ADV ARCHON — paquete beta para probadores"
echo " Root : ${ROOT}"
echo " Zip  : ${ZIP_PATH}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

rm -rf "${PAYLOAD_DIR}" "${ZIP_PATH}"
mkdir -p "${PAYLOAD_DIR}"

echo "→ Generando app con código fuente embebido…"
PYTHONPATH=src uv run python -c \
"from pathlib import Path
from adv_archon.desktop.bundle import create_macos_app_bundle
create_macos_app_bundle(
    destination_dir=Path('${PAYLOAD_DIR}'),
    project_root=Path('${ROOT}'),
    embed_project=True,
)"

cat > "${INSTALLER}" <<'INSTALLER_EOF'
#!/bin/zsh
set -e

clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ADV ARCHON — instalador beta"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SRC="${PACKAGE_DIR}/ADV ARCHON.app"
INSTALL_DIR="${HOME}/Applications"
APP_DST="${INSTALL_DIR}/ADV ARCHON.app"
MODEL="qwen2.5:7b"

fail_dialog() {
  osascript -e "display alert \"ADV ARCHON\" message \"$1\" as critical" >/dev/null 2>&1 || true
  echo "ERROR: $1"
  echo ""
  echo "Pulsa Enter para cerrar."
  read -r _
  exit 1
}

info_dialog() {
  osascript -e "display notification \"$1\" with title \"ADV ARCHON\"" >/dev/null 2>&1 || true
}

if [ ! -d "$APP_SRC" ]; then
  fail_dialog "No encuentro ADV ARCHON.app junto al instalador. Descomprime el ZIP completo y vuelve a intentarlo."
fi

echo "1/5 Copiando ADV ARCHON.app a ~/Applications…"
mkdir -p "$INSTALL_DIR"
rm -rf "$APP_DST"
ditto "$APP_SRC" "$APP_DST"
xattr -dr com.apple.quarantine "$APP_DST" 2>/dev/null || true

echo "2/5 Comprobando uv…"
for UV in "$HOME/.cargo/bin/uv" "/opt/homebrew/bin/uv" "/usr/local/bin/uv" "$(command -v uv 2>/dev/null)"; do
  [ -x "$UV" ] && break
done
if [ ! -x "$UV" ]; then
  echo "uv no está instalado. Instalando uv desde astral.sh…"
  if ! command -v curl >/dev/null 2>&1; then
    fail_dialog "No se encontró curl para instalar uv. Instala uv manualmente desde https://astral.sh/uv"
  fi
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
  UV="$HOME/.cargo/bin/uv"
fi
[ -x "$UV" ] || fail_dialog "No se pudo instalar uv. Revisa tu conexión y vuelve a ejecutar este instalador."

PROJECT_ROOT="$APP_DST/Contents/Resources/adv-archon-source"
[ -d "$PROJECT_ROOT/src/adv_archon" ] || fail_dialog "La app no contiene el código fuente embebido esperado."

echo "3/5 Instalando dependencias locales de ADV ARCHON…"
cd "$PROJECT_ROOT"
"$UV" sync --extra desktop

echo "4/5 Comprobando Ollama…"
OLLAMA_BIN="$(command -v ollama 2>/dev/null || true)"
if [ -z "$OLLAMA_BIN" ] && [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]; then
  OLLAMA_BIN="/Applications/Ollama.app/Contents/Resources/ollama"
fi
if [ -z "$OLLAMA_BIN" ]; then
  open "https://ollama.com/download"
  fail_dialog "Ollama no está instalado. Se ha abierto la página de descarga. Instala Ollama y vuelve a ejecutar este instalador."
fi

open -a Ollama >/dev/null 2>&1 || true
sleep 2

if ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  "$OLLAMA_BIN" serve >/tmp/adv-archon-ollama.log 2>&1 &
  sleep 3
fi

if ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  fail_dialog "Ollama está instalado, pero no responde. Abre Ollama manualmente y vuelve a ejecutar este instalador."
fi

if ! "$OLLAMA_BIN" list | awk '{print $1}' | grep -qx "$MODEL"; then
  echo "Descargando modelo local ${MODEL}. Puede tardar varios minutos…"
  "$OLLAMA_BIN" pull "$MODEL"
fi

echo "5/5 Guardando configuración y preparando acceso directo…"
mkdir -p "$HOME/.adv-archon"
if [ ! -f "$HOME/.adv-archon/config.toml" ]; then
  cat > "$HOME/.adv-archon/config.toml" <<CONFIG_EOF
[llm]
mode = "local"
ollama_model = "qwen2.5:7b"
CONFIG_EOF
fi

rm -rf "$HOME/Desktop/ADV ARCHON.app"
ln -s "$APP_DST" "$HOME/Desktop/ADV ARCHON.app"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Instalación completada."
echo " Se abrirá ADV ARCHON ahora."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info_dialog "Instalación completada. Abriendo ADV ARCHON…"
open "$APP_DST"
echo ""
echo "Puedes cerrar esta ventana."
INSTALLER_EOF
chmod +x "${INSTALLER}"

cat > "${README_TXT}" <<'README_EOF'
ADV ARCHON — beta interna para probadores

Qué es
ADV ARCHON es una app local-first para revisar expedientes urbanísticos de arquitectura en España: parcela, Catastro, PGOU, afecciones sectoriales, análisis preliminar e informe PDF.

Cómo instalar
1. Descomprime ADV_ARCHON_BETA.zip.
2. Abre la carpeta ADV_ARCHON_BETA.
3. Haz doble clic en “Instalar ADV ARCHON.command”.
4. Si macOS pregunta, confirma que quieres abrirlo.
5. El instalador comprobará uv, Ollama y el modelo qwen2.5:7b.
6. Al terminar abrirá ADV ARCHON y dejará un acceso directo en el Escritorio.

Qué probar
- Crear un expediente nuevo.
- Introducir dirección, coordenadas o referencia catastral.
- Adjuntar un plano PDF si tenéis uno de prueba.
- Pulsar Analizar.
- Exportar el informe PDF.

Qué feedback necesitamos
- Qué partes se entienden sin explicación.
- Qué partes suenan demasiado técnicas.
- Si el informe sirve para una primera revisión de despacho.
- Si falta algún dato que un arquitecto esperaría ver.
- Dónde se siente lento o poco fiable.

Aviso importante
Esta beta genera un análisis preliminar no vinculante. No sustituye el criterio profesional ni la comprobación oficial del planeamiento aplicable.
README_EOF

echo "→ Generando README_PROBADORES.pdf…"
PYTHONPATH=src uv run python -c \
"from pathlib import Path
from fpdf import FPDF

out = Path('${README_PDF}')
pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=16)
pdf.add_page()
pdf.set_font('Helvetica', 'B', 18)
pdf.cell(0, 10, 'ADV ARCHON - beta interna')
pdf.ln(12)
pdf.set_font('Helvetica', '', 11)
sections = [
    ('Qué es', 'ADV ARCHON es una app local-first para revisar expedientes urbanísticos de arquitectura en España: parcela, Catastro, PGOU, afecciones sectoriales, análisis preliminar e informe PDF.'),
    ('Cómo instalar', '1. Descomprime ADV_ARCHON_BETA.zip.\\n2. Abre la carpeta ADV_ARCHON_BETA.\\n3. Haz doble clic en Instalar ADV ARCHON.command.\\n4. El instalador comprobará uv, Ollama y el modelo qwen2.5:7b.\\n5. Al terminar abrirá ADV ARCHON y dejará un acceso directo en el Escritorio.'),
    ('Qué probar', '- Crear un expediente nuevo.\\n- Introducir dirección, coordenadas o referencia catastral.\\n- Adjuntar un plano PDF si tenéis uno de prueba.\\n- Pulsar Analizar.\\n- Exportar el informe PDF.'),
    ('Feedback que necesitamos', '- Qué partes se entienden sin explicación.\\n- Qué partes suenan demasiado técnicas.\\n- Si el informe sirve para una primera revisión de despacho.\\n- Si falta algún dato que un arquitecto esperaría ver.\\n- Dónde se siente lento o poco fiable.'),
    ('Aviso', 'Esta beta genera un análisis preliminar no vinculante. No sustituye el criterio profesional ni la comprobación oficial del planeamiento aplicable.'),
]
for title, body in sections:
    pdf.ln(5)
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.multi_cell(pdf.epw, 7, title)
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Helvetica', '', 11)
    pdf.multi_cell(pdf.epw, 6, body)
pdf.output(out)
"

echo "→ Quitando cuarentena local del payload…"
xattr -cr "${PAYLOAD_DIR}" 2>/dev/null || true

echo "→ Creando ZIP…"
(
  cd "${WORK_DIR}"
  ditto -c -k --sequesterRsrc --keepParent "${BETA_NAME}" "${ZIP_PATH}"
)

ZIP_SIZE=$(du -sh "${ZIP_PATH}" | cut -f1)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✓ Paquete beta creado: ${ZIP_PATH}"
echo " ✓ Tamaño: ${ZIP_SIZE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
