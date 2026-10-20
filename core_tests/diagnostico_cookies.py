"""Diagnóstico de cookies para yt-downloader.

Prueba una URL de YouTube contra cada navegador detectado y contra los
clientes de fallback de yt-dlp, e imprime el resultado exacto de cada
intento. No descarga nada ni modifica datos: solo consulta la sesión.

Uso:
    python diagnostico_cookies.py [URL]

Por defecto usa la URL reportada por el usuario en el issue.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402

URL_DEFECTO = "https://www.youtube.com/watch?v=EfmPzaOlgYw"


def _linea(titulo):
    print("\n" + "=" * 60)
    print(titulo)
    print("=" * 60)


def probar_verificacion(url):
    _linea("VERIFICACION SIN COOKIES (fallback de clientes)")
    res = core.verificar_url(url)
    restr = res.get("restriccion")
    if res.get("info") and not restr:
        print("OK  · acceso libre (sin cookies)")
        return True
    tipo = (restr or {}).get("tipo", "?")
    print(f"RESTRINGIDO · {tipo}")
    detalle = (restr or {}).get("detalle", "") or ""
    if detalle:
        print("Detalle:", detalle.strip().splitlines()[0][:200])
    return False


def probar_navegador(url, navegador):
    print(f"\n--- {navegador.upper()} ---")
    try:
        res = core.verificar_url(url, navegador)
    except Exception as e:  # noqa: BLE001
        print("EXCEPCION:", repr(e)[:200])
        return
    restr = res.get("restriccion")
    if res.get("info") and not restr:
        print(f"OK  · {navegador} entrego sesion valida")
        return
    tipo = (restr or {}).get("tipo", "?")
    print(f"FALLO · {tipo}")
    detalle = (restr or {}).get("detalle", "") or ""
    if detalle:
        print("Detalle:", detalle.strip().splitlines()[0][:220])


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else URL_DEFECTO
    print("yt-downloader · diagnostico de cookies")
    print("yt-dlp:", core.yt_dlp.version.__version__)
    print("plataforma:", sys.platform)
    print("URL:", url)

    _linea("NAVEGADORES DETECTADOS")
    detectados = core.detectar_navegadores()
    print(detectados or "(ninguno)")

    probar_verificacion(url)

    _linea("PRUEBA POR NAVEGADOR")
    for nav in ("brave", "edge", "firefox"):
        probar_navegador(url, nav)
    print("\nZen (fork de Firefox) se lee por el slot 'firefox'.")
    print("Si 'FIREFOX' dio OK, Zen/el perfil default-release sirve.")

    _linea("FIN")
    print("Pega TODO este texto en el reporte.")


if __name__ == "__main__":
    main()
