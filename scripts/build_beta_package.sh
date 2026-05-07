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
#     Windows/
#       Instalar_ADV_ARCHON.bat
#       ADV_ARCHON.cmd
#       adv-archon-source/
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
WINDOWS_DIR="${PAYLOAD_DIR}/Windows"
WINDOWS_SOURCE_DIR="${WINDOWS_DIR}/adv-archon-source"
WINDOWS_INSTALLER="${WINDOWS_DIR}/Instalar_ADV_ARCHON.bat"
WINDOWS_LAUNCHER="${WINDOWS_DIR}/ADV_ARCHON.cmd"
WINDOWS_README="${WINDOWS_DIR}/README_WINDOWS.txt"

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

echo "→ Preparando versión Windows portable…"
mkdir -p "${WINDOWS_DIR}"
rsync -a \
  --exclude ".git" \
  --exclude ".mypy_cache" \
  --exclude ".pytest_cache" \
  --exclude ".ruff_cache" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "dist" \
  "${ROOT}/" "${WINDOWS_SOURCE_DIR}/"

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
"$UV" sync --extra desktop --reinstall-package python-dotenv --reinstall-package PySide6 --reinstall-package PySide6-Addons --reinstall-package PySide6-Essentials --reinstall-package shiboken6

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

cat > "${WINDOWS_LAUNCHER}" <<'WIN_LAUNCHER_EOF'
@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%adv-archon-source"
if not exist "%PROJECT_ROOT%\src\adv_archon" (
  set "PROJECT_ROOT=%USERPROFILE%\ADV ARCHON Beta\adv-archon-source"
)
if not exist "%PROJECT_ROOT%\src\adv_archon" (
  echo No se encontro adv-archon-source. Ejecuta primero Instalar_ADV_ARCHON.bat.
  pause
  exit /b 1
)

set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%LOCALAPPDATA%\Programs\Ollama;%PATH%"
cd /d "%PROJECT_ROOT%"
set "PYTHONPATH=%PROJECT_ROOT%\src;%PYTHONPATH%"
uv run python -c "import dotenv.main; from PySide6.QtWidgets import QApplication; app = QApplication([])" >nul 2>&1
if errorlevel 1 (
  uv sync --extra desktop --reinstall-package python-dotenv --reinstall-package PySide6 --reinstall-package PySide6-Addons --reinstall-package PySide6-Essentials --reinstall-package shiboken6
)
uv run python -m adv_archon.main desktop
WIN_LAUNCHER_EOF

cat > "${WINDOWS_INSTALLER}" <<'WIN_INSTALLER_EOF'
@echo off
setlocal EnableExtensions

title ADV ARCHON - instalador beta
set "MODEL=qwen2.5:7b"
set "PACKAGE_DIR=%~dp0"
set "SOURCE_DIR=%PACKAGE_DIR%adv-archon-source"
set "INSTALL_DIR=%USERPROFILE%\ADV ARCHON Beta"
set "PROJECT_ROOT=%INSTALL_DIR%\adv-archon-source"
set "DESKTOP=%USERPROFILE%\Desktop"

echo ==================================================
echo  ADV ARCHON - instalador beta Windows
echo ==================================================
echo.

if not exist "%SOURCE_DIR%\src\adv_archon" (
  echo ERROR: No encuentro adv-archon-source junto al instalador.
  echo Descomprime el ZIP completo y vuelve a intentarlo.
  pause
  exit /b 1
)

echo 1/5 Copiando ADV ARCHON a "%INSTALL_DIR%"...
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%"
mkdir "%INSTALL_DIR%" >nul 2>&1
xcopy "%SOURCE_DIR%" "%PROJECT_ROOT%\" /E /I /Y >nul
copy "%PACKAGE_DIR%ADV_ARCHON.cmd" "%INSTALL_DIR%\ADV_ARCHON.cmd" >nul

echo 2/5 Comprobando uv...
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
where uv >nul 2>&1
if errorlevel 1 (
  echo uv no esta instalado. Instalando uv...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)
where uv >nul 2>&1
if errorlevel 1 (
  echo ERROR: No se pudo instalar uv. Revisa tu conexion y vuelve a ejecutar este instalador.
  pause
  exit /b 1
)

echo 3/5 Instalando dependencias locales...
cd /d "%PROJECT_ROOT%"
uv sync --extra desktop --reinstall-package python-dotenv --reinstall-package PySide6 --reinstall-package PySide6-Addons --reinstall-package PySide6-Essentials --reinstall-package shiboken6
if errorlevel 1 (
  echo ERROR: No se pudieron instalar las dependencias.
  pause
  exit /b 1
)

echo 4/5 Comprobando Ollama y modelo local...
set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
where ollama >nul 2>&1
if errorlevel 1 (
  start "" "https://ollama.com/download/windows"
  echo ERROR: Ollama no esta instalado. Se ha abierto la pagina de descarga.
  echo Instala Ollama para Windows y vuelve a ejecutar este instalador.
  pause
  exit /b 1
)

