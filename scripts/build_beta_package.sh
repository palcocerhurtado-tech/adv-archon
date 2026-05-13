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
DEMO_DIR="${PAYLOAD_DIR}/Demos Studio"
FEEDBACK_TXT="${PAYLOAD_DIR}/CHECKLIST_FEEDBACK_ARQUITECTOS.txt"
FEEDBACK_PDF="${PAYLOAD_DIR}/CHECKLIST_FEEDBACK_ARQUITECTOS.pdf"

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
  --include ".env.example" \
  --exclude ".env" \
  --exclude ".env.*" \
  --exclude ".DS_Store" \
  --exclude ".git" \
  --exclude ".mypy_cache" \
  --exclude ".pytest_cache" \
  --exclude ".ruff_cache" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "dist" \
  --exclude "docs/archive" \
  --exclude "normativa_arquitectura_es" \
  --exclude "src/adv_archon.egg-info" \
  --exclude "tests" \
  --exclude "*.pyc" \
  --exclude "*.pyo" \
  "${ROOT}/" "${WINDOWS_SOURCE_DIR}/"

cat > "${INSTALLER}" <<'INSTALLER_EOF'
#!/bin/zsh
set -e

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SRC="${PACKAGE_DIR}/ADV ARCHON.app"
INSTALL_DIR="${HOME}/Applications"
APP_DST="${INSTALL_DIR}/ADV ARCHON.app"
MODEL="qwen2.5:7b"
LOG_FILE="${HOME}/.adv-archon/install.log"

mkdir -p "${HOME}/.adv-archon"
exec > >(tee -a "$LOG_FILE") 2>&1

clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ADV ARCHON — instalador beta"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Log de instalación: $LOG_FILE"
echo ""

fail_dialog() {
  osascript -e "display alert \"ADV ARCHON\" message \"$1\" as critical" >/dev/null 2>&1 || true
  echo "ERROR: $1"
  echo "Log de instalación: $LOG_FILE"
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
uv run python -c "import dotenv.main; from PySide6.QtCore import QLibraryInfo; print(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))" >nul 2>&1
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
set "LOG_DIR=%USERPROFILE%\.adv-archon"
set "LOG_FILE=%LOG_DIR%\install-windows.log"

echo ==================================================
echo  ADV ARCHON - instalador beta Windows
echo ==================================================
echo.
mkdir "%LOG_DIR%" >nul 2>&1
echo ADV ARCHON install %DATE% %TIME% > "%LOG_FILE%"
echo Log de instalacion: %LOG_FILE%
echo.

if not exist "%SOURCE_DIR%\src\adv_archon" (
  echo ERROR: No encuentro adv-archon-source junto al instalador.
  echo Descomprime el ZIP completo y vuelve a intentarlo.
  echo Revisa el log: %LOG_FILE%
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
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" >> "%LOG_FILE%" 2>&1
  set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)
where uv >nul 2>&1
if errorlevel 1 (
  echo ERROR: No se pudo instalar uv. Revisa tu conexion y vuelve a ejecutar este instalador.
  echo Revisa el log: %LOG_FILE%
  pause
  exit /b 1
)

echo 3/5 Instalando dependencias locales...
cd /d "%PROJECT_ROOT%"
uv sync --extra desktop --reinstall-package python-dotenv --reinstall-package PySide6 --reinstall-package PySide6-Addons --reinstall-package PySide6-Essentials --reinstall-package shiboken6 >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  echo ERROR: No se pudieron instalar las dependencias.
  echo Revisa el log: %LOG_FILE%
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
  echo Revisa el log: %LOG_FILE%
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
  echo Revisa el log: %LOG_FILE%
  pause
  exit /b 1
)

