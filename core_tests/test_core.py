import os
import threading

import pytest

import core
from core import (
    PLATFORM_REGEX,
    detectar_plataforma,
    es_youtube,
    ClasificadorErrores,
    comparar_versiones,
    _construir_opciones_descarga,
    _opciones_base,
    DescargaCancelada,
    PLATAFORMAS_CONFIG,
    RESOLUCIONES_YOUTUBE,
    RESOLUCIONES_GENERICAS,
    verificar_url,
    cargar_preferencias,
    guardar_preferencias,
    extraer_url_completa,
    enmascarar_url,
    sanitizar_detalle,
    sanear_texto_clipboard,
    descargar_musica,
)
from core import CALIDADES_AUDIO, CALIDADES_VIDEO
from core import (
    detectar_navegadores,
    elegir_navegador_sesion,
    navegadores_para_reintento,
    ORDEN_NAVEGADORES,
    CLIENTES_FALLBACK_BOT,
)


class TestDetectarPlataforma:
    @pytest.mark.parametrize("url,esperado", [
        ("https://www.youtube.com/watch?v=abc", "YouTube"),
        ("https://youtu.be/abc", "YouTube"),
        ("https://www.instagram.com/reel/abc/", "Instagram"),
        ("https://instagr.am/p/abc/", "Instagram"),
        ("https://www.facebook.com/watch/?v=1", "Facebook"),
        ("https://www.tiktok.com/@u/video/1", "TikTok"),
        ("https://vm.tiktok.com/abc/", "TikTok"),
        ("https://www.twitch.tv/videos/123", "Twitch"),
        ("https://vimeo.com/123456", "Vimeo"),
        ("https://twitter.com/user/status/1", "Twitter/X"),
        ("https://x.com/user/status/1", "Twitter/X"),
        ("https://www.reddit.com/r/x/comments/1/", "Reddit"),
        ("https://example.com/video", "Otra"),
    ])
    def test_deteccion(self, url, esperado):
        assert detectar_plataforma(url) == esperado

    def test_es_youtube(self):
        assert es_youtube("https://youtu.be/x") is True
        assert es_youtube("https://example.com") is False

    def test_case_insensitive(self):
        assert detectar_plataforma("HTTPS://WWW.YOUTUBE.COM/x") == "YouTube"


class TestPlataformaRegex:
    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=abc",
        "https://youtu.be/abc",
        "youtube.com/watch?v=x",
        "https://www.instagram.com/p/x/",
        "https://twitter.com/u/s/1",
        "www.twitch.tv/videos/1",
        "https://vimeo.com/1",
        "https://www.reddit.com/r/x/comments/1/",
    ])
    def test_reconocidas(self, url):
        assert PLATFORM_REGEX.search(url) is not None

    @pytest.mark.parametrize("url", [
        "",
        "https://example.com",
        "just random text",
        "https://mydomain.com/youtube",
    ])
    def test_no_reconocidas(self, url):
        assert PLATFORM_REGEX.search(url) is None


class TestClasificadorErrores:
    @pytest.mark.parametrize("mensaje,tipo_esperado", [
        ("ERROR: [youtube] abc: This video is private.", "private"),
        ("This video is members-only", "members_only"),
        ("Sign in to confirm your age", "age_restricted"),
        ("This video is not available in your country", "geo"),
        ("Video unavailable", "unavailable"),
        ("Log in to watch this video", "sign_in"),
        ("Please sign in to view this video", "sign_in"),
        ("Sign in to confirm you're not a bot", "bot"),
        ("This is not a valid URL", "invalid_url"),
        ("Video not found", "not_found"),
    ])
    def test_clasificacion(self, mensaje, tipo_esperado):
        import yt_dlp
        exc = yt_dlp.utils.DownloadError(mensaje)
        res = ClasificadorErrores.clasificar(exc, "YouTube")
        assert res["tipo"] == tipo_esperado

    def test_desconocido(self):
        import yt_dlp
        exc = yt_dlp.utils.DownloadError("completely weird gibberish error xxqp")
        res = ClasificadorErrores.clasificar(exc, "YouTube")
        assert res["tipo"] == "desconocido"
        assert res["sugerencia"] is None

    def test_detalle_truncado(self):
        import yt_dlp
        largo = "x" * 1000
        exc = yt_dlp.utils.DownloadError("Some odd error here " + largo)
        res = ClasificadorErrores.clasificar(exc, "YouTube")
        assert len(res["detalle"]) <= 404

    def test_mensaje_cambia_por_plataforma(self):
        import yt_dlp
        exc = yt_dlp.utils.DownloadError("This video is a private video")
        yt = ClasificadorErrores.clasificar(exc, "YouTube")
        ig = ClasificadorErrores.clasificar(exc, "Instagram")
        assert yt["mensaje"] != ig["mensaje"]

    def test_availability_map(self):
        res = ClasificadorErrores.clasificar_availability("private", "YouTube")
        assert res is not None and res["tipo"] == "private"
        assert ClasificadorErrores.clasificar_availability("public", "YouTube") is None

    @pytest.mark.parametrize("mensaje", [
        "ERROR: Could not copy Chrome cookie database. See https://github.com/yt-dlp/yt-dlp/issues/7271",
        "ERROR: Could not copy Edge cookie database.",
        "ERROR: Could not copy Brave cookie database.",
        "ERROR: could not copy firefox cookie database",
    ])
    def test_cookies_bloqueadas_por_navegador_abierto(self, mensaje):
        import yt_dlp
        res = ClasificadorErrores.clasificar(yt_dlp.utils.DownloadError(mensaje), "YouTube")
        assert res["tipo"] == "cookies"

    def test_sugerencia_cookies_menciona_cerrar_navegador(self):
        sugerencia = ClasificadorErrores.SUGERENCIAS.get("cookies", "").lower()
        assert "cierra" in sugerencia


class TestCompararVersiones:
    @pytest.mark.parametrize("v1,v2,esperado", [
        ("2.2.1", "2.2.0", 1),
        ("2.2.0", "2.2.1", -1),
        ("2.2.1", "2.2.1", 0),
        ("2.2", "2.2.1", -1),
        ("2025.1.1", "2024.10.10", 1),
    ])
    def test_comparar(self, v1, v2, esperado):
        assert comparar_versiones(v1, v2) == esperado


