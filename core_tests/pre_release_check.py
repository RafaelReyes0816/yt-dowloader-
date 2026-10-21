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
  - YouTube    -> el nombre del archivo lleva el sufijo " [id]" (unicidad)
  - subtitulos -> el .vtt cae en la MISMA carpeta que el medio (no en una
                  subcarpeta "Titulo [id]/")

Uso:
    .venv/bin/python core_tests/pre_release_check.py
    .venv/bin/python core_tests/pre_release_check.py --url "https://..." --res 1080p
    .venv/bin/python core_tests/pre_release_check.py --navegador firefox
    .venv/bin/python core_tests/pre_release_check.py --solo subtitulos

Codigo de salida 0 si todo OK; 1 si algo falla (NO taggear).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import core  # noqa: E402

URL_DEFECTO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
RES_DEFECTO = "720p"
MODOS = ("video", "audio", "subtitulos")


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
    """Primer archivo de la propia carpeta (no de subcarpetas)."""
    for nombre in sorted(os.listdir(carpeta)):
        if nombre.lower().endswith(tuple(extensiones)):
            return os.path.join(carpeta, nombre)
    return None


def _id_de_youtube(url):
    try:
        consulta = urllib.parse.urlparse(url).query
        valores = urllib.parse.parse_qs(consulta)
        if "v" in valores and valores["v"]:
            return valores["v"][0]
    except Exception:  # noqa: BLE001
        pass
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


def _check_nombre_id(archivo, url):
    """En YouTube el archivo debe llevar el sufijo ' [id]' (evita colisiones)."""
    if core.detectar_plataforma(url) != "YouTube":
        return "no aplica (no es YouTube)"
    id_video = _id_de_youtube(url)
    if not id_video:
        return "no se pudo deducir el id de la URL"
    nombre = os.path.basename(archivo)
    _exigir(f"[{id_video}]" in nombre,
            f"el nombre '{nombre}' no lleva el sufijo ' [{id_video}]'")
    return f"nombre='{nombre}' con [id]"


def _check_subtitulos(carpeta, archivo_medio):
    """El .vtt debe caer junto al medio, no en una subcarpeta."""
    subtitulos = _un_archivo(carpeta, (".vtt",))
    if subtitulos:
        _exigir(os.path.dirname(os.path.abspath(subtitulos)) ==
                os.path.dirname(os.path.abspath(archivo_medio)),
                f"el .vtt esta en '{subtitulos}' y el medio en '{archivo_medio}': "
                "deben compartir carpeta")
        return subtitulos, os.path.basename(subtitulos)

    # ¿quedo en una subcarpeta? (regresion de las carpetas "Titulo [id]/").
    for raiz, _dirs, archivos in os.walk(carpeta):
        for nombre in archivos:
            if nombre.lower().endswith(".vtt"):
                raise RuntimeError(
                    f"el .vtt quedo en '{os.path.join(raiz, nombre)}' y no junto al medio: "
                    "los subtitulos deben escribirse en la misma carpeta")
    return None, "no se genero .vtt (este video puede no tener subtitulos)"


def _descargar(url, carpeta, modo, calidad, subtitulos, navegador):
    exito, mensaje, tipo = core.descargar_musica(
        url, carpeta, modo, calidad,
        subtitulos=subtitulos,
        navegador=navegador,
    )
    if not exito:
        raise RuntimeError(f"la descarga fallo ({tipo}): {mensaje}")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Chequeo E2E previo a una release.")
    parser.add_argument("--url", default=URL_DEFECTO, help="URL a descargar")
    parser.add_argument("--res", default=RES_DEFECTO, help="calidad de video (ej. 720p)")
    parser.add_argument("--navegador", default=None,
                        help="navegador del que tomar cookies (firefox, brave, ...)")
    parser.add_argument("--solo", choices=MODOS, default=None,
                        help="ejecutar solo un modo")
    args = parser.parse_args(argv)

    ffprobe = _ffprobe()
    if not ffprobe:
        print("FALLO: ffprobe no encontrado (instala ffmpeg y ponlo en PATH).")
        return 1

    modos = [args.solo] if args.solo else ["video", "audio", "subtitulos"]
    print(f"URL: {args.url}")
    print(f"Resolucion: {args.res}")
    print(f"Navegador: {args.navegador or '(ninguno)'}")
    print(f"ffprobe: {ffprobe}")
    print(f"Modos: {', '.join(modos)}")

    fallos = []
    avisos = []
    with tempfile.TemporaryDirectory(prefix="pre-release-") as base:
        for modo in modos:
            carpeta = os.path.join(base, modo)
            os.makedirs(carpeta, exist_ok=True)
            print(f"\n--- {modo} ---")
            try:
                _descargar(args.url, carpeta, modo, args.res,
                           modo == "subtitulos", args.navegador)
            except Exception as exc:  # noqa: BLE001
                fallos.append(f"{modo}: {exc}")
                print(f"FALLO: {fallos[-1]}")
                continue

            if modo == "video":
                archivo = _un_archivo(carpeta, (".mp4",))
                if not archivo:
                    fallos.append(f"{modo}: no se genero ningun .mp4 en {carpeta}")
                    print(f"FALLO: {fallos[-1]}")
                    continue
                try:
                    print(f"OK: {os.path.basename(archivo)} -> {_check_video(ffprobe, archivo)}")
                    print(f"OK: {_check_nombre_id(archivo, args.url)}")
                except Exception as exc:  # noqa: BLE001
                    fallos.append(f"{modo}: {exc}")
                    print(f"FALLO: {fallos[-1]}")
            elif modo == "audio":
                archivo = _un_archivo(carpeta, (".mp3",))
                if not archivo:
                    fallos.append(f"{modo}: no se genero ningun .mp3 en {carpeta}")
                    print(f"FALLO: {fallos[-1]}")
                    continue
                try:
                    print(f"OK: {os.path.basename(archivo)} -> {_check_audio(ffprobe, archivo)}")
                except Exception as exc:  # noqa: BLE001
                    fallos.append(f"{modo}: {exc}")
                    print(f"FALLO: {fallos[-1]}")
            else:  # subtitulos
                archivo = _un_archivo(carpeta, (".mp4", ".mkv", ".webm"))
                if not archivo:
                    fallos.append(f"{modo}: no se genero ningun medio en {carpeta}")
                    print(f"FALLO: {fallos[-1]}")
                    continue
                try:
                    vtt, detalle = _check_subtitulos(carpeta, archivo)
                except Exception as exc:  # noqa: BLE001
                    fallos.append(f"{modo}: {exc}")
                    print(f"FALLO: {fallos[-1]}")
                    continue
                if vtt is None:
                    if args.solo == "subtitulos":
                        fallos.append(f"{modo}: {detalle}")
                        print(f"FALLO: {fallos[-1]}")
                    else:
                        avisos.append(f"{modo}: {detalle}")
                        print(f"AVISO: {detalle}")
                else:
                    print(f"OK: {detalle} (junto al medio, sin subcarpeta)")

    print()
    for aviso in avisos:
        print(f"  aviso: {aviso}")
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