powershell -NoProfile -Command "try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  start "" "%LOCALAPPDATA%\Programs\Ollama\Ollama.exe" >nul 2>&1
  timeout /t 5 /nobreak >nul
)

powershell -NoProfile -Command "try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo ERROR: Ollama esta instalado, pero no responde.
  echo Abre Ollama manualmente y vuelve a ejecutar este instalador.
  pause
  exit /b 1
)

ollama list | findstr /B /C:"%MODEL% " >nul 2>&1
if errorlevel 1 (
  echo Descargando modelo %MODEL%. Puede tardar varios minutos...
  ollama pull "%MODEL%"
)

echo 5/5 Guardando configuracion y acceso directo...
mkdir "%USERPROFILE%\.adv-archon" >nul 2>&1
if not exist "%USERPROFILE%\.adv-archon\config.toml" (
  > "%USERPROFILE%\.adv-archon\config.toml" echo [llm]
  >> "%USERPROFILE%\.adv-archon\config.toml" echo mode = "local"
  >> "%USERPROFILE%\.adv-archon\config.toml" echo ollama_model = "qwen2.5:7b"
)
copy "%INSTALL_DIR%\ADV_ARCHON.cmd" "%DESKTOP%\ADV_ARCHON.cmd" >nul

echo.
echo ==================================================
echo  Instalacion completada. Abriendo ADV ARCHON...
echo ==================================================
start "" "%INSTALL_DIR%\ADV_ARCHON.cmd"
echo Puedes cerrar esta ventana.
pause
WIN_INSTALLER_EOF

cat > "${WINDOWS_README}" <<'WIN_README_EOF'
ADV ARCHON — beta Windows

Cómo instalar:
1. Descomprime ADV_ARCHON_BETA.zip.
2. Abre la carpeta Windows.
3. Haz doble clic en Instalar_ADV_ARCHON.bat.
4. Windows puede mostrar SmartScreen porque esta beta no está firmada. Pulsa "Más información" > "Ejecutar de todas formas" si confías en el origen.
5. El instalador comprobará uv, dependencias Python, Ollama y el modelo qwen2.5:7b.
6. Al terminar abrirá ADV ARCHON y dejará ADV_ARCHON.cmd en el Escritorio.

Requisitos:
- Windows 10/11.
- Internet durante la primera instalación.
- Ollama para Windows instalado desde https://ollama.com/download/windows.

Aviso:
Esta beta es local-first y preliminar. No sustituye criterio profesional ni comprobación oficial del planeamiento.
WIN_README_EOF

cat > "${README_TXT}" <<'README_EOF'
ADV ARCHON — beta interna para probadores

Qué es
ADV ARCHON es una app local-first para revisar expedientes urbanísticos de arquitectura en España: parcela, Catastro, PGOU, afecciones sectoriales, análisis preliminar e informe PDF.

Cómo instalar
macOS:
1. Descomprime ADV_ARCHON_BETA.zip.
2. Abre la carpeta ADV_ARCHON_BETA.
3. Haz doble clic en “Instalar ADV ARCHON.command”.
4. Si macOS pregunta, confirma que quieres abrirlo.
5. El instalador comprobará uv, Ollama y el modelo qwen2.5:7b.
6. Al terminar abrirá ADV ARCHON y dejará un acceso directo en el Escritorio.

Windows:
1. Descomprime ADV_ARCHON_BETA.zip.
2. Abre la carpeta Windows.
3. Haz doble clic en “Instalar_ADV_ARCHON.bat”.
4. Si Windows SmartScreen avisa, pulsa “Más información” > “Ejecutar de todas formas”.
5. El instalador comprobará uv, dependencias, Ollama y el modelo qwen2.5:7b.
6. Al terminar abrirá ADV ARCHON y dejará ADV_ARCHON.cmd en el Escritorio.

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
    ('Cómo instalar', 'macOS:\\n1. Descomprime ADV_ARCHON_BETA.zip.\\n2. Haz doble clic en Instalar ADV ARCHON.command.\\n3. El instalador comprobará uv, Ollama y el modelo qwen2.5:7b.\\n\\nWindows:\\n1. Descomprime ADV_ARCHON_BETA.zip.\\n2. Abre la carpeta Windows.\\n3. Haz doble clic en Instalar_ADV_ARCHON.bat.\\n4. El instalador comprobará uv, dependencias, Ollama y el modelo qwen2.5:7b.'),
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
  COPYFILE_DISABLE=1 ditto -c -k --norsrc --keepParent "${BETA_NAME}" "${ZIP_PATH}"
)

ZIP_SIZE=$(du -sh "${ZIP_PATH}" | cut -f1)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✓ Paquete beta creado: ${ZIP_PATH}"
echo " ✓ Tamaño: ${ZIP_SIZE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
