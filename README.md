# YT-DownLoader del Jaeger

**YT-DownLoader del Jaeger** es una aplicación de escritorio en Python que te permite descargar audio (mp3) o video (mp4) de múltiples plataformas, con una interfaz moderna, cola de descargas y soporte de autenticación.

<img src="assets/icons/icon.png" width="128" alt="Logo">

## Plataformas compatibles

YouTube, Instagram, Facebook, TikTok, Twitch, Vimeo, Twitter/X y Reddit.

## Características

- **Descarga audio** en formato mp3 (calidad seleccionable: 128–320 kbps).
- **Descarga video** en formato mp4 (resoluciones YouTube: 360p hasta 2160p/4K; otras plataformas: calidad genérica).
- **Pistas de audio adicionales** (YouTube): lista los audios extra (original y doblajes) y permite descargar cada uno por separado, en su contenedor nativo (`m4a`/`webm`), dentro de `Título [id]/audio adicional - <idioma>.<ext>`. El audio del video no se modifica.
- **Cola de descargas** con soporte para múltiples archivos simultáneos, botón de cancelar por item y "Detener todo".
- **Descarga paralela** opcional (1–3 descargas simultáneas, configurable en preferencias).
- **Autenticación vía navegador**: si un video requiere sesión (privado, miembros, age-gated), la app puede usar cookies de Firefox/Chrome/Brave/Edge automáticamente sin almacenar credenciales.
- **Ventana de diagnóstico**: verificación de ffmpeg, navegador disponible, versión de yt-dlp instalada vs. última en PyPI, con botón de actualización.
- **Privacidad de URLs**: las URLs se muestran enmascaradas en la cola y el historial (por defecto activado).
- **Atajos de teclado**: `Ctrl+Return` agregar URL, `Ctrl+L` limpiar campo, `Ctrl+D` activar/desactivar auto-URL del portapapeles.
- **Detección automática** de URLs copiadas al portapapeles.
- **Barra de progreso** por item con fases visibles: Descargando / Convirtiendo.
- **Verificación de actualizaciones** de la app al iniciar (via GitHub Releases).

## Instalación

### Descargar ejecutable (recomendado)

