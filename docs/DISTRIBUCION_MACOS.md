# ADV ARCHON — Distribución macOS (coste cero)

Guía completa para construir, empaquetar y distribuir ADV ARCHON sin cuenta de desarrollador Apple ni herramientas de pago.

---

## Requisitos mínimos

- macOS 13 Ventura o superior
- [uv](https://astral.sh/uv) instalado (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Repositorio clonado en `/Users/<tu-usuario>/Desktop/adv archon`

No se necesita PyInstaller, Xcode, ni Apple Developer Program.

---

## 1. Construir el .app

### Opción A — Rápida (solo .app en el Escritorio)

```bash
cd "/Users/pabloalcocer/Desktop/adv archon"
uv pip install -e ".[desktop]"
uv run adv-archon desktop-bundle ~/Desktop
```

El resultado es `~/Desktop/ADV ARCHON.app`.

### Opción B — Script completo con DMG (recomendado para distribuir)

```bash
cd "/Users/pabloalcocer/Desktop/adv archon"
./scripts/build_macos.sh --sign --dmg
```

Genera en `dist/`:
- `ADV ARCHON.app` — la aplicación
- `ADV ARCHON.dmg` — instalador para distribución

Opciones disponibles:

| Flag | Efecto |
|------|--------|
| `--sign` | Firma ad-hoc con `codesign -s -` (no requiere cuenta Apple) |
| `--dmg` | Crea `.dmg` arrastrable con acceso directo a Aplicaciones |
| `--open` | Abre el DMG en el Finder al terminar |

---

## 2. Crear el DMG manualmente (alternativa)

Si prefieres hacerlo paso a paso sin el script:

```bash
# 1. Generar el .app en dist/
uv run adv-archon desktop-bundle dist/

# 2. Quitar cuarentena
xattr -cr "dist/ADV ARCHON.app"

# 3. Firma ad-hoc (opcional pero recomendado)
codesign --force --deep --sign - "dist/ADV ARCHON.app"

# 4. Crear carpeta de staging
mkdir -p /tmp/archon_dmg
cp -r "dist/ADV ARCHON.app" /tmp/archon_dmg/
ln -sf /Applications /tmp/archon_dmg/Aplicaciones

# 5. Crear DMG comprimido
hdiutil create \
  -volname "ADV ARCHON" \
  -srcfolder /tmp/archon_dmg \
  -ov \
  -format UDZO \
  "dist/ADV ARCHON.dmg"

rm -rf /tmp/archon_dmg
```

---

## 3. Instalar en otro Mac

### El arquitecto recibe el .dmg:

1. Hacer doble clic en `ADV ARCHON.dmg`
2. Arrastrar `ADV ARCHON` a la carpeta `Aplicaciones` (o al Escritorio)
3. Expulsar el DMG

### Primera apertura:

macOS puede mostrar un aviso de seguridad porque la app no está notarizada por Apple.

**Solución opción A — Sin terminal:**
- Ir a `Ajustes del Sistema` → `Privacidad y Seguridad`
- Bajar hasta ver `"ADV ARCHON" fue bloqueado porque no es de un desarrollador identificado`
- Pulsar `Abrir de todos modos`

**Solución opción B — Con terminal (1 comando):**
```bash
xattr -dr com.apple.quarantine "/Applications/ADV ARCHON.app"
```

---

## 4. Actualizar en un Mac que ya tiene la app

```bash
cd "/Users/pabloalcocer/Desktop/adv archon"
git pull origin claude/deepseek-v4-exploration-P51AF
./scripts/build_macos.sh --sign --dmg
```

Luego reemplazar la app existente con la nueva versión de `dist/`.

---

## 5. Limitaciones actuales (coste cero)

| Limitación | Causa | Solución futura |
|---|---|---|
| Aviso de Gatekeeper en la primera apertura | Sin notarización Apple | Apple Developer Program (~99 USD/año) |
| La app debe estar en la misma carpeta del repositorio | Bundle.py lanza con `uv run` | Empaquetar con PyInstaller (autocontenido) |
| Sin auto-update | Sin infraestructura de distribución | Servidor de actualizaciones o Sparkle |
| Solo arquitectura nativa del Mac que construye | Bundle.py usa el Python local | `--target-arch universal2` con PyInstaller |

---

## 6. Camino a distribución profesional (cuando haya presupuesto)

1. **Apple Developer Program** ($99/año):
   - Notarización Apple → sin avisos de seguridad para ningún usuario
   - Distribución en Mac App Store (opcional)

2. **PyInstaller autocontenido** (`archon.spec` ya preparado):
   ```bash
   ./scripts/build_macos.sh --pyinstaller --sign --dmg
   ```
   Genera un `.app` que lleva Python embebido — no requiere `uv` en el Mac del cliente.

3. **Auto-update con Sparkle** (open-source):
   - El usuario recibe notificaciones de actualización dentro de la app
   - Requiere servidor web para alojar las actualizaciones

---

## Referencia rápida

```bash
# Build completo recomendado
./scripts/build_macos.sh --sign --dmg

# Solo .app en dist/
./scripts/build_macos.sh

# Quitar cuarentena manualmente
xattr -dr com.apple.quarantine "/Applications/ADV ARCHON.app"

# Verificar firma
codesign -dv "dist/ADV ARCHON.app"
```