class TestConstruirOpciones:
    def test_youtube_audio_outtmpl_unicidad(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "audio", "320", False, False
        )
        assert "%(id)s" in opts["outtmpl"]
        assert os.path.join("/tmp/out", "") + "%(title)s [%(id)s].%(ext)s" in opts["outtmpl"].replace("\\\\", "/")

    def test_youtube_video_formato_1080p(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "video", "1080p", False, False
        )
        assert "1080" in opts["format"]
        assert opts["merge_output_format"] == "mp4"

    def test_no_youtube_outtmpl_sin_id(self):
        opts = _construir_opciones_descarga(
            "https://vimeo.com/123", "/tmp/out", "audio", "192", False, False
        )
        assert "%(id)s" not in opts["outtmpl"]
        assert "%(title)s.%(ext)s" in opts["outtmpl"]

    def test_subtitulos_solo_youtube(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "video", "720p", True, False
        )
        assert opts.get("writesubtitles") is True

        opts_ig = _construir_opciones_descarga(
            "https://instagram.com/p/x", "/tmp/out", "video", "720p", True, False
        )
        assert opts_ig.get("writesubtitles") is None

    def test_playlist_flag(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/playlist?list=x", "/tmp/out", "audio", "128", False, True
        )
        assert opts["noplaylist"] is False

    def test_descarga_incluye_socket_timeout_finito(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "audio", "128", False, False
        )
        assert isinstance(opts.get("socket_timeout"), (int, float))
        assert 0 < opts["socket_timeout"] <= 60


class TestDescargarMusicaCallbacks:
    """Regresión: descargar_musica debe cablear progress_callback/speed_callback
    sin referenciar nombres inexistentes (NameError) en ninguna rama."""

    def _fake_ydl(self, monkeypatch, capturadas):
        import core as core_mod

        class FakeYDL:
            def __init__(self, opciones):
                self.opciones = opciones
                capturadas.append(opciones)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def download(self, urls):
                for hook in self.opciones.get("progress_hooks", []):
                    hook({
                        "status": "downloading",
                        "total_bytes": 100,
                        "downloaded_bytes": 50,
                        "elapsed": 2,
                    })
                    hook({"status": "finished"})

        monkeypatch.setattr(core_mod.yt_dlp, "YoutubeDL", FakeYDL)
        return FakeYDL

    def test_progress_y_speed_callback_se_invokan(self, monkeypatch, tmp_path):
        capturadas = []
        self._fake_ydl(monkeypatch, capturadas)
        progreso, velocidad = [], []
        ok, mensaje, tipo = descargar_musica(
            "https://youtube.com/watch?v=x", str(tmp_path), "audio", "128",
            progress_callback=progreso.append,
            speed_callback=lambda v, d, t: velocidad.append((v, d, t)),
        )
        assert ok is True
        assert mensaje == "Descarga completada"
        assert tipo is None
        assert progreso == [0.5, 1.0]
        assert velocidad and velocidad[0][1] == 50

    def test_sin_callbacks_no_falla(self, monkeypatch, tmp_path):
        capturadas = []
        self._fake_ydl(monkeypatch, capturadas)
        ok, mensaje, tipo = descargar_musica(
            "https://youtube.com/watch?v=x", str(tmp_path), "video", "720p",
        )
        assert ok is True
        assert capturadas and capturadas[0].get("merge_output_format") == "mp4"

    def test_ydl_holder_se_limpia_al_terminar(self, monkeypatch, tmp_path):
        capturadas = []
        self._fake_ydl(monkeypatch, capturadas)
        holder = {}
        descargar_musica(
            "https://youtube.com/watch?v=x", str(tmp_path), "audio", "128",
            ydl_holder=holder,
        )
        assert holder.get("ydl") is None


class TestCancelacion:
    def test_hook_lanza_descarga_cancelada_cuando_flag_activo(self):
        flag = threading.Event()
        flag.set()
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "audio", "128", False, False,
            progreso_callback=lambda p: None, cancel_flag=flag,
        )
        hook = opts["progress_hooks"][0]
        with pytest.raises(DescargaCancelada):
            hook({"status": "downloading"})

    def test_hook_no_lanza_cuando_flag_inactivo(self):
        flag = threading.Event()
        prog = []
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "audio", "128", False, False,
            progreso_callback=prog.append, cancel_flag=flag,
        )
        hook = opts["progress_hooks"][0]
        hook({"status": "downloading", "total_bytes": 100, "downloaded_bytes": 50})
        hook({"status": "finished"})
        assert prog == [0.5, 1.0]


class TestOpcionesBaseAntiHang:
    def test_incluye_socket_timeout_finito(self):
        opts = _opciones_base()
        assert isinstance(opts.get("socket_timeout"), (int, float))
        assert 0 < opts["socket_timeout"] <= 60

    def test_socket_timeout_con_flag_y_navegador(self):
        opts = _opciones_base(navegador="firefox", cancel_flag=threading.Event())
        assert 0 < opts["socket_timeout"] <= 60

    def test_verificacion_no_recorre_playlist_completa(self):
        opts = _opciones_base()
        assert opts.get("noplaylist") is True

    def test_incluye_sleep_y_reintentos_extractor(self):
        opts = _opciones_base()
        assert opts.get("sleep_interval_requests") == 1
        assert opts.get("extractor_retries") == 3

    def test_impersonate_y_player_client_opcionales(self):
        opts = _opciones_base(impersonate="chrome", player_client="tv")
        assert opts.get("impersonate") == "chrome"
        assert opts.get("extractor_args") == {"youtube": {"player_client": ["tv"]}}

    def test_sin_impersonate_ni_player_client(self):
        opts = _opciones_base()
        assert "impersonate" not in opts
        assert "extractor_args" not in opts


