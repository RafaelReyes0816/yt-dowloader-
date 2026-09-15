# YT-DownLoader del Jaeger

**YT-DownLoader del Jaeger** es una aplicación de escritorio en Python que te permite descargar audio (mp3) o video (mp4) de múltiples plataformas, con una interfaz moderna, cola de descargas y soporte de autenticación.

<img src="assets/icons/icon.png" width="128" alt="Logo">

## Plataformas compatibles

YouTube, Instagram, Facebook, TikTok, Twitch, Vimeo, Twitter/X y Reddit.

## Características

- **Descarga audio** en formato mp3 (calidad seleccionable: 128–320 kbps).
- **Descarga video** en formato mp4 (resoluciones YouTube: 360p hasta 2160p/4K; otras plataformas: calidad genérica).
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
