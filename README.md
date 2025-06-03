# YT-DownLoader del Jaeger

🎵 **YT-DownLoader del Jaeger** es una aplicación de escritorio en Python que te permite descargar audio (mp3) o video (mp4) de YouTube de manera sencilla y elegante, eligiendo la calidad que prefieras. Cuenta con una interfaz gráfica moderna y personalizable.

## Características
- Descarga audio en formato **mp3** (calidad seleccionable: 128, 192, 256, 320 kbps)
- Descarga video en formato **mp4** (calidad seleccionable: 360p, 480p, 720p, 1080p)
- Interfaz gráfica elegante y oscura
- Selección fácil de formato y calidad
- Descarga individual (no playlist completa)
- Compatible con Linux, Windows y MacOS

## Requisitos
- Python 3.8 o superior
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/) (para la conversión a mp3/mp4)
- Tkinter (normalmente incluido en Python, en Linux puede requerir `sudo apt install python3-tk`)

## Instalación
1. **Clona el repositorio:**
   ```bash
   git clone https://github.com/tuusuario/Youtube-Dowloader.git
   cd Youtube-Dowloader
   ```
2. **Crea y activa un entorno virtual (opcional pero recomendado):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```
3. **Instala las dependencias:**
   ```bash
   pip install yt-dlp
   pip install pyinstaller
   # Asegúrate de tener ffmpeg instalado en tu sistema
   ```

## Uso
1. Ejecuta la aplicación:
   ```bash
   python yt-dowloader.py
   ```
2. Pega la URL del video de YouTube.
3. Elige si quieres descargar audio (mp3) o video (mp4).
4. Selecciona la calidad deseada.
5. Haz clic en **Descargar**.
6. El archivo se guardará en la carpeta `Mi_musica` dentro del proyecto.

## Captura de pantalla
_Agrega aquí una imagen de la interfaz ejecutando el programa:_

```
![screenshot](screenshot.png)
```

## Créditos y agradecimientos
- Inspirado por la comunidad open source.
- Usa [yt-dlp](https://github.com/yt-dlp/yt-dlp) y [ffmpeg](https://ffmpeg.org/).
- Desarrollado por Rafael Reyes (Jaeger).

---
¡Disfruta descargando tu música y videos favoritos de YouTube! 🎶 