class TestDeteccionNavegadores:
    def _perfiles(self, tmp_path, perfiles):
        raiz = tmp_path
        for nombre, archivo in perfiles.items():
            d = raiz / nombre
            d.mkdir(parents=True, exist_ok=True)
            (d / archivo).write_text("x")
        return raiz

    def test_ignora_carpeta_sin_archivo_perfil(self, monkeypatch, tmp_path):
        raiz = tmp_path / "User Data"
        raiz.mkdir(parents=True, exist_ok=True)
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "brave", {"linux": [str(raiz)]})
        assert detectar_navegadores() == []

    def test_detecta_con_archivo_perfil(self, monkeypatch, tmp_path):
        raiz = self._perfiles(tmp_path, {"brave": "Local State"})
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "brave", {"linux": [str(raiz / "brave")]})
        assert "brave" in detectar_navegadores()

    def test_ordena_por_mtime_mas_reciente(self, monkeypatch, tmp_path):
        base = self._perfiles(tmp_path, {"brave": "Local State", "firefox": "profiles.ini"})
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "brave", {"linux": [str(base / "brave")]})
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "firefox", {"linux": [str(base / "firefox")]})
        os.utime(base / "firefox" / "profiles.ini", (2000, 2000))
        os.utime(base / "brave" / "Local State", (1000, 1000))
        assert detectar_navegadores() == ["firefox", "brave"]

    def test_desempate_por_orden_preferido(self, monkeypatch, tmp_path):
        base = self._perfiles(tmp_path, {"brave": "Local State", "firefox": "profiles.ini"})
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "brave", {"linux": [str(base / "brave")]})
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "firefox", {"linux": [str(base / "firefox")]})
        os.utime(base / "firefox" / "profiles.ini", (1000, 1000))
        os.utime(base / "brave" / "Local State", (1000, 1000))
        assert detectar_navegadores() == ["firefox", "brave"]


class TestRutasNavegadores:
    def test_fork_gecko_tiene_rutas_en_los_tres_so(self):
        for nav in ("zen", "waterfox", "librewolf", "firefox"):
            rutas = core.NAVEGADORES_RUTAS[nav]
            assert rutas.get("win32") and rutas.get("darwin") and rutas.get("linux")

    def test_chromium_incluye_vivaldi_y_opera(self):
        for nav in ("vivaldi", "opera", "brave", "chrome", "edge"):
            rutas = core.NAVEGADORES_RUTAS[nav]
            assert rutas.get("win32") and rutas.get("darwin") and rutas.get("linux")

    def test_archivo_perfil_por_navegador(self):
        for nav in ("zen", "waterfox", "librewolf", "firefox"):
            assert core.NAVEGADORES_ARCHIVO_PERFIL[nav] == core.PERFIL_FIREFOX
        for nav in ("vivaldi", "opera", "brave", "chrome", "edge"):
            assert core.NAVEGADORES_ARCHIVO_PERFIL[nav] == core.PERFIL_CHROMIUM

    def test_navegadores_gecko(self):
        assert core.NAVEGADORES_GECKO == {"firefox", "zen", "waterfox", "librewolf"}


class TestPerfilGecko:
    def test_encuentra_perfil_con_cookies_mas_reciente(self, monkeypatch, tmp_path):
        raiz = tmp_path / "zen"
        (raiz / "Profiles" / "abc.default").mkdir(parents=True)
        (raiz / "Profiles" / "xyz.Default (release)").mkdir(parents=True)
        ini = raiz / "profiles.ini"
        ini.write_text(
            "[Profile0]\nName=default\nIsRelative=1\nPath=Profiles/abc.default\n\n"
            "[Profile1]\nName=Default (release)\nIsRelative=1\nPath=Profiles/xyz.Default (release)\n"
        )
        viejo = raiz / "Profiles" / "abc.default" / "cookies.sqlite"
        nuevo = raiz / "Profiles" / "xyz.Default (release)" / "cookies.sqlite"
        viejo.write_text("x")
        nuevo.write_text("x")
        os.utime(viejo, (1000, 1000))
        os.utime(nuevo, (2000, 2000))
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "zen", {"linux": [str(raiz)]})
        assert core.perfil_gecko("zen") == str(nuevo.parent)

    def test_sin_perfiles_devuelve_vacio(self, monkeypatch, tmp_path):
        raiz = tmp_path / "zen"
        raiz.mkdir()
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "zen", {"linux": [str(raiz)]})
        assert core.perfil_gecko("zen") == ""

    def test_ignora_perfil_sin_cookies(self, monkeypatch, tmp_path):
        raiz = tmp_path / "librewolf"
        (raiz / "Profiles" / "p1").mkdir(parents=True)
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "librewolf", {"linux": [str(raiz)]})
        assert core.perfil_gecko("librewolf") == ""


class TestConstruirOpcionesCookies:
    def test_sin_navegador_sin_cookies(self):
        assert core.construir_opciones_cookies("") == {}
        assert core.construir_opciones_cookies(None) == {}

    def test_chromium_por_nombre(self):
        assert core.construir_opciones_cookies("brave") == {
            "cookiesfrombrowser": ("brave", None, None, None)}
        assert core.construir_opciones_cookies("vivaldi") == {
            "cookiesfrombrowser": ("vivaldi", None, None, None)}

    def test_firefox_por_nombre(self):
        assert core.construir_opciones_cookies("firefox") == {
            "cookiesfrombrowser": ("firefox", None, None, None)}

    def test_fork_gecko_usa_firefox_con_perfil(self, monkeypatch, tmp_path):
        raiz = tmp_path / "zen"
        (raiz / "Profiles" / "p").mkdir(parents=True)
        db = raiz / "Profiles" / "p" / "cookies.sqlite"
        db.write_text("x")
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "zen", {"linux": [str(raiz)]})
        assert core.construir_opciones_cookies("zen") == {
            "cookiesfrombrowser": ("firefox", str(db.parent), None, None)}

    def test_fork_gecko_sin_perfil_no_pone_cookies(self, monkeypatch, tmp_path):
        raiz = tmp_path / "zen"
        raiz.mkdir()
        monkeypatch.setitem(core.NAVEGADORES_RUTAS, "zen", {"linux": [str(raiz)]})
        assert core.construir_opciones_cookies("zen") == {}


class TestElegirNavegadorSesion:
    def test_respeta_pref_guardada(self, monkeypatch):
        monkeypatch.setattr(core, "detectar_navegadores", lambda: ["brave", "firefox"])
        assert elegir_navegador_sesion("firefox") == "firefox"

    def test_pref_invalida_usa_el_primero(self, monkeypatch):
        monkeypatch.setattr(core, "detectar_navegadores", lambda: ["brave", "firefox"])
        assert elegir_navegador_sesion("edge") == "firefox"

    def test_sin_navegadores_devuelve_vacio(self, monkeypatch):
        monkeypatch.setattr(core, "detectar_navegadores", lambda: [])
        assert elegir_navegador_sesion("brave") == ""

    def test_orden_preferido_gecko_primero(self):
        assert ORDEN_NAVEGADORES[0] == "zen"
        assert ORDEN_NAVEGADORES.index("firefox") < ORDEN_NAVEGADORES.index("brave")