Descarga la última versión desde [Releases](https://github.com/RafaelReyes0816/yt-dowloader-/releases). No requiere Python instalado.

| Plataforma | Notas |
|---|---|
| **Windows** | El ejecutable incluye ffmpeg. Solo descargar y ejecutar. |
| **Linux** | Instalar ffmpeg: `sudo apt install ffmpeg` |
| **macOS** | Instalar ffmpeg: `brew install ffmpeg` |

### Ejecutar desde código fuente

```bash
git clone https://github.com/RafaelReyes0816/yt-dowloader-.git
cd yt-dowloader-
pip install -r requirements.txt
python yt-dowloader.py
```

**Requisitos del sistema:**
- Python 3.8 o superior.
- `ffmpeg` instalado y en PATH (requerido para conversión a mp3 y muxing de mp4).
- Linux: `sudo apt install python3-tk` si tkinter no viene incluido.

## Pistas de audio adicionales (solo YouTube)

Algunos videos de YouTube traen varias pistas de audio (el audio original y uno o más doblajes). La app te deja descargarlas **por separado, sin tocar el video**.

**Cómo descargarlas**

1. Pega la URL del video de YouTube.
2. Pulsa **Buscar pistas**. Aparece la lista de pistas disponibles (idioma y contenedor, p. ej. `Spanish`, `Portuguese`, `English (US)`).
3. Marca las que quieras y pulsa **Agregar a la cola**. Cada pista se descarga como un item independiente (puedes cancelarla sola).

**Dónde quedan los archivos**

```
Mi_musica/
├── Título del video [ID].mp4        ← el video (audio original intacto)
└── Título del video [ID]/
    ├── audio adicional - Spanish.m4a
    └── audio adicional - Portuguese.webm
```

**Cómo reproducirlas / importarlas en tu reproductor**

| Contenedor | Qué es | Compatibilidad |
|---|---|---|
| `.m4a` | audio AAC | Universal: VLC, mpv, foobar2000, Windows Media Player, Reproductor de Windows, Música (macOS/iOS), Android, etc. |
| `.webm` | audio Opus | VLC, mpv y foobar2000 (con Opus). Otros reproductores pueden no abrirlo. |

- **VLC (todas las plataformas)**: `Medio → Abrir archivo…` y elige el archivo, o arrástralo sobre la ventana. Para ambos formatos a la vez: `Medio → Abrir carpeta…` sobre la subcarpeta `Título [ID]/`.
- **Windows**: con `.m4a`, clic derecho → *Abrir con* → Reproductor de Windows / Windows Media Player, o *Agregar a la biblioteca*. El `.webm` normalmente necesita VLC.
- **macOS**: doble clic en el `.m4a` (se abre en Música) o arrástralo a *Música* para importarlo a la biblioteca. El `.webm` ábrelo con VLC.
- **Linux**: `vlc "audio adicional - Spanish.m4a"` o ábrelo desde el reproductor; los reproductores con GStreamer necesitan `gstreamer1.0-plugins-bad` para Opus.
- **Android / iOS**: copia la carpeta al teléfono y ábrela con VLC; el `.m4a` también funciona en el reproductor del sistema.

**Si tu reproductor no abre el `.webm` (Opus)**, conviértelo a `.m4a` (AAC) o `.mp3` con ffmpeg:

```bash
ffmpeg -i "audio adicional - Portuguese.webm" -c:a aac "audio adicional - Portuguese.m4a"
ffmpeg -i "audio adicional - Portuguese.webm" -c:a libmp3lame -q:a 2 "audio adicional - Portuguese.mp3"
```

**Si quieres dejar una pista como audio fijo del video** (por ejemplo, para compartirlo con el doblaje ya incluido):

```bash
ffmpeg -i "Título del video [ID].mp4" -i "Título del video [ID]/audio adicional - Spanish.m4a" \
  -map 0:v -map 1:a -c copy "Título del video [ID] (Spanish).mp4"
```

> La app no modifica el archivo de video original: las pistas extra se guardan aparte para que tú decidas qué hacer con ellas.

## Build standalone (ejecutable sin Python)

```bash
pip install pyinstaller yt-dlp customtkinter
pyinstaller yt-dowloader.spec
```

El ejecutable se genera en `dist/`. El spec es **multiplataforma** — PyInstaller detecta el SO automáticamente.

## CI/CD

El workflow de GitHub Actions (`.github/workflows/build.yml`) construye ejecutables para Linux, Windows (x64) y macOS (Intel + ARM) automáticamente al hacer push de un tag `v*`:

```bash
git tag v3.3.0
git push origin v3.3.0
```

Los ejecutables se publican en [Releases](https://github.com/RafaelReyes0816/yt-dowloader-/releases) vía `softprops/action-gh-release`.

## Arquitectura

```
yt-dowloader.py   ─ UI (CustomTkinter): App, VentanaDiagnostico, QueueCard,
                     SegmentedControl, PillToggle, Annunciador, SpinnerRing
core.py           ─ Lógica pura (testable): descarga, verificación, errores,
                     preferencias, auto-update. Sin UI ni network en import.
theme.py          ─ Design tokens (colores, fuentes, radios) + GLYPHS
yt-dowloader.spec ─ Configuración de PyInstaller (multiplataforma)
assets/icons/     ─ icon.png / icon.ico / icon.icns
core_tests/       ─ Tests unitarios (pytest) + tests live de plataformas
```

## Tests

```bash
# Suite completa (unitarios, sin red)
.venv/bin/python -m pytest core_tests/test_core.py -m "not live" -q

# Tests live (golpean URLs reales, solo bajo demanda)
.venv/bin/python -m pytest core_tests/test_plataformas_live.py -m live -v
```

El CI ejecuta la suite por defecto antes de cada release; un fallo bloquea la build.

## Notas

- El typo `dowloader` (sin 'n') es **intencional** — coincide con el nombre de salida del spec de PyInstaller. No renombrar sin actualizar el spec.
- La interfaz está 100% en español.
- `GITHUB_REPO` en `core.py` debe coincidir con el path del repositorio en GitHub para que el auto-update funcione.

---

Desarrollado por Rafael Reyes (Jaeger).
