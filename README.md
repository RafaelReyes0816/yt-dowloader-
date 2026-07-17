# YT-DownLoader del Jaeger

**YT-DownLoader del Jaeger** es una aplicación de escritorio en Python que te permite descargar audio (mp3) o video (mp4) de YouTube con una interfaz moderna y elegante.

## Características

- Descarga audio en formato **mp3** (calidad seleccionable: 128, 192, 256, 320 kbps)
- Descarga video en formato **mp4** (calidad seleccionable: 360p, 480p, 720p, 1080p)
- Interfaz gráfica moderna con tema oscuro (ttkbootstrap)
- Barra de progreso en tiempo real
- Verificación automática de actualizaciones
- Compatible con Linux, Windows y macOS

## Instalación

### Descargar ejecutable

Descarga la última versión desde [Releases](https://github.com/RafaelReyes0816/yt-dowloader-/releases). No requiere Python instalado.

**Windows:** El ejecutable ya incluye ffmpeg. Solo descarga y ejecuta.

**Linux:** Instala ffmpeg antes de usar:
```bash
sudo apt install ffmpeg
```

**macOS:** Instala ffmpeg antes de usar:
```bash
brew install ffmpeg
```

### Ejecutar desde código fuente

```bash
git clone https://github.com/RafaelReyes0816/yt-dowloader-.git
cd yt-dowloader-
pip install -r requirements.txt
python yt-dowloader.py
```

**Requisitos del sistema:**
- Python 3.8 o superior
- `ffmpeg` instalado y en PATH (requerido para conversión a mp3/mp4)
- En Linux: `sudo apt install python3-tk` (si no viene incluido)

## Build standalone

```bash
pip install pyinstaller yt-dlp ttkbootstrap
pyinstaller yt-dowloader.spec
```

El ejecutable se genera en `dist/`.

## Arquitectura

- `yt-dowloader.py` — App completa: interfaz tkinter/ttkbootstrap + lógica de descarga con yt-dlp
- `yt-dowloader.spec` — Configuración de PyInstaller (multiplataforma)
- `.github/workflows/build.yml` — CI/CD: build automático para Linux, Windows, macOS

## Distribución

Los ejecutables se generan automáticamente via GitHub Actions al crear un tag `v*`:

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

Desarrollado por Rafael Reyes (Jaeger).