class TestNavegadoresParaReintento:
    def test_sin_pref_firefox_primero(self):
        assert navegadores_para_reintento("", ["brave", "firefox", "edge"]) == [
            "firefox", "brave", "edge"]

    def test_sin_pref_sin_firefox_conserva_orden(self):
        assert navegadores_para_reintento("", ["brave", "chrome", "edge"]) == [
            "brave", "chrome", "edge"]

    def test_pref_detectada_va_primero(self):
        assert navegadores_para_reintento("edge", ["brave", "firefox", "edge"]) == [
            "edge", "brave", "firefox"]

    def test_pref_ausente_cae_a_firefox_primero(self):
        assert navegadores_para_reintento("chrome", ["brave", "firefox"]) == [
            "firefox", "brave"]

    def test_sin_detectados_devuelve_vacio(self):
        assert navegadores_para_reintento("brave", []) == []

    def test_usa_deteccion_por_defecto(self, monkeypatch):
        monkeypatch.setattr(core, "detectar_navegadores", lambda: ["firefox", "brave"])
        assert navegadores_para_reintento() == ["firefox", "brave"]


class TestTiposCuenta:
    def test_tipos_cuenta(self):
        assert core.TIPOS_CUENTA == {"private", "members_only", "age_restricted", "sign_in"}

    def test_no_incluye_bot_ni_cookies(self):
        assert "bot" not in core.TIPOS_CUENTA
        assert "cookies" not in core.TIPOS_CUENTA

    def test_gecko_compatibles_abiertos(self):
        assert "zen" in core.NAVEGADORES_COMPATIBLES_ABIERTOS
        assert "firefox" in core.NAVEGADORES_COMPATIBLES_ABIERTOS
        assert "brave" not in core.NAVEGADORES_COMPATIBLES_ABIERTOS


class TestFallbackBotSinCookies:
    def _opciones_capturadas(self, monkeypatch, navegador):
        import core as core_mod
        capturadas = []

        class FakeYDL:
            def __init__(self, opciones):
                capturadas.append(opciones)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def download(self, urls):
                raise core_mod.yt_dlp.utils.DownloadError("still bot")

        monkeypatch.setattr(core_mod.yt_dlp, "YoutubeDL", FakeYDL)
        monkeypatch.setattr(core_mod, "navegadores_para_reintento", lambda *a, **k: [])
        clasificado = {"mensaje": "bot", "sugerencia": "s", "detalle": "", "tipo": "bot"}
        core_mod._descargar_fallback_bot(
            "https://youtu.be/x", "/tmp/out", "audio", "320", False, False,
            None, None, navegador, None, None, None, clasificado,
        )
        return capturadas

    def test_sin_navegador_no_usa_cookies(self, monkeypatch):
        capturadas = self._opciones_capturadas(monkeypatch, None)
        assert capturadas
        assert all("cookiesfrombrowser" not in o for o in capturadas)

    def test_con_navegador_usa_cookies(self, monkeypatch):
        capturadas = self._opciones_capturadas(monkeypatch, "firefox")
        assert capturadas
        assert all(o.get("cookiesfrombrowser") == ("firefox", None, None, None)
                   for o in capturadas)



class TestFallbackBot:
    def test_orden_clientes_fallback(self):
        assert CLIENTES_FALLBACK_BOT == ["tv", "web_embedded", "android_vr"]

    def test_verificar_prueba_navegadores_tras_bot(self, monkeypatch):
        import core as core_mod
        intentos = []

        def fake_verificar(url, navegador, cancel_flag, impersonate=None, player_client=None):
            intentos.append(navegador)
            if navegador == "zen":
                return {"title": "ok"}, None
            raise core_mod.yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot")

        monkeypatch.setattr(core_mod, "_intentar_verificar", fake_verificar)
        monkeypatch.setattr(core_mod, "navegadores_para_reintento", lambda *a, **k: ["zen", "firefox"])
        r = verificar_url("https://youtu.be/x", navegador="brave")
        assert r["info"] == {"title": "ok"}
        assert "zen" in intentos

    def test_verificar_no_prueba_navegadores_si_ok(self, monkeypatch):
        import core as core_mod
        intentos = []

        def fake_verificar(url, navegador, cancel_flag, impersonate=None, player_client=None):
            intentos.append(navegador)
            return {"title": "ok"}, None

        monkeypatch.setattr(core_mod, "_intentar_verificar", fake_verificar)
        monkeypatch.setattr(core_mod, "navegadores_para_reintento", lambda *a, **k: ["zen"])
        r = verificar_url("https://youtu.be/x", navegador="brave")
        assert r["info"] == {"title": "ok"}
        assert intentos == ["brave"]

    def test_reintenta_con_clientes_y_impersonate(self, monkeypatch):
        import core as core_mod
        intentos = []

        def fake_verificar(url, navegador, cancel_flag, impersonate=None, player_client=None):
            intentos.append((impersonate, player_client))
            if player_client == "web_embedded":
                return {"title": "ok"}, None
            raise core_mod.yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot")

        monkeypatch.setattr(core_mod, "_intentar_verificar", fake_verificar)
        r = verificar_url("https://youtu.be/x")
        assert r["info"] == {"title": "ok"}
        assert ("chrome", "tv") in intentos
        assert ("chrome", "web_embedded") in intentos

    def test_cancel_flag_detiene_fallback(self, monkeypatch):
        import core as core_mod
        flag = threading.Event()
        intentos = []

        def fake_verificar(url, navegador, cancel_flag, impersonate=None, player_client=None):
            intentos.append(player_client)
            flag.set()
            raise core_mod.yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot")

        monkeypatch.setattr(core_mod, "_intentar_verificar", fake_verificar)
        r = verificar_url("https://youtu.be/x", cancel_flag=flag)
        assert intentos == [None]
        assert r["restriccion"]["tipo"] == "cancelada"

    def test_sugerencia_bot_menciona_sesion(self):
        sugerencia = ClasificadorErrores.SUGERENCIAS.get("bot", "")
        assert "sesion" in sugerencia.lower() or "sesión" in sugerencia.lower()


