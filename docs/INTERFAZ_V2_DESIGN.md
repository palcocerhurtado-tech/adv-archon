# INTERFAZ V2 — Especificación de Diseño

## 1. Dimensiones y disposición general

```
┌─────────────────────────────────────────────────────────────────┐
│  VENTANA: 1280 × 800 px (mínimo), escalable                     │
│                                                                   │
│  ┌──────────┐  ┌───────────────────────────┐  ┌──────────────┐  │
│  │ Sidebar  │  │      Área central          │  │ Panel dcho.  │  │
│  │  220 px  │  │       740 px               │  │   280 px     │  │
│  │          │  │  ┌─────────────────────┐   │  │              │  │
│  │          │  │  │  Hero compacto 52px │   │  │              │  │
│  │          │  │  └─────────────────────┘   │  │              │  │
│  │          │  │  ┌───────────┬─────────┐   │  │              │  │
│  │          │  │  │ Contenido │ Editor  │   │  │              │  │
│  │          │  │  │  70%      │  30%    │   │  │              │  │
│  │          │  │  └───────────┴─────────┘   │  │              │  │
│  └──────────┘  └───────────────────────────┘  └──────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │            Composer multimodal  140 px                       │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Sidebar izquierda (220 px)

### Estructura

```
┌──────────────────────────┐
│  ⬡  ADV ARCHON           │  Logo + nombre (20px, serif bold)
│  ─────────────────────── │
│                           │
│  ▸ INICIO                 │  Grupo 1 — navegación principal
│    🏠 Panel principal     │
│    📋 Expedientes         │  ← activo: borde izq 3px dorado (#C9A84C),
│    🗺 Geo / Parcela       │              fondo negro puro
│                           │
│  ▸ ANÁLISIS               │  Grupo 2 — herramientas de análisis
│    ⚖ Cumplimiento         │
│    📄 Documentos          │
│    📊 PGOU                │
│                           │
│  ▸ AGENTE                 │  Grupo 3 — modos IA
│    🤖 Studio              │
│    💬 Chat contextual     │
│                           │
│  ▸ DATOS                  │  Grupo 4 — gestión de datos
│    🗂 Archivos             │
│    🧠 Memoria              │
│                           │
│  ─────────────────────── │
│  ▾ CONFIGURACIÓN  ⚙       │  Grupo 5 — colapsable
│    Modo: [local ▾]        │
│    Modelo: [llama3.2 ▾]   │
│    Perfil: [general ▾]    │
│                           │
│  ─────────────────────── │
│  🟡 Beta 0.2              │  Footer: versión + estado sistema
│  Ollama ● activo          │  ● verde si activo, ● gris si inactivo
└──────────────────────────┘
```

### Estilos de sidebar

| Elemento | Valor |
|---|---|
| Fondo sidebar | `#111111` |
| Texto grupo (label) | `#666666`, mayúsculas, 10px, letter-spacing 1.5px |
| Texto ítem | `#CCCCCC`, 13px, Inter |
| Ítem activo fondo | `#1A1A1A` |
| Ítem activo borde izq | 3px solid `#C9A84C` |
| Ítem activo texto | `#FFFFFF` bold |
| Hover ítem | fondo `#1C1C1C`, transición 150ms ease |
| Icono de grupo (▸/▾) | animación rotate 90° al colapsar, 200ms ease |
| Separadores | `1px solid #2A2A2A` |
| Footer texto | `#C9A84C` (versión), `#888888` (estado) |

---

## 3. Barra superior de estado (32 px, ancho completo menos sidebar)

```
┌──────────────────────────────────────────────────────────────────┐
│  ◌  Abriendo bases de datos…          ████████░░░░  68%          │
│     [icono animado pulsante]  [texto dinámico]  [barra progreso] │
└──────────────────────────────────────────────────────────────────┘
```

- **Fondo**: `#1A1A1A`
- **Barra de progreso**: riel `#2A2A2A`, relleno `#C9A84C`, altura 3px, border-radius 2px
- **Icono de estado**: círculo pulsante (keyframe CSS/QPropertyAnimation) durante carga; ✓ verde cuando listo
- **Texto**: `#AAAAAA`, 12px Inter. Máximo 60 caracteres. Se trunca con `…`
- **Cuando inactivo** (sistema listo): la barra desaparece y el espacio se colapsa a 0px con transición height 200ms

---

## 4. Área central

### 4.1 Hero compacto (fijo, altura 52 px)

```
┌──────────────────────────────────────────────────────────────────┐
│  ADV ARCHON STUDIO · Expedientes urbanísticos    [+ Nuevo exp.]  │
└──────────────────────────────────────────────────────────────────┘
```

- **Fondo**: `#F7F4EF` (blanco roto)
- **Título**: serif bold 15px, `#111111` · separador `·` en `#C9A84C`
- **Subtítulo inline**: sans-serif 13px, `#888888`
- **Botón "Nuevo expediente"**: fondo `#C9A84C`, texto `#111111` bold 12px, padding 6×14px, border-radius 4px, hover: `#D4AF60`, transición 150ms

### 4.2 Layout de dos columnas (resto del área central)

**Columna izquierda (70% ≈ 516 px)**

```
┌─────────────────────────────────────────────┐
│  MÉTRICAS (fila horizontal de 4 tarjetas)   │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐│
│  │  12    │ │   8    │ │   3    │ │  llm  ││
│  │ Exped. │ │Inform. │ │Riesgos │ │ local ││
│  └────────┘ └────────┘ └────────┘ └───────┘│
│                                              │
│  EXPEDIENTES RECIENTES                       │
│  ┌──────────────────────────────────────────┐│
│  │ ● Residencial Calle Mayor 3  Madrid      ││
│  │   VIABLE · hace 2h · Ver →              ││
│  ├──────────────────────────────────────────┤│
│  │ ⚠ Ampliación nave Pol. Ind. Sur Valencia ││
│  │   CONDICIONADO · hace 1d · Ver →        ││
│  └──────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

Tarjetas de métricas:
- Fondo `#FFFFFF`, borde `1px solid #E8E4DD`, border-radius 8px, padding 12px, sombra `0 1px 3px rgba(0,0,0,0.08)`
- Número: 24px bold `#C9A84C` (serif)
- Label: 11px `#888888` (sans-serif, uppercase)
- Hover: sombra `0 4px 12px rgba(0,0,0,0.12)`, transición 200ms

Filas de expediente:
- Fondo `#FFFFFF`, borde-bottom `1px solid #F0EDE8`
- Estado ●: verde `#22C55E` (VIABLE), naranja `#F59E0B` (CONDICIONADO), rojo `#EF4444` (REVISAR)
- Nombre: 13px bold `#111111`
- Meta: 12px `#888888`
- Hover: fondo `#FAF8F5`, flecha → anima 4px a la derecha

**Columna derecha (30% ≈ 220 px) — contexto dinámico**

Estado A — *Generando informe* (Editor de borrador):
```
┌─────────────────────────┐
│  ✏ BORRADOR EN VIVO     │
│  ─────────────────────  │
│  [QTextEdit enriquecido]│
│  con contenido editable │
│  en tiempo real         │
│                         │
│  [Actualizar vista]     │
│  [Exportar como… ▾]     │
│    PDF / DOCX / XLSX    │
└─────────────────────────┘
```

Estado B — *Sin análisis activo* (Asistente de parámetros):
```
┌─────────────────────────┐
│  ⚙ PARÁMETROS           │
│  ─────────────────────  │
│  Municipio: Madrid      │
│  Edificabilidad: 1.5    │
│  Altura máx.: 10 m      │
│  Ocupación: 60%         │
│  Retranqueos: 5 m       │
│  ─────────────────────  │
│  Confianza: ● Alta      │
│  [Confirmar] [Editar]   │
└─────────────────────────┘
```

- Fondo columna derecha: `#F7F4EF`
- Borde izquierdo: `1px solid #E8E4DD`
- Padding: 16px
- Título sección: 10px uppercase `#888888`, letter-spacing 1.5px

---

## 5. Panel lateral derecho (280 px)

Fondo `#111111`, borde izquierdo `1px solid #2A2A2A`. Se actualiza en tiempo real vía señales Qt.

```
┌──────────────────────────────┐
│  CONTEXTO                    │  14px bold `#FFFFFF`
│  ─────────────────────────── │
│                              │
│  ▾ HERRAMIENTAS ACTIVAS      │  10px `#888888` uppercase
│    ☑ catastro.parcel         │  12px `#CCCCCC`, checkbox amarillo si activo
│    ☑ snczi.flood             │
│    ☐ pgou_search             │  gris si inactivo
│                              │
│  ▾ FUENTES CONSULTADAS       │
│    📄 Art.23 PGOU Madrid     │  12px `#C9A84C`, hover subrayado
│    🌐 Catastro OVC           │
│    🌐 SNCZI/CNIG             │
│                              │
│  ▾ HISTORIAL DE ACCIONES     │
│    14:32 → Búsqueda PGOU     │  10px `#666666` timestamp
│    14:33 → Extracción params │  12px `#CCCCCC` descripción
│    14:34 → Análisis LLM ●    │  ● pulsante si en curso
│                              │
│  ▾ ADJUNTOS RECIENTES        │
│    ┌──┐ ┌──┐ ┌──┐           │  Miniaturas 40×40px
│    │🖼│ │📄│ │📊│           │  con overlay del tipo de archivo
│    └──┘ └──┘ └──┘           │
│    plano.pdf  datos.xlsx     │  10px `#666666`
└──────────────────────────────┘
```

- El panel se desliza hacia dentro desde la derecha al abrirse (translate 280px → 0px, 250ms ease-out)
- Cada sección es colapsable con ▾/▸ y animación de altura
- Las fuentes son clicables (abren en el chat con referencia citada)
- El historial añade entradas con fade-in (opacity 0 → 1, 300ms)
- Las miniaturas tienen hover con tooltip (nombre completo del archivo)

---

## 6. Composer multimodal (140 px)

```
┌──────────────────────────────────────────────────────────────────┐
│ ┌────────────────────────────────────────────┐  [🎤] [📎] [✨]  │
│ │ Escribe tu consulta o arrastra archivos…   │                   │
│ │                                            │  Ctrl+Enter envía │
│ └────────────────────────────────────────────┘                   │
│ ──────────────────────────────────────────────────────────────── │
│  [📄 plano.pdf ×]  [🖼 foto.jpg ×]   ← franja de adjuntos       │
└──────────────────────────────────────────────────────────────────┘
```

- **Campo de texto**: `QPlainTextEdit`, fondo `#1A1A1A`, texto `#EEEEEE`, placeholder `#555555`, border `1px solid #333333`, border-radius 6px, padding 10px
- **Área de arrastre**: al entrar un archivo, el campo parpadea con borde `#C9A84C` (keyframe 3× fade)
- **Botón Hablar (🎤)**: en reposo `#333333`; al grabar, anillo pulsante `#C9A84C` alrededor del icono (QPropertyAnimation sobre radio), texto cambia a "Grabando…"
- **Botón Enviar (✨)**: fondo `#C9A84C`, icono, hover: fondo `#D4AF60`; mientras el agente procesa → spinner circular sustituyendo el ícono, fondo `#555555` (desactivado)
- **Franja de adjuntos**: altura 40px, se expande si hay adjuntos; cada chip tiene miniatura 28×28px, nombre truncado 12px, botón × para eliminar
- **Atajos activos**:
  - `Ctrl+Enter` → enviar
  - `Ctrl+N` → nuevo expediente
  - `Ctrl+O` → adjuntar archivo
  - `Esc` → cancelar adjunto pendiente

---

## 7. Modo oscuro / claro

| Token | Modo claro | Modo oscuro |
|---|---|---|
| `bg-surface` | `#F7F4EF` | `#111111` |
| `bg-card` | `#FFFFFF` | `#1A1A1A` |
| `bg-sidebar` | `#111111` | `#0A0A0A` |
| `text-primary` | `#111111` | `#EEEEEE` |
| `text-secondary` | `#888888` | `#666666` |
| `accent` | `#C9A84C` | `#C9A84C` |
| `border` | `#E8E4DD` | `#2A2A2A` |
| `shadow` | `rgba(0,0,0,0.08)` | `rgba(0,0,0,0.4)` |

El toggle de modo se activa desde `Configuración > Apariencia`. La transición global usa `QPropertyAnimation` sobre `palette()`, 300ms.

---

## 8. Micro-interacciones (mínimo requerido)

1. **Hover sobre tarjeta de expediente o métrica**: sombra pasa de `0 1px 3px` a `0 4px 12px rgba(0,0,0,0.12)`, transición 200ms ease-out. La tarjeta sube 1px con `margin-top -1px`.

2. **Apertura del panel derecho**: si estaba oculto (< 800px de ancho), desliza desde la derecha con `QPropertyAnimation` sobre `maximumWidth`, de 0 a 280px en 250ms ease-out. El área central se comprime simultáneamente.

3. **Indicador de carga del botón Enviar**: al hacer clic, el icono ✨ se reemplaza por un arco giratorio (dibujado con `QPainter` en un `QWidget` overlay), duración indefinida hasta respuesta. El botón queda deshabilitado pero con cursor `wait`.

4. **Entrada de nueva acción en historial**: cada nuevo ítem del panel derecho aparece con `opacity: 0` y `margin-top: -16px`, y anima a `opacity: 1`, `margin-top: 0` en 300ms ease-out.

5. **Pulsación del estado "en curso"** en el historial: el punto ● del último ítem usa un keyframe `box-shadow 0→8px→0` con color `#C9A84C`, period 1.4s, loop infinito mientras el agente esté activo.
