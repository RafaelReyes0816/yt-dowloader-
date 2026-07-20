# Rediseño UI — YT-DownLoader del Jaeger

**Framework actual:** Tkinter / CustomTkinter · **Plataformas:** Linux, macOS, Windows
**Objetivo:** pasar de un layout funcional-pero-genérico a una interfaz con identidad propia, sin perder la simplicidad de uso.

---

## 1. Diagnóstico rápido de la versión actual

- El azul marino plano + rosa saturado no tienen jerarquía: título, botones y estado de "ffmpeg OK" compiten al mismo nivel visual.
- Los checkboxes de opciones (Subtítulos, Playlist, Auto-URL) son cajitas default de Tkinter — rompen la coherencia con el resto.
- Hay mucho espacio vacío entre "Opciones" y "Cola de Descargas" que no aporta nada.
- La barra de progreso inferior es genérica y no dice qué está pasando.
- El único acento de color (rosa) se usa para todo: título, botón activo y botón de acción → pierde significado.

La propuesta abajo resuelve esto con un sistema de tokens claro y un elemento de firma pensado para esta app en concreto.

---

## 2. Concepto de dirección

**Nombre del concepto:** *HUD de hangar* — un tablero de control oscuro, preciso, con un solo acento cálido, inspirado en la idea de "Jaeger" (panel de mando) pero sin caer en cliché gamer/RGB. Cada descarga en cola se trata como una "unidad" con su propio anillo de progreso circular (el elemento de firma), en vez de una barra genérica.

---

## 3. Tokens de diseño

### 3.1 Color

| Token | Hex | Uso |
|---|---|---|
| `bg.base` | `#0B0F1A` | Fondo de ventana |
| `bg.surface` | `#141B2D` | Tarjetas, inputs, filas de la cola |
| `bg.surface-hover` | `#1B2438` | Hover sobre tarjetas/filas |
| `border.subtle` | `#232D45` | Bordes y divisores |
| `text.primary` | `#E8ECF4` | Texto principal |
| `text.secondary` | `#8B96AE` | Labels, subtítulos, placeholders |
| `accent.brand` | `#FF4F6E` | Marca, botón principal, foco |
| `accent.success` | `#35D499` | Estado "Completado" |
| `accent.progress` | `#FFB454` | Estado "Descargando" |
| `accent.error` | `#FF5D5D` | Errores, cancelaciones |

Un solo acento cálido (`accent.brand`) para acción/marca; los otros tres colores son **de estado**, nunca decorativos. Esto es lo que le faltaba a la versión actual: cada color significa algo.

### 3.2 Tipografía

| Rol | Fuente | Fallback multiplataforma |
|---|---|---|
| Display (título app) | Sora (700) | Segoe UI Semibold / SF Pro Display / Inter |
| UI / cuerpo | Inter (400/500/600) | Segoe UI / SF Pro Text / Noto Sans |
| Monoespaciada (URLs, rutas) | JetBrains Mono (400) | Consolas / Menlo / DejaVu Sans Mono |

Escala: `11 / 13 / 15 / 18 / 24` px. Nada por debajo de 11px (legibilidad en pantallas 4K con escalado).

### 3.3 Espaciado y forma

- Escala de espaciado: `4, 8, 12, 16, 24, 32`.
- `corner_radius`: `8` para inputs y botones, `12` para tarjetas/filas de cola, `999` (círculo completo) para el anillo de progreso y los chips de opciones.
- Borde de 1px `border.subtle` en tarjetas sobre `bg.surface`, nunca sombras (Tkinter no las renderiza bien de forma nativa).

---

## 4. Wireframe general

```
┌──────────────────────────────────────────────────────────┐
│  ●  ○  ○      YT-DownLoader del Jaeger      ffmpeg● v1.2.5│  ← barra título (custom)
├──────────────────────────────────────────────────────────┤
│                                                            │
│  YT-DownLoader                                            │  ← display, accent.brand
│  Descarga video o audio desde una URL                     │  ← subtítulo, text.secondary
│                                                            │
│  ┌──────────────────────────────────────────┐  ┌────────┐│
│  │ 🔗  https://youtu.be/...                  │  │ Agregar││
│  └──────────────────────────────────────────┘  └────────┘│
│                                                            │
│  (Audio mp3)  (Video mp4 ●)   Calidad [1080p ▾]           │  ← chips segmentados
│  [ ] Subtítulos   [ ] Playlist   [✓] Auto-URL              │  ← toggles pill
│                                                            │
│  Guardar en   📁 /home/rafaelreyes/Downloads/Mi_musica     │
│                                                    [Cambiar]│
│                                                            │
│  COLA DE DESCARGAS                                   2 ítems│
│  ┌────────────────────────────────────────────────────┐  │
│  │ ⟢  https://youtu.be/J_sH-GrUeUw          Video · MP4│  │
│  │    ●●●●●●●●●● 100%                      Completado ✓│  │
│  ├────────────────────────────────────────────────────┤  │
│  │ ⟠  https://youtu.be/xxxxxxxxxxx          Audio · MP3│  │
│  │    ●●●●●●○○○○ 64%                       Descargando…│  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│  [ Iniciar descargas ]   [ Limpiar cola ]                 │
├──────────────────────────────────────────────────────────┤
│  ● Listo                                    2 en cola · 1 activa │  ← status bar
└──────────────────────────────────────────────────────────┘
```