class TestCancelacionPostproceso:
    def test_postprocessor_hook_aborta_cuando_flag_activo(self):
        flag = threading.Event()
        flag.set()
        llamadas = []
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/o", "audio", "128", False, False,
            cancel_flag=flag, postprocessor_callback=lambda e, n: llamadas.append((e, n)),
        )
        hook = opts["postprocessor_hooks"][0]
        with pytest.raises(DescargaCancelada):
            hook({"status": "started", "postprocessor": "ExtractAudio"})
        assert llamadas == []

    def test_postprocessor_hook_continua_cuando_flag_inactivo(self):
        flag = threading.Event()
        llamadas = []
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/o", "audio", "128", False, False,
            cancel_flag=flag, postprocessor_callback=lambda e, n: llamadas.append((e, n)),
        )
        hook = opts["postprocessor_hooks"][0]
        hook({"status": "finished", "postprocessor": "ExtractAudio"})
        assert ("finished", "ExtractAudio") in llamadas


class TestPlataformasConfig:
    def test_youtube_soporta_subtitulos(self):
        assert PLATAFORMAS_CONFIG["YouTube"]["soporta_subtitulos"] is True

    def test_todas_plataformas_presentes(self):
        for p in ["YouTube", "Instagram", "Facebook", "TikTok", "Twitch", "Vimeo", "Twitter/X", "Reddit"]:
            assert p in PLATAFORMAS_CONFIG


class TestCalidadNoYoutube:
    def test_audio_bitrate_honrado(self):
        for bitrate in ("128", "192", "256", "320"):
            opts = _construir_opciones_descarga(
                "https://tiktok.com/@u/video/1", "/tmp/o", "audio", bitrate, False, False
            )
            pp = opts["postprocessors"][0]
            assert pp["preferredquality"] == bitrate

    @pytest.mark.parametrize("res", ["360p", "480p", "720p", "1080p", "1440p", "2160p"])
    def test_video_resolucion_generica(self, res):
        opts = _construir_opciones_descarga(
            "https://instagram.com/p/x", "/tmp/o", "video", res, False, False
        )
        limite = res.replace("p", "")
        assert f"height<={limite}" in opts["format"]
        assert opts["merge_output_format"] == "mp4"

    def test_video_resolucion_default_720p(self):
        opts = _construir_opciones_descarga(
            "https://instagram.com/p/x", "/tmp/o", "video", "9999p", False, False
        )
        assert "height<=720" in opts["format"]


class TestResolucionesYoutube4K:
    def test_map_tiene_4k_y_2k(self):
        assert "1440p" in RESOLUCIONES_YOUTUBE
        assert "2160p" in RESOLUCIONES_YOUTUBE

    def test_4k_sin_filtro_ext_mp4(self):
        fmt = RESOLUCIONES_YOUTUBE["2160p"]
        assert "height<=2160" in fmt
        assert "ext=mp4" not in fmt

    def test_2k_sin_filtro_ext_mp4(self):
        fmt = RESOLUCIONES_YOUTUBE["1440p"]
        assert "ext=mp4" not in fmt

    def test_fhd_conserva_mp4(self):
        assert "ext=mp4" in RESOLUCIONES_YOUTUBE["1080p"]

    def test_4k_aplicado_en_descarga(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/o", "video", "2160p", False, False
        )
        assert "height<=2160" in opts["format"]
        assert "ext=mp4" not in opts["format"]


class TestCompatibilidadCodecVlc:
    """El video debe salir en H.264 (avc1): VLC no puede abrir AV1/VP9 en mp4."""

    @pytest.mark.parametrize("res", ["360p", "480p", "720p", "1080p"])
    def test_youtube_prefiere_h264(self, res):
        fmt = RESOLUCIONES_YOUTUBE[res]
        assert "[vcodec^=avc1]" in fmt
        assert "[ext=mp4]" in fmt

    @pytest.mark.parametrize("res", ["360p", "480p", "720p", "1080p"])
    def test_youtube_conserva_respaldo(self, res):
        limite = res.replace("p", "")
        fmt = RESOLUCIONES_YOUTUBE[res]
        assert (
            f"bestvideo[height<={limite}][ext=mp4]+bestaudio[ext=m4a]/mp4" in fmt
        )

    @pytest.mark.parametrize("res", ["360p", "480p", "720p", "1080p"])
    def test_generica_prefiere_h264(self, res):
        assert "[vcodec^=avc1]" in RESOLUCIONES_GENERICAS[res]

    def test_descarga_1080p_pide_h264(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/o", "video", "1080p", False, False
        )
        assert "[vcodec^=avc1]" in opts["format"]


class TestPostprocessorCallback:
    def test_opciones_incluyen_postprocessor_hooks(self):
        llamadas = []
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/o", "audio", "128", False, False,
            postprocessor_callback=lambda e, n: llamadas.append((e, n)),
        )
        hook = opts["postprocessor_hooks"][0]
        hook({"status": "started", "postprocessor": "ExtractAudio"})
        hook({"status": "finished", "postprocessor": "ExtractAudio"})
        assert ("started", "ExtractAudio") in llamadas

    def test_sin_callback_no_hooks(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/o", "audio", "128", False, False
        )
        assert "postprocessor_hooks" not in opts


class TestClasificadorTikTok:
    @pytest.mark.parametrize("mensaje", [
        "ERROR: [tiktok] 123: Unexpected response from webpage request; please report",
        "ERROR: [tiktok] 123: Unable to extract universal data for rehydration",
        "Impersonating chrome133a is not supported",
    ])
    def test_errores_tiktok_a_extractor(self, mensaje):
        import yt_dlp
        res = ClasificadorErrores.clasificar(yt_dlp.utils.DownloadError(mensaje), "TikTok")
        assert res["tipo"] == "extractor"
        assert "TikTok" in res["mensaje"]

    def test_sugerencia_tiktok_incluye_curl_cffi(self):
        import yt_dlp
        res = ClasificadorErrores.clasificar(
            yt_dlp.utils.DownloadError("Unexpected response from webpage request"), "TikTok")
        assert "curl-cffi" in res["sugerencia"]
        assert "Usar sesion" in res["sugerencia"]


