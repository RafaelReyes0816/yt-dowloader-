#!/usr/bin/env python3
"""Chequeo E2E obligatorio antes de taggear una release.

Descarga un video real usando la MISMA ruta de codigo que la app
(`core.descargar_musica`) y verifica el archivo resultante con `ffprobe`.

Motivo: el CI solo corre los tests offline; los bugs que solo aparecen al
descargar de verdad (p. ej. YouTube sirviendo AV1 y VLC sin poder abrirlo)
no se detectan hasta que un usuario abre el archivo.

Verifica:
  - video 720p -> contenedor mp4, video h264 (avc1), audio aac
  - audio 320  -> mp3 valido

Uso:
    .venv/bin/python core_tests/pre_release_check.py
Variables opcionales:
    PRE_RELEASE_URL   (default: video corto y estable de YouTube)
    PRE_RELEASE_RES   (default: 720p)
Codigo de salida 0 si todo OK; 1 si algo falla (NO taggear).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import core  # noqa: E402

URL = os.environ.get("PRE_RELEASE_URL", "https://www.youtube.com/watch?v=jNQXAC9IVRw")
RES_VIDEO = os.environ.get("PRE_RELEASE_RES", "720p")


def _exigir(condicion, mensaje):
    if not condicion:
        raise RuntimeError(mensaje)


def _ffprobe():
    carpeta = core.find_ffmpeg()
    nombre = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    if carpeta:
        ruta = os.path.join(carpeta, nombre)
        if os.path.isfile(ruta):
            return ruta
    return shutil.which("ffprobe")


def _streams(ffprobe, archivo):
    salida = subprocess.run(
        [ffprobe, "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", archivo],
        capture_output=True, text=True, check=True,
    )
    return json.loads(salida.stdout)


def _un_archivo(carpeta, extensiones):
    for nombre in sorted(os.listdir(carpeta)):
        if nombre.lower().endswith(tuple(extensiones)):
            return os.path.join(carpeta, nombre)
    return None


def _check_video(ffprobe, archivo):
    datos = _streams(ffprobe, archivo)
    video = next((s for s in datos["streams"] if s.get("codec_type") == "video"), None)
    audio = next((s for s in datos["streams"] if s.get("codec_type") == "audio"), None)
    _exigir(video is not None, "el mp4 no tiene pista de video")
    _exigir(audio is not None, "el mp4 no tiene pista de audio")
    _exigir(video["codec_name"] == "h264",
            f"video='{video['codec_name']}' (se esperaba h264/avc1 para que VLC lo abra)")
    _exigir(audio["codec_name"] == "aac",
            f"audio='{audio['codec_name']}' (se esperaba aac)")
    contenedor = datos["format"]["format_name"]
    _exigir("mp4" in contenedor, f"contenedor='{contenedor}' (se esperaba mp4)")
    return (f"video={video['codec_name']} {video.get('width')}x{video.get('height')} "
            f"audio={audio['codec_name']} contenedor={contenedor}")


def _check_audio(ffprobe, archivo):
    datos = _streams(ffprobe, archivo)
    audio = next((s for s in datos["streams"] if s.get("codec_type") == "audio"), None)
    _exigir(audio is not None, "el mp3 no tiene pista de audio")
    _exigir(audio["codec_name"] == "mp3",
            f"audio='{audio['codec_name']}' (se esperaba mp3)")
    return f"audio={audio['codec_name']}"


def main():
    ffprobe = _ffprobe()
    if not ffprobe:
        print("FALLO: ffprobe no encontrado (instala ffmpeg y ponlo en PATH).")
        return 1
    print(f"URL: {URL}")
    print(f"ffprobe: {ffprobe}")
    fallos = []
    with tempfile.TemporaryDirectory(prefix="pre-release-") as base:
        for modo, calidad, extensiones, check in (
            ("video", RES_VIDEO, (".mp4",), _check_video),
            ("audio", "320", (".mp3",), _check_audio),
        ):
            carpeta = os.path.join(base, modo)
            os.makedirs(carpeta, exist_ok=True)
            print(f"\n--- {modo} ({calidad}) ---")
            try:
                core.descargar_musica(URL, carpeta, modo, calidad)
            except Exception as exc:  # noqa: BLE001
                fallos.append(f"{modo}: la descarga lanzo {type(exc).__name__}: {exc}")
                print(f"FALLO: {fallos[-1]}")
                continue
            archivo = _un_archivo(carpeta, extensiones)
            if not archivo:
                fallos.append(f"{modo}: no se genero ningun {extensiones} en {carpeta}")
                print(f"FALLO: {fallos[-1]}")
                continue
            try:
                detalle = check(ffprobe, archivo)
            except Exception as exc:  # noqa: BLE001
                fallos.append(f"{modo}: {exc}")
                print(f"FALLO: {fallos[-1]}")
                continue
            print(f"OK: {os.path.basename(archivo)} -> {detalle}")
    print()
    if fallos:
        print("RESULTADO: FALLO")
        for fallo in fallos:
            print(f"  - {fallo}")
        print("NO taggear la release.")
        return 1
    print("RESULTADO: OK - seguro para taggear la release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
