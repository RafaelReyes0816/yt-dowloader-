"""Diagnostico de cookies para yt-downloader.

Prueba una URL de YouTube contra cada navegador configurado y contra los
clientes de fallback de yt-dlp, e imprime el resultado exacto de cada
intento. No descarga nada ni modifica datos: solo consulta la sesion.

Uso:
    python diagnostico_cookies.py [URL]

Por defecto usa una URL publica de YouTube (video musical corto).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402

URL_DEFECTO = "https://www.youtube.com/watch?v=EfmPza0lgYw"


class _LoggerSilencioso:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def _silenciar_ytdlp():
    _orig = core.yt_dlp.YoutubeDL

    class _YDL(_orig):
        def __init__(self, params=None, *a, **k):
            params = dict(params or {})
            params.setdefault("logger", _LoggerSilencioso())
            super().__init__(params, *a, **k)

    core.yt_dlp.YoutubeDL = _YDL


def _linea(titulo):
    print("\n" + "=" * 64)
    print(titulo)
    print("=" * 64)


def probar_verificacion(url):
    _linea("VERIFICACION SIN COOKIES (fallback de clientes + navegadores)")
    res = core.verificar_url(url)
    restr = res.get("restriccion")
    if res.get("info") and not restr:
        print("OK  · acceso libre (sin cookies)")
        return True
    tipo = (restr or {}).get("tipo", "?")
    print(f"RESTRINGIDO · {tipo}")
    detalle = (restr or {}).get("detalle", "") or ""
    if detalle:
        print("Detalle:", detalle.strip().splitlines()[0][:240])
    return False


def probar_navegador(url, navegador):
    print(f"\n--- {navegador.upper()} ---")
    print("  cookies_from_browser ->", core.construir_opciones_cookies(navegador))
    if navegador in core.NAVEGADORES_GECKO and navegador != "firefox":
        perfil = core.perfil_gecko(navegador)
        print("  perfil gecko ->", perfil or "(no encontrado)")
    try:
        res = core.verificar_url(url, navegador)
    except Exception as e:  # noqa: BLE001
        print("  EXCEPCION:", repr(e)[:220])
        return
    restr = res.get("restriccion")
    if res.get("info") and not restr:
        print(f"  OK  · {navegador} entrego sesion valida")
        return
    tipo = (restr or {}).get("tipo", "?")
    print(f"  FALLO · {tipo}")
    detalle = (restr or {}).get("detalle", "") or ""
    if detalle:
        print("  Detalle:", detalle.strip().splitlines()[0][:240])


def listar_rutas():
    _linea("RUTAS CONFIGURADAS Y EXISTENCIA")
    for nombre, rutas in core.NAVEGADORES_RUTAS.items():
        for ruta in rutas.get(sys.platform, []):
            existe = "SI" if os.path.isdir(ruta) else "no"
            print(f"  {nombre:10} [{existe}] {ruta}")


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else URL_DEFECTO
    _silenciar_ytdlp()
    print("yt-downloader · diagnostico de cookies")
    print("yt-dlp:", core.yt_dlp.version.__version__)
    print("plataforma:", sys.platform)
    print("URL:", url)

    _linea("NAVEGADORES DETECTADOS")
    detectados = core.detectar_navegadores()
    print(detectados or "(ninguno)")

    listar_rutas()

    probar_verificacion(url)

    _linea("PRUEBA POR NAVEGADOR")
    for nav in list(core.NAVEGADORES_RUTAS.keys()):
        probar_navegador(url, nav)

    _linea("FIN")
    print("Pega TODO este texto en el reporte.")


if __name__ == "__main__":
    main()