class TestVerificarUrlCancel:
    def test_url_invalida_temprana(self):
        r = verificar_url("https://example.com", cancel_flag=None)
        assert r["reconocida"] is False

    def test_acepta_cancel_flag_sin_romper(self):
        r = verificar_url("", navegador=None, cancel_flag=threading.Event())
        assert r["reconocida"] is False

    def test_cancel_flag_convierte_a_cancelada(self, monkeypatch):
        import core as core_mod
        from core import DescargaCancelada as DC

        def fake_opciones(nav=None, cancel_flag=None, **kwargs):
            return {}

        class FakeYDL:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return None
            def extract_info(self, url, download=False):
                raise DC()

        monkeypatch.setattr(core_mod, "_opciones_base", fake_opciones)
        monkeypatch.setattr(core_mod.yt_dlp, "YoutubeDL", FakeYDL)
        flag = threading.Event()
        r = verificar_url("https://youtu.be/x", navegador=None, cancel_flag=flag)
        assert r["restriccion"]["tipo"] == "cancelada"


class TestPreferenciasRoundtrip:
    def test_roundtrip_vacio(self, monkeypatch, tmp_path):
        import core as core_mod
        cfg = tmp_path / "cfg"
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg / "config.json"))
        prefs = {"modo": "audio", "calidad": "320", "max_paralelas": 1}
        guardar_preferencias(prefs)
        loaded = cargar_preferencias()
        assert loaded["modo"] == "audio"
        assert loaded["calidad"] == "320"

    def test_defaults_cuando_no_hay_archivo(self, monkeypatch, tmp_path):
        import core as core_mod
        cfg = tmp_path / "cfg"
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg / "config.json"))
        with pytest.raises(FileNotFoundError):
            open(cfg / "config.json")
        loaded = cargar_preferencias()
        assert loaded["modo"] == "audio"
        assert loaded["carpeta"] != ""

    def test_json_corrupto_no_rompe(self, monkeypatch, tmp_path):
        import core as core_mod
        cfg = tmp_path / "cfg"
        cfg.mkdir()
        cfg_file = cfg / "config.json"
        cfg_file.write_text("{ no es json")
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg_file))
        loaded = cargar_preferencias()
        assert loaded["modo"] == "audio"


class TestExtraerUrlCompleta:
    @pytest.mark.parametrize("texto,esperado", [
        ("https://youtu.be/dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=abc&t=30&list=x",
         "https://www.youtube.com/watch?v=abc&t=30&list=x"),
        ("Mira: https://www.instagram.com/reel/CxQ8A0gNfKV/ copialo",
         "https://www.instagram.com/reel/CxQ8A0gNfKV/"),
        ("https://www.tiktok.com/@u/video/123",
         "https://www.tiktok.com/@u/video/123"),
        ("https://youtu.be/abc.", "https://youtu.be/abc"),
        ("(https://youtu.be/dQw4)", "https://youtu.be/dQw4"),
        ("[https://youtu.be/dQw4]", "https://youtu.be/dQw4"),
        ("{https://youtu.be/dQw4}", "https://youtu.be/dQw4"),
        ("«https://vimeo.com/123»", "https://vimeo.com/123"),
        ("Mira: https://youtu.be/dQw4…", "https://youtu.be/dQw4"),
        ("www.x.com/user/status/123", "www.x.com/user/status/123"),
    ])
    def test_extrae_url_completa(self, texto, esperado):
        assert extraer_url_completa(texto) == esperado

    @pytest.mark.parametrize("texto", [
        "", None, "solo texto sin url",
        "https://ejemplo.com/video",
    ])
    def test_sin_url(self, texto):
        assert extraer_url_completa(texto) is None


class TestEnmascararUrl:
    @pytest.mark.parametrize("url,esperado", [
        ("https://www.youtube.com/watch?v=abc123&t=30", "youtube.com/···"),
        ("https://youtu.be/dQw4w9WgXcQ", "youtu.be/···"),
        ("youtube.com/watch?v=x", "youtube.com/···"),
        ("https://www.instagram.com/reel/CxQ8/", "instagram.com/···"),
        ("https://vimeo.com/123456", "vimeo.com/···"),
        ("https://twitter.com/user/status/1", "twitter.com/···"),
        ("https://www.reddit.com/r/x/comments/1/", "reddit.com/···"),
        ("https://vimeo.com/", "vimeo.com"),
        ("https://youtu.be", "youtu.be"),
        ("", ""),
        (None, ""),
    ])
    def test_enmascara(self, url, esperado):
        assert enmascarar_url(url) == esperado

    @pytest.mark.parametrize("url", [
        "https://youtube.com/watch?v=abc",
        "youtu.be/test?id=1&token=SECRET",
        "https://instagram.com/stories/user/123",
    ])
    def test_nunca_expone_ruta_o_query(self, url):
        mascara = enmascarar_url(url)
        assert "watch" not in mascara
        assert "token" not in mascara
        assert "=" not in mascara
        assert "/" not in mascara.replace("/···", "", 1)


class TestSanitizarDetalle:
    def test_enmascara_urls_dentro_de_texto(self):
        detalle = "ERROR: [youtube] https://youtube.com/watch?v=abc&token=X no se pudo"
        result = sanitizar_detalle(detalle)
        assert "youtube.com/···" in result
        assert "watch" not in result
        assert "token=X" not in result

    def test_enmascara_urls_sin_esquema(self):
        detalle = "Error en youtube.com/watch?v=abc y en tiktok.com/@u/video/1"
        result = sanitizar_detalle(detalle)
        assert "youtube.com/···" in result
        assert "tiktok.com/···" in result
        assert "watch" not in result

    @pytest.mark.parametrize("texto", [
        "Sign in to confirm your age here",
        "This video is private",
        "Some odd error here",
    ])
    def test_conserva_texto_clave(self, texto):
        assert sanitizar_detalle(texto) == texto

    def test_limpia_parametros_tipo_token(self):
        detalle = "Failed with access_token=abc123&sig=deadbeef final"
        result = sanitizar_detalle(detalle)
        assert "abc123" not in result
        assert "sig=deadbeef" not in result
        assert "Failed with" in result

    def test_trunca_a_404(self):
        largo = "x" * 1000
        result = sanitizar_detalle("some error " + largo)
        assert len(result) <= 404

    def test_vacio_y_none(self):
        assert sanitizar_detalle("") == ""
        assert sanitizar_detalle(None) == ""