ollama list | findstr /B /C:"%MODEL% " >nul 2>&1
if errorlevel 1 (
  echo Descargando modelo %MODEL%. Puede tardar varios minutos...
  ollama pull "%MODEL%" >> "%LOG_FILE%" 2>&1
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
- 8 GB de RAM recomendados.
- 8-12 GB libres para dependencias y modelo local.

Si falla:
- Repite el instalador una vez.
- Si vuelve a fallar, envía una captura y este log:
  %USERPROFILE%\.adv-archon\install-windows.log

Aviso:
Esta beta es local-first y preliminar. No sustituye criterio profesional ni comprobación oficial del planeamiento.
WIN_README_EOF

cat > "${README_TXT}" <<'README_EOF'
ADV ARCHON Beta 0.1 — guía para probadores

Qué es
ADV ARCHON es una app local-first para revisar expedientes urbanísticos de arquitectura en España: parcela, Catastro, PGOU, afecciones sectoriales, análisis preliminar e informe PDF.

Objetivo de esta beta
Queremos saber si un arquitecto no técnico puede probar ADV ARCHON sin ayuda y decir si lo compraría para una primera revisión de despacho.

Tiempo recomendado
Reserva 10-15 minutos. La primera instalación puede tardar más si hay que descargar el modelo local qwen2.5:7b.

Requisitos
- Internet durante la primera instalación.
- Ollama instalado o permiso para instalarlo desde la web oficial.
- macOS 13+ o Windows 10/11.
- 8 GB de RAM recomendados.
- 8-12 GB libres para dependencias y modelo local.

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
- Abrir “Studio Demo” y pulsar “Iniciar demo comercial”.
- Abrir los 3 informes de ejemplo incluidos en la carpeta “Demos Studio”.
- Crear un expediente nuevo.
- Introducir dirección, coordenadas o referencia catastral.
- Adjuntar un plano PDF si tenéis uno de prueba.
- Pulsar Analizar.
- Exportar el informe PDF.

Prueba de compra
Al terminar, responde con sinceridad:
- ¿Entenderías esta app sin que Pablo te la explique?
- ¿La usarías en un expediente real como cribado preliminar?
- ¿Qué tendría que mejorar para que el precio fuera defendible?
- ¿Qué dato o pantalla falta para que parezca una herramienta de despacho?

Qué feedback necesitamos
- Qué partes se entienden sin explicación.
- Qué partes suenan demasiado técnicas.
- Si el informe sirve para una primera revisión de despacho.
- Si falta algún dato que un arquitecto esperaría ver.
- Dónde se siente lento o poco fiable.

Si falla
- macOS: envía una captura y el archivo ~/.adv-archon/install.log.
- Windows: envía una captura y el archivo %USERPROFILE%\.adv-archon\install-windows.log.

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
pdf.cell(0, 10, 'ADV ARCHON Beta 0.1')
pdf.ln(12)
pdf.set_font('Helvetica', '', 11)
sections = [
    ('Qué es', 'ADV ARCHON es una app local-first para revisar expedientes urbanísticos de arquitectura en España: parcela, Catastro, PGOU, afecciones sectoriales, análisis preliminar e informe PDF.'),
    ('Objetivo', 'Queremos saber si un arquitecto no técnico puede probar ADV ARCHON sin ayuda y decir si lo compraría para una primera revisión de despacho. Reserva 10-15 minutos; la primera instalación puede tardar más si descarga qwen2.5:7b.'),
    ('Requisitos', '- Internet durante la primera instalación.\\n- macOS 13+ o Windows 10/11.\\n- Ollama instalado o permiso para instalarlo.\\n- 8 GB de RAM recomendados.\\n- 8-12 GB libres.'),
    ('Cómo instalar', 'macOS:\\n1. Descomprime ADV_ARCHON_BETA.zip.\\n2. Haz doble clic en Instalar ADV ARCHON.command.\\n3. El instalador comprobará uv, Ollama y el modelo qwen2.5:7b.\\n\\nWindows:\\n1. Descomprime ADV_ARCHON_BETA.zip.\\n2. Abre la carpeta Windows.\\n3. Haz doble clic en Instalar_ADV_ARCHON.bat.\\n4. El instalador comprobará uv, dependencias, Ollama y el modelo qwen2.5:7b.'),
    ('Qué probar', '- Abrir Studio Demo y pulsar Iniciar demo comercial.\\n- Abrir los 3 informes de ejemplo incluidos en Demos Studio.\\n- Crear un expediente nuevo.\\n- Introducir dirección, coordenadas o referencia catastral.\\n- Adjuntar un plano PDF si tenéis uno de prueba.\\n- Pulsar Analizar.\\n- Exportar el informe PDF.'),
    ('Prueba de compra', '- ¿Entenderías esta app sin explicación?\\n- ¿La usarías en un expediente real como cribado preliminar?\\n- ¿Qué tendría que mejorar para que el precio fuera defendible?\\n- ¿Qué dato o pantalla falta para que parezca herramienta de despacho?'),
    ('Feedback que necesitamos', '- Qué partes se entienden sin explicación.\\n- Qué partes suenan demasiado técnicas.\\n- Si el informe sirve para una primera revisión de despacho.\\n- Si falta algún dato que un arquitecto esperaría ver.\\n- Dónde se siente lento o poco fiable.'),
    ('Si falla', 'macOS: envía una captura y ~/.adv-archon/install.log.\\nWindows: envía una captura y %USERPROFILE%\\\\.adv-archon\\\\install-windows.log.'),
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

cat > "${FEEDBACK_TXT}" <<'FEEDBACK_EOF'
CHECKLIST DE FEEDBACK PARA ARQUITECTOS — ADV ARCHON STUDIO

Objetivo
Validar si ADV ARCHON se entiende como herramienta de despacho y si el informe parece suficientemente profesional para una primera revisión urbanística.

Prueba guiada de 10 minutos
[ ] Abrí Studio Demo sin ayuda.
[ ] Entendí los 3 casos: cambio de uso, inundabilidad y PGOU pendiente.
[ ] Abrí al menos un informe PDF.
[ ] Entendí el semáforo de decisión.
[ ] Entendí qué fuentes se habían consultado.
[ ] Entendí qué parte era preliminar y qué parte requería revisión profesional.

Valor percibido
[ ] Me ahorraría tiempo en una primera lectura de expediente.
[ ] Me ayudaría a detectar riesgos antes de presupuestar.
[ ] El PDF podría circular internamente en un despacho.
[ ] El flujo se parece a cómo trabajaría un arquitecto.

Preguntas clave
1. ¿Qué caso demo te pareció más creíble?
2. ¿Qué dato faltó para confiar más?
3. ¿Qué pantalla o texto te pareció demasiado técnico?
4. ¿Qué cambiarías del PDF para enseñarlo a un cliente o socio?
5. ¿Cuánto pagarías por una versión con tus municipios y plantilla de despacho?

Aviso
Esta beta es preliminar y no sustituye comprobación oficial ni criterio profesional.
FEEDBACK_EOF

echo "→ Generando CHECKLIST_FEEDBACK_ARQUITECTOS.pdf y PDFs demo Studio…"
mkdir -p "${DEMO_DIR}"
PYTHONPATH=src uv run python -c \
"from pathlib import Path
from fpdf import FPDF

from adv_archon.core.demo import create_studio_demo_expedientes
from adv_archon.core.expediente import ExpedienteStore

feedback_pdf = Path('${FEEDBACK_PDF}')
pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=16)
pdf.add_page()
pdf.set_font('Helvetica', 'B', 17)
pdf.cell(0, 10, 'Checklist de feedback para arquitectos')
pdf.ln(12)
pdf.set_font('Helvetica', '', 11)
blocks = [
    ('Objetivo', 'Validar si ADV ARCHON se entiende como herramienta de despacho y si el informe parece suficientemente profesional para una primera revisión urbanística.'),
    ('Prueba guiada de 10 minutos', '[ ] Abrí Studio Demo sin ayuda.\\n[ ] Entendí los 3 casos: cambio de uso, inundabilidad y PGOU pendiente.\\n[ ] Abrí al menos un informe PDF.\\n[ ] Entendí el semáforo de decisión.\\n[ ] Entendí qué fuentes se habían consultado.\\n[ ] Entendí qué parte era preliminar y qué parte requería revisión profesional.'),
    ('Valor percibido', '[ ] Me ahorraría tiempo en una primera lectura de expediente.\\n[ ] Me ayudaría a detectar riesgos antes de presupuestar.\\n[ ] El PDF podría circular internamente en un despacho.\\n[ ] El flujo se parece a cómo trabajaría un arquitecto.'),
    ('Preguntas clave', '1. ¿Qué caso demo te pareció más creíble?\\n2. ¿Qué dato faltó para confiar más?\\n3. ¿Qué pantalla o texto te pareció demasiado técnico?\\n4. ¿Qué cambiarías del PDF para enseñarlo a un cliente o socio?\\n5. ¿Cuánto pagarías por una versión con tus municipios y plantilla de despacho?'),
    ('Aviso', 'Esta beta es preliminar y no sustituye comprobación oficial ni criterio profesional.'),
]
for title, body in blocks:
    pdf.ln(5)
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.multi_cell(pdf.epw, 7, title)
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Helvetica', '', 11)
    pdf.multi_cell(pdf.epw, 6, body)
pdf.output(feedback_pdf)

data_dir = Path('${WORK_DIR}') / 'studio-demo-data'
data_dir.mkdir(parents=True, exist_ok=True)
store = ExpedienteStore(data_dir / 'expedientes.db')
demos = create_studio_demo_expedientes(store, data_dir=data_dir)
demo_dir = Path('${DEMO_DIR}')
names = {
    'cambio_uso_vivienda': '01_cambio_de_uso_local_a_vivienda.pdf',
    'vivienda_unifamiliar': '02_parcela_con_inundabilidad.pdf',
    'obra_nueva': '03_vivienda_unifamiliar_pgou_pendiente.pdf',
}
for exp in demos:
    src = Path(exp.report_path)
    if src.exists():
        target = demo_dir / names.get(exp.case_type, f'{exp.case_type}.pdf')
        target.write_bytes(src.read_bytes())
"

echo "→ Quitando cuarentena local del payload…"
xattr -cr "${PAYLOAD_DIR}" 2>/dev/null || true

echo "→ Creando ZIP…"
(
  cd "${WORK_DIR}"
  COPYFILE_DISABLE=1 ditto -c -k --norsrc --keepParent "${BETA_NAME}" "${ZIP_PATH}"
)

echo "→ Verificando que el ZIP no contiene secretos ni caches…"
ZIP_LIST="$(mktemp)"
if command -v zipinfo >/dev/null 2>&1; then
  zipinfo -1 "${ZIP_PATH}" > "${ZIP_LIST}"
else
  unzip -Z1 "${ZIP_PATH}" > "${ZIP_LIST}"
fi
if grep -E '(^|/)\.env($|\.)' "${ZIP_LIST}" | grep -v '/\.env\.example$'; then
  echo "ERROR: El ZIP contiene archivos .env. No se puede distribuir esta beta."
  exit 1
fi
if grep -E '(^|/)(\.git|\.venv|__pycache__|\.pytest_cache|\.ruff_cache|\.mypy_cache)(/|$)' "${ZIP_LIST}"; then
  echo "ERROR: El ZIP contiene carpetas internas o caches. No se puede distribuir esta beta."
  exit 1
fi
if grep -F '/normativa_arquitectura_es/' "${ZIP_LIST}"; then
  echo "ERROR: El ZIP contiene el subproyecto de normativa. No se puede distribuir esta beta."
  exit 1
fi
rm -f "${ZIP_LIST}"

ZIP_SIZE=$(du -sh "${ZIP_PATH}" | cut -f1)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✓ Paquete beta creado: ${ZIP_PATH}"
echo " ✓ Tamaño: ${ZIP_SIZE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