---

## 5. Componentes clave

### 5.1 Barra superior
Quitar la barra de título nativa de Windows/GNOME y usar una propia (`overrideredirect` + hitbox de arrastre), igual en los tres sistemas operativos. El indicador "ffmpeg OK" pasa de texto verde suelto a un **badge**: punto de estado + texto, sobre `bg.surface`, radio 999.

### 5.2 Input de URL + Agregar
- Input: `bg.surface`, texto `JetBrains Mono` (una URL se lee mejor en monoespaciada), ícono de link a la izquierda dentro del campo.
- Botón "Agregar": único botón sólido en `accent.brand`, el resto de botones de la app son *outline* o *ghost*. Así el ojo va directo a la acción principal.

### 5.3 Opciones → chips segmentados
Reemplazar los checkboxes nativos:
- **Audio/Video**: control segmentado (como un switch de dos posiciones), no checkboxes sueltos — son mutuamente excluyentes, deben *verse* excluyentes.
- **Subtítulos / Playlist / Auto-URL**: pills tipo toggle (fondo `bg.surface` → `accent.brand` al activarse), con `corner_radius=999`.
- **Calidad**: dropdown con `corner_radius=8`, mismo alto que los chips para que la fila quede alineada.

### 5.4 Cola de descargas — el elemento de firma
Cada ítem es una tarjeta (`bg.surface`, radio 12), no una fila plana:
- Ícono/anillo circular a la izquierda que representa **visualmente** el progreso (0–100%) rellenando un círculo, en vez de la barra rectangular genérica. Color del anillo = color de estado (`accent.progress` mientras descarga, `accent.success` al completar, `accent.error` si falla).
- Debajo de la URL, una micro barra de progreso lineal fina (2px) como refuerzo, no como protagonista.
- Etiqueta de estado a la derecha en texto, no solo color, para accesibilidad (daltonismo).

*Nota de implementación:* CustomTkinter no tiene un widget de anillo nativo. Se dibuja con `tkinter.Canvas.create_arc` sobre el `CTkFrame` de la fila, actualizando el ángulo (`extent`) según el % de progreso. Es liviano y no requiere librerías extra.

### 5.5 Botones de acción
- "Iniciar descargas": sólido `accent.brand`.
- "Limpiar cola": *outline*, borde `border.subtle`, texto `text.secondary` — acción secundaria/destructiva, no debe competir con la principal.

### 5.6 Barra de estado inferior
Reemplaza la barra de progreso rosa genérica de abajo (que hoy no comunica nada por sí sola) por texto de estado + contador ("2 en cola · 1 activa"). El progreso real ya vive en cada tarjeta de la cola — no hace falta duplicarlo abajo.

---

## 6. Estados vacíos y de error

- **Cola vacía:** ilustración simple (círculo punteado + ícono de descarga) y el texto *"Pega una URL arriba para empezar"* — nunca dejar el espacio en blanco sin guía, como pasa hoy.
- **Error de descarga:** la tarjeta cambia el borde a `accent.error`, el anillo se detiene en el % donde falló, y el estado dice el motivo en una línea corta ("Error: URL no disponible"), con un botón pequeño "Reintentar" a la derecha.

---

## 7. Notas de implementación multiplataforma (CustomTkinter)

- Fijar `ctk.set_appearance_mode("dark")` y **no** usar `set_default_color_theme` de las plantillas predefinidas; definir los tokens de la sección 3 como diccionario propio (`COLORS = {...}`) para tener control total y consistencia entre OS.
- Cargar fuentes con `customtkinter.CTkFont(family=..., size=..., weight=...)`; empaquetar Inter/Sora/JetBrains Mono como `.ttf` dentro del proyecto y registrarlas en runtime (en Windows con `ctypes` + `AddFontResourceEx`, en Linux/macOS suelen funcionar si están en la carpeta de fuentes del usuario o cargadas vía `tkinter.font`).
- Windows: el degradado de la barra de título nativa no se puede personalizar fácilmente → usar `overrideredirect(True)` y reconstruir minimizar/cerrar como botones propios (igual que en el wireframe).
- macOS: cuidado con `overrideredirect` y el notch de cámara/menu bar; probar con `root.tk.call("::tk::unsupported::MacWindowStyle", ...)` si se quiere mantener los controles nativos en vez de una barra custom.
- Mantener un solo archivo `theme.py` con los tokens (colores, fuentes, radios, espaciados) para que cambiar la paleta completa sea una sola edición, no buscar y reemplazar por todo el código.

---

## 8. Resumen de qué cambia y por qué

| Antes | Después | Por qué |
|---|---|---|
| Un solo rosa para todo | 1 acento de marca + 3 colores de estado | El color vuelve a significar algo |
| Checkboxes nativos | Chips/pills segmentados | Coherencia visual, agrupa opciones excluyentes |
| Barra de progreso genérica abajo | Anillo de progreso por ítem + status bar textual | El progreso vive donde ocurre la acción |
| Espacio vacío sin propósito | Estado vacío con guía | Ninguna pantalla se siente "rota" o incompleta |
| Filas planas en la cola | Tarjetas con jerarquía clara | Cada descarga es una unidad legible de un vistazo |