class TestConstantesCalidades:
    def test_audio_coincide_con_config_youtube(self):
        assert CALIDADES_AUDIO == ["128", "192", "256", "320"]

    def test_video_deriva_de_resoluciones(self):
        assert CALIDADES_VIDEO == list(RESOLUCIONES_YOUTUBE.keys())
        assert "2160p" in CALIDADES_VIDEO


class TestPrefsLimpiaTema:
    def test_guardar_elimina_clave_legacy_tema(self, monkeypatch, tmp_path):
        import core as core_mod
        import json
        cfg = tmp_path / "cfg"
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg / "config.json"))
        prefs = {"modo": "audio", "tema": "dark", "ocultar_urls": True}
        guardar_preferencias(prefs)
        guardado = json.loads((cfg / "config.json").read_text())
        assert "tema" not in guardado
        assert guardado["ocultar_urls"] is True

    def test_cargar_ignora_tema(self, monkeypatch, tmp_path):
        import core as core_mod
        import json
        cfg = tmp_path / "cfg"
        cfg.mkdir()
        cfg_file = cfg / "config.json"
        cfg_file.write_text(json.dumps({"modo": "video", "tema": "dark"}))
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg_file))
        loaded = cargar_preferencias()
        assert "tema" not in loaded
        assert loaded["modo"] == "video"


class TestSanearClipboard:
    def test_quita_controles(self):
        assert sanear_texto_clipboard(
            "https://youtu.be/abc\x00\x0b\x1fdef") == "https://youtu.be/abc def"

    def test_normaliza_whitespace(self):
        assert sanear_texto_clipboard(
            "  \n\thttps://youtu.be/abc \n\n  basura ") == "https://youtu.be/abc basura"

    def test_quita_bom_y_anchos_cero(self):
        assert sanear_texto_clipboard(
            "\ufeffhttps://youtu.be/abc\u200b\u200c") == "https://youtu.be/abc"

    def test_vacio_y_none(self):
        assert sanear_texto_clipboard("") == ""
        assert sanear_texto_clipboard(None) == ""
        assert sanear_texto_clipboard("   \n ") == ""


class TestPreferenciasOcultarUrls:
    def test_default_ocultar_urls_true(self, monkeypatch, tmp_path):
        import core as core_mod
        cfg = tmp_path / "cfg"
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg / "config.json"))
        loaded = cargar_preferencias()
        assert loaded["ocultar_urls"] is True

    def test_roundtrip_conserva_ocultar_urls(self, monkeypatch, tmp_path):
        import core as core_mod
        cfg = tmp_path / "cfg"
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg / "config.json"))
        prefs = {"modo": "video", "ocultar_urls": False}
        guardar_preferencias(prefs)
        loaded = cargar_preferencias()
        assert loaded["ocultar_urls"] is False


class TestPreferenciasActualizacion:
    def test_default_preguntar(self, monkeypatch, tmp_path):
        import core as core_mod
        cfg = tmp_path / "cfg"
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg / "config.json"))
        loaded = cargar_preferencias()
        assert loaded["actualizar_automaticamente"] == "preguntar"
        assert loaded["ultima_revision_update"] == 0
        assert loaded["version_avisada"] == ""

    def test_roundtrip_conserva_valor(self, monkeypatch, tmp_path):
        import core as core_mod
        cfg = tmp_path / "cfg"
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg / "config.json"))
        guardar_preferencias({"actualizar_automaticamente": "auto", "ultima_revision_update": 12345})
        loaded = cargar_preferencias()
        assert loaded["actualizar_automaticamente"] == "auto"
        assert loaded["ultima_revision_update"] == 12345

    def test_valor_invalido_se_normaliza(self, monkeypatch, tmp_path):
        import core as core_mod
        import json as json_mod
        cfg = tmp_path / "cfg"
        cfg.mkdir()
        cfg_file = cfg / "config.json"
        cfg_file.write_text(json_mod.dumps({"actualizar_automaticamente": "siempre"}))
        monkeypatch.setattr(core_mod, "CONFIG_DIR", str(cfg))
        monkeypatch.setattr(core_mod, "CONFIG_FILE", str(cfg_file))
        assert cargar_preferencias()["actualizar_automaticamente"] == "preguntar"


class TestOuttmplSubtitulos:
    def test_sin_subtitulos_sigue_siendo_cadena(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "video", "720p", False, False,
        )
        assert opts["outtmpl"] == os.path.join("/tmp/out", "%(title)s [%(id)s].%(ext)s")

    def test_con_subtitulos_mantiene_cadena_plana(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "video", "720p", True, False,
        )
        assert opts["writesubtitles"] is True
        assert opts["subtitleslangs"] == ["es", "en", "pt"]
        assert isinstance(opts["outtmpl"], str)
        assert opts["outtmpl"] == os.path.join("/tmp/out", "%(title)s [%(id)s].%(ext)s")

    def test_no_youtube_con_subtitulos_conserva_cadena(self):
        opts = _construir_opciones_descarga(
            "https://instagram.com/p/x", "/tmp/out", "video", "720p", True, False,
        )
        assert isinstance(opts["outtmpl"], str)
        assert opts.get("writesubtitles") is None


class TestActualizacionAssets:
    ASSETS = [
        {"name": "yt-dowloader-linux.deb", "url": "https://x/deb", "size": 10},
        {"name": "yt-dowloader-linux.tar.gz", "url": "https://x/tar", "size": 20},
        {"name": "YT-DownLoader-Jaeger-Setup.exe", "url": "https://x/exe", "size": 30},
        {"name": "yt-dowloader-macos.dmg", "url": "https://x/dmg", "size": 40},
    ]

    @pytest.mark.parametrize("so,esperado", [
        ("windows", "YT-DownLoader-Jaeger-Setup.exe"),
        ("macos", "yt-dowloader-macos.dmg"),
        ("linux", "yt-dowloader-linux.deb"),
    ])
    def test_selecciona_asset_por_so(self, so, esperado):
        assert core.seleccionar_asset_update(self.ASSETS, so)["name"] == esperado

    def test_so_desconocido_o_sin_asset(self):
        assert core.seleccionar_asset_update(self.ASSETS, "desconocido") is None
        assert core.seleccionar_asset_update([{"name": "otro.zip", "url": "u"}], "linux") is None
        assert core.seleccionar_asset_update([], "windows") is None

    def test_asset_sin_url_no_se_elige(self):
        assets = [{"name": "yt-dowloader-linux.deb", "url": ""}]
        assert core.seleccionar_asset_update(assets, "linux") is None

    def test_detectar_instalacion_linux(self, monkeypatch):
        monkeypatch.setattr(core.os.path, "realpath", lambda p: p)
        assert core.detectar_instalacion_linux("/opt/yt-dowloader/yt-dowloader") == "deb"
        assert core.detectar_instalacion_linux("/home/u/dist/yt-dowloader/yt-dowloader") == "portable"


