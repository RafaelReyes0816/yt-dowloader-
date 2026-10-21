#!/usr/bin/env python3
"""Smoke test de la UI: arranca la app y comprueba que la ventana vive.

El CI solo puede correr la suite offline de pytest (no hay red garantizada y
no se deben descargar archivos en cada build). Este script cubre lo que los
tests offline no ven: que `yt-dowloader.py` importa, que `App` se construye
sin romperse, que la cola acepta una URL y que el layout responsive reacciona
a un cambio de tamano.

Es HERMETICO: no toca la red (la comprobacion de actualizaciones se
desactiva) ni el portapapeles real, asi que se puede correr en CI con:

    xvfb-run -a python core_tests/smoke_ui.py

Codigo de salida 0 si todo va bien; 1 si algo falla.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

URL_PRUEBA = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _esperar(app, condicion, timeout_ms=3000):
    """Bombea el bucle de eventos hasta que `condicion()` sea cierta.

    Necesario porque la app usa `after()` (debounce de 300 ms en la
    validacion inline, 80 ms en el resize): `update()` no ejecuta un timer
    que aun no ha vencido."""
    limite = time.time() + timeout_ms / 1000
    while time.time() < limite:
        app.update()
        if condicion():
            return True
        time.sleep(0.02)
    return bool(condicion())


def _cargar_app():
    ruta = os.path.join(RAIZ, "yt-dowloader.py")
    spec = importlib.util.spec_from_file_location("yt_dowloader_app", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _neutralizar_red(app_mod):
    """Deja la app sin red y sin portapapeles (CI headless)."""
    app_mod.obtener_release_latest = lambda *a, **k: None
    app_mod.debe_revisar_update = lambda *a, **k: False


def _checks(app):
    fallos = []

    def comprobar(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    # 1) la ventana existe
    comprobar(app.winfo_exists() == 1, "la ventana principal no existe")

    # 2) la entrada de URL existe y acepta texto
    app.url_entry.delete(0, "end")
    app.url_entry.insert(0, URL_PRUEBA)
    app.update_idletasks()
    comprobar(app.url_entry.get() == URL_PRUEBA, "la entrada de URL no guarda el texto")

    # 3) la validacion inline reconoce una URL valida
    app._programar_validacion_inline()
    _esperar(app, lambda: app._url_valida)
    comprobar(app._url_valida, "la URL de prueba no se marco como valida")

    # 4) la cola acepta el item
    app._agregar_a_cola()
    app.update()
    comprobar(len(app.queue_items) == 1,
              f"la cola deberia tener 1 item, tiene {len(app.queue_items)}")
    if app.queue_items:
        item = app.queue_items[0]
        comprobar(item.get("url") == URL_PRUEBA, "el item de la cola no guarda la URL")
        comprobar(bool(app._titulo_item(item)), "el item de la cola no tiene titulo")

    # 5) la feature de pistas de audio (v3.5.0) no debe reaparecer
    comprobar(not hasattr(app, "pistas_frame"),
              "la UI no debe tener atributo 'pistas_frame' (feature de v3.5.0)")

    # 6) layout responsive: 1 columna y 2 columnas
    app.geometry("900x700")
    app.update()
    _esperar(app, lambda: app._modo_layout == "una_columna", timeout_ms=1500)
    comprobar(app._modo_layout == "una_columna",
              f"se esperaba 'una_columna' por debajo del breakpoint, hay {app._modo_layout}")
    app.geometry("1400x900")
    app.update()
    _esperar(app, lambda: app._modo_layout == "dos_columnas", timeout_ms=1500)
    comprobar(app._modo_layout == "dos_columnas",
              f"se esperaban 'dos_columnas' por encima del breakpoint, hay {app._modo_layout}")

    return fallos


def main():
    try:
        app_mod = _cargar_app()
        _neutralizar_red(app_mod)
    except Exception:
        print("FALLO: no se pudo importar yt-dowloader.py")
        traceback.print_exc()
        return 1

    app = None
    try:
        app = app_mod.App()
        app.update_idletasks()
        fallos = _checks(app)
    except Exception as exc:  # noqa: BLE001
        print(f"FALLO: excepcion durante el smoke: {exc}")
        traceback.print_exc()
        return 1
    finally:
        if app is not None:
            try:
                app.destroy()
            except Exception:  # noqa: BLE001
                pass

    if fallos:
        print("SMOKE FAIL")
        for fallo in fallos:
            print(f"  - {fallo}")
        return 1

    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