class TestSha256Update:
    def test_parsear_sha256sums(self):
        texto = (
            "a" * 64 + "  yt-dowloader-linux.deb\n"
            + "b" * 64 + " *yt-dowloader-windows-portable.zip\n"
            "linea-invalida\n"
            "corta  archivo\n"
        )
        hashes = core.parsear_sha256sums(texto)
        assert hashes == {
            "yt-dowloader-linux.deb": "a" * 64,
            "yt-dowloader-windows-portable.zip": "b" * 64,
        }

    def test_parsear_sha256sums_vacio(self):
        assert core.parsear_sha256sums("") == {}
        assert core.parsear_sha256sums(None) == {}

    def test_verificar_sha256_ok_y_fallo(self, tmp_path):
        archivo = tmp_path / "paquete.deb"
        archivo.write_bytes(b"contenido de prueba")
        real = core.sha256_de_archivo(str(archivo))
        assert core.verificar_sha256(str(archivo), real) is True
        assert core.verificar_sha256(str(archivo), real.upper()) is True
        assert core.verificar_sha256(str(archivo), "0" * 64) is False

    def test_verificar_sha256_sin_esperado_o_sin_archivo(self, tmp_path):
        archivo = tmp_path / "x"
        archivo.write_bytes(b"x")
        assert core.verificar_sha256(str(archivo), "") is False
        assert core.verificar_sha256(str(tmp_path / "no-existe"), "a" * 64) is False


class TestComandoActualizacion:
    def test_windows_silencioso(self):
        cmd = core.comando_actualizacion("C:/tmp/setup.exe", "windows")
        assert cmd["args"] == ["C:/tmp/setup.exe", "/S"]
        assert cmd["requiere_privilegios"] is True

    def test_macos_abre_dmg(self):
        cmd = core.comando_actualizacion("/tmp/app.dmg", "macos")
        assert cmd["args"] == ["open", "/tmp/app.dmg"]
        assert cmd["requiere_privilegios"] is False

    def test_linux_usa_pkexec(self):
        cmd = core.comando_actualizacion("/tmp/pkg.deb", "linux")
        assert cmd["args"][0] == "pkexec"
        assert cmd["args"][-1] == "/tmp/pkg.deb"
        assert cmd["requiere_privilegios"] is True

    def test_so_desconocido(self):
        assert core.comando_actualizacion("/tmp/x", "desconocido") is None


class TestDebeRevisarUpdate:
    def test_desactivado_no_revisa(self):
        prefs = {"actualizar_automaticamente": "desactivado", "ultima_revision_update": 0}
        assert core.debe_revisar_update(prefs) is False

    def test_revisa_por_defecto(self):
        assert core.debe_revisar_update({}) is True

    def test_revisa_ignora_historial_de_horas(self):
        prefs = {"ultima_revision_update": 9_000_000}
        assert core.debe_revisar_update(prefs) is True

    def test_revisa_aunque_avisado(self):
        prefs = {"version_avisada": "3.6.2", "actualizar_automaticamente": "preguntar"}
        assert core.debe_revisar_update(prefs) is True

    def test_modo_auto_revisa(self):
        prefs = {"actualizar_automaticamente": "auto"}
        assert core.debe_revisar_update(prefs) is True


class TestDebeAvisar:
    def test_avisa_version_nueva(self):
        assert core.debe_avisar("3.6.2", {}) is True

    def test_no_avisa_si_ya_se_aviso_esa_version(self):
        prefs = {"version_avisada": "3.6.2"}
        assert core.debe_avisar("3.6.2", prefs) is False

    def test_avisa_si_cambia_la_version(self):
        prefs = {"version_avisada": "3.6.2"}
        assert core.debe_avisar("3.6.3", prefs) is True

    def test_sin_version_no_avisa(self):
        assert core.debe_avisar("", {}) is False


class TestDescargarAsset:
    def test_descarga_y_renombra(self, tmp_path, monkeypatch):
        class FakeResp:
            headers = {"Content-Length": "9"}

            def __init__(self):
                self._datos = [b"12345", b"6789", b""]

            def read(self, n):
                return self._datos.pop(0)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr(core.urllib.request, "urlopen", lambda *a, **k: FakeResp())
        progreso = []
        destino = str(tmp_path / "pkg.deb")
        ok, msg, ruta = core.descargar_asset(
            "https://x/pkg.deb", destino, progress_cb=lambda d, t: progreso.append((d, t))
        )
        assert ok is True
        assert ruta == destino
        assert (tmp_path / "pkg.deb").read_bytes() == b"123456789"
        assert not os.path.exists(destino + ".part")
        assert progreso[-1] == (9, 9)

    def test_cancelacion_borra_parcial(self, tmp_path, monkeypatch):
        flag = threading.Event()

        class FakeResp:
            headers = {"Content-Length": "10"}

            def read(self, n):
                flag.set()
                return b"12345"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr(core.urllib.request, "urlopen", lambda *a, **k: FakeResp())
        destino = str(tmp_path / "pkg.deb")
        ok, msg, ruta = core.descargar_asset("https://x/pkg.deb", destino, cancel_flag=flag)
        assert ok is False
        assert ruta is None
        assert "cancelada" in msg.lower()
        assert not os.path.exists(destino)
        assert not os.path.exists(destino + ".part")

    def test_error_de_red_borra_parcial(self, tmp_path, monkeypatch):
        def fake_urlopen(*a, **k):
            raise OSError("sin red")

        monkeypatch.setattr(core.urllib.request, "urlopen", fake_urlopen)
        destino = str(tmp_path / "pkg.deb")
        ok, msg, ruta = core.descargar_asset("https://x/pkg.deb", destino)
        assert ok is False
        assert ruta is None
        assert "no se pudo descargar" in msg.lower()
        assert not os.path.exists(destino + ".part")

