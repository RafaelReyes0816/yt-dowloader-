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
    normalizar_pistas_audio,
    nombre_pista_seguro,
    es_audio_original,
    descargar_musica,
)
from core import CALIDADES_AUDIO, CALIDADES_VIDEO


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

        def fake_opciones(nav=None, cancel_flag=None):
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


def _formato_audio(format_id, language=None, format_note=None, ext="m4a",
                   abr=129.5, pref=-1, acodec="mp4a.40.2", vcodec="none", **extra):
    formato = {
        "format_id": format_id,
        "language": language,
        "format_note": format_note,
        "ext": ext,
        "abr": abr,
        "tbr": abr,
        "acodec": acodec,
        "vcodec": vcodec,
        "audio_channels": 2,
        "language_preference": pref,
    }
    formato.update(extra)
    return formato


class TestNormalizarPistasAudio:
    def test_excluye_original_y_deduplica_por_idioma(self):
        info = {
            "language": "en-US",
            "formats": [
                _formato_audio("139-7", "en-US", "English (US) original (default), low", abr=48.8, pref=10),
                _formato_audio("140-7", "en-US", "English (US) original (default), medium", pref=10),
                _formato_audio("251-7", "en-US", "English (US) original (default), medium", ext="webm", abr=136.1, pref=10),
                _formato_audio("233-1", "es-US", "es-US - dubbed-auto", ext="mp4", abr=None),
                _formato_audio("140-1", "es-US", "Spanish (US), medium"),
                _formato_audio("251-2", "es-US", "Spanish (US), medium", ext="webm", abr=138.6),
                _formato_audio("251-4", "de-DE", "German (DE), medium", ext="webm", abr=140.8),
                _formato_audio("299", None, None, ext="mp4", abr=None,
                               acodec="none", vcodec="avc1"),
            ],
        }
        pistas = normalizar_pistas_audio(info)
        assert [p["format_id"] for p in pistas] == ["251-4", "140-1"]
        assert all(p["language"] != "en-US" for p in pistas)
        assert pistas[1]["label"] == "Spanish (US)"
        assert pistas[1]["ext"] == "m4a"
        assert pistas[1]["acodec"] == "mp4a.40.2"

    def test_video_de_un_solo_idioma_no_tiene_pistas(self):
        info = {
            "language": "en",
            "formats": [
                _formato_audio("139", "en", "English, low", abr=48.8),
                _formato_audio("140", "en", "English, medium"),
                _formato_audio("251", "en", "English, medium", ext="webm", abr=130.0),
                _formato_audio("251-drc", "en", "medium, DRC", ext="webm", abr=130.1),
            ],
        }
        assert normalizar_pistas_audio(info) == []

    def test_original_por_language_si_no_hay_marca_de_preferencia(self):
        info = {
            "language": "en",
            "formats": [
                _formato_audio("140", "en", "English, medium"),
                _formato_audio("140-1", "es", "Spanish, medium"),
            ],
        }
        pistas = normalizar_pistas_audio(info)
        assert [p["language"] for p in pistas] == ["es"]

    def test_original_acepta_variante_base_del_idioma(self):
        info = {
            "language": "en",
            "formats": [
                _formato_audio("140", "en-US", "English (US), medium"),
                _formato_audio("140-1", "es-US", "Spanish (US), medium"),
            ],
        }
        pistas = normalizar_pistas_audio(info)
        assert [p["language"] for p in pistas] == ["es-US"]

    def test_variantes_regionales_no_se_consideran_el_mismo_idioma(self):
        info = {
            "language": "en-US",
            "formats": [
                _formato_audio("140", "en-GB", "English (GB), medium"),
                _formato_audio("140-1", "en-US", "English (US) original (default), medium", pref=10),
            ],
        }
        pistas = normalizar_pistas_audio(info)
        assert [p["language"] for p in pistas] == ["en-GB"]

    def test_sin_marca_y_varios_idiomas_es_ambiguo(self):
        info = {
            "formats": [
                _formato_audio("140", "en", "English, medium"),
                _formato_audio("140-1", "es", "Spanish, medium"),
            ],
        }
        assert normalizar_pistas_audio(info) == []

    def test_tolera_info_incompleta(self):
        assert normalizar_pistas_audio({}) == []
        assert normalizar_pistas_audio({"formats": None}) == []
        assert normalizar_pistas_audio({"formats": [None, "x", 1]}) == []
        assert normalizar_pistas_audio(None) == []

    def test_etiiqueta_neutral_para_pistas_sin_idioma(self):
        info = {
            "language": "en",
            "formats": [
                _formato_audio("140", "en", "English, medium", pref=10),
                _formato_audio("140-x", None, "Comentario", abr=100.0),
                _formato_audio("140-y", None, None, abr=90.0),
            ],
        }
        pistas = normalizar_pistas_audio(info)
        assert [p["format_id"] for p in pistas] == ["140-y", "140-x"]
        assert [p["label"] for p in pistas] == ["140-y", "Comentario"]

    def test_prefiere_m4a_sobre_webm(self):
        info = {
            "language": "en",
            "formats": [
                _formato_audio("140", "en", "English, medium", pref=10),
                _formato_audio("140-1", "es", "Spanish, medium", abr=129.5),
                _formato_audio("251-1", "es", "Spanish, medium", ext="webm", abr=140.0),
            ],
        }
        pistas = normalizar_pistas_audio(info)
        assert pistas[0]["format_id"] == "140-1"
        assert pistas[0]["ext"] == "m4a"

    def test_sin_m4a_elige_el_mayor_bitrate(self):
        info = {
            "language": "en",
            "formats": [
                _formato_audio("140", "en", "English, medium", pref=10),
                _formato_audio("249-1", "es", "Spanish, low", ext="webm", abr=50.0),
                _formato_audio("251-1", "es", "Spanish, medium", ext="webm", abr=140.0),
            ],
        }
        pistas = normalizar_pistas_audio(info)
        assert pistas[0]["format_id"] == "251-1"

    def test_nombres_unicos_cuando_las_etiquetas_coinciden(self):
        info = {
            "language": "en",
            "formats": [
                _formato_audio("140", "en", "English, medium", pref=10),
                _formato_audio("140-1", "es-ES", "Spanish, medium"),
                _formato_audio("140-2", "es-MX", "Spanish, medium"),
            ],
        }
        pistas = normalizar_pistas_audio(info)
        assert [p["label"] for p in pistas] == ["Spanish", "Spanish"]
        nombres = [p["nombre"] for p in pistas]
        assert len(set(nombres)) == 2
        assert all("140-" in n for n in nombres)


class TestNombrePistaSeguro:
    def test_no_conserva_separadores_de_ruta(self):
        nombre = nombre_pista_seguro("../../etc/passwd")
        assert "/" not in nombre
        assert "\\" not in nombre

    def test_no_inyecta_campos_de_outtmpl(self):
        nombre = nombre_pista_seguro("%(title)s")
        assert "%" not in nombre

    def test_conserva_espacios_y_parentesis(self):
        assert nombre_pista_seguro("Spanish (US)") == "Spanish (US)"

    def test_vacio_o_solo_puntos_devuelve_neutral(self):
        assert nombre_pista_seguro("") == "pista"
        assert nombre_pista_seguro("..") == "pista"
        assert nombre_pista_seguro(None) == "pista"


class TestEsAudioOriginal:
    def test_marca_de_preferencia(self):
        assert es_audio_original(
            {"language": "en-US", "language_preference": 10}, {"language": "es"}) is True

    def test_language_superior_con_variante(self):
        assert es_audio_original(
            {"language": "en-US", "language_preference": -1}, {"language": "en"}) is True

    def test_doblaje_no_es_original(self):
        assert es_audio_original(
            {"language": "es-US", "language_preference": -1}, {"language": "en"}) is False

    def test_variantes_regionales_distintas(self):
        assert es_audio_original(
            {"language": "en-GB", "language_preference": -1}, {"language": "en-US"}) is False


class TestOpcionesPistaAudio:
    def test_usa_format_id_sin_postprocesadores(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "audio", "128", False, False,
            format_id="140-1", pista_label="Spanish (US)",
        )
        assert opts["format"] == "140-1"
        assert "postprocessors" not in opts
        assert "postprocessor_args" not in opts
        assert "merge_output_format" not in opts
        assert opts.get("writesubtitles") is None

    def test_outtmpl_en_subcarpeta_con_nombre_seguro(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "audio", "128", False, False,
            format_id="140-1", pista_label="Spanish (US)",
        )
        esperado = os.path.join(
            "/tmp/out", "%(title)s [%(id)s]", "audio adicional - Spanish (US).%(ext)s")
        assert opts["outtmpl"] == esperado
        assert "%(language)s" not in opts["outtmpl"]

    def test_etiqueta_peligrosa_se_sanea(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "audio", "128", False, False,
            format_id="140-1", pista_label="../%(title)s",
        )
        directorio = os.path.join("/tmp/out", "%(title)s [%(id)s]") + os.sep
        assert opts["outtmpl"].startswith(directorio)
        nombre_archivo = opts["outtmpl"][len(directorio):]
        assert "/" not in nombre_archivo
        assert "\\" not in nombre_archivo
        assert nombre_archivo.startswith("audio adicional - ")
        assert "%(title)s" not in nombre_archivo
        assert "%(id)s" not in nombre_archivo

    def test_format_id_tiene_prioridad_sobre_modo_video(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "video", "1080p", False, False,
            format_id="251-2", pista_label="Spanish",
        )
        assert opts["format"] == "251-2"
        assert "merge_output_format" not in opts

    def test_pista_siempre_es_noplaylist(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x&list=y", "/tmp/out", "audio", "128",
            False, True, format_id="140-1", pista_label="Spanish",
        )
        assert opts["noplaylist"] is True

    def test_pista_ignora_subtitulos(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "audio", "128", True, False,
            format_id="140-1", pista_label="Spanish",
        )
        assert opts.get("writesubtitles") is None
        assert isinstance(opts["outtmpl"], str)

    def test_tmpfile_callback_recibe_la_ruta_parcial(self):
        rutas = []
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "audio", "128", False, False,
            tmpfile_callback=rutas.append, format_id="140-1", pista_label="Spanish",
        )
        hook = opts["progress_hooks"][0]
        hook({
            "status": "downloading",
            "tmpfilename": "/tmp/out/T [x]/audio adicional - Spanish.m4a.part",
            "downloaded_bytes": 1,
            "total_bytes": 2,
        })
        assert rutas == [
            "/tmp/out/T [x]/audio adicional - Spanish.m4a.part"]


class TestOuttmplSubtitulos:
    def test_sin_subtitulos_sigue_siendo_cadena(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "video", "720p", False, False,
        )
        assert opts["outtmpl"] == os.path.join("/tmp/out", "%(title)s [%(id)s].%(ext)s")

    def test_con_subtitulos_usa_diccionario(self):
        opts = _construir_opciones_descarga(
            "https://youtube.com/watch?v=x", "/tmp/out", "video", "720p", True, False,
        )
        assert opts["writesubtitles"] is True
        assert isinstance(opts["outtmpl"], dict)
        assert opts["outtmpl"]["default"] == os.path.join(
            "/tmp/out", "%(title)s [%(id)s].%(ext)s")
        assert opts["outtmpl"]["subtitle"] == os.path.join(
            "/tmp/out", "%(title)s [%(id)s]", "%(title)s [%(id)s].%(ext)s")

    def test_no_youtube_con_subtitulos_conserva_cadena(self):
        opts = _construir_opciones_descarga(
            "https://instagram.com/p/x", "/tmp/out", "video", "720p", True, False,
        )
        assert isinstance(opts["outtmpl"], str)
        assert opts.get("writesubtitles") is None


class TestDescargarPistaAudio:
    def test_descargar_musica_reenvia_format_id_y_etiqueta(self, monkeypatch, tmp_path):
        capturado = {}

        def fake_construir(url, carpeta, modo, calidad, subtitulos, playlist,
                           progreso_callback=None, cancel_flag=None,
                           postprocessor_callback=None, format_id=None,
                           pista_label=None, tmpfile_callback=None):
            capturado["format_id"] = format_id
            capturado["pista_label"] = pista_label
            capturado["postprocessor_callback"] = postprocessor_callback
            capturado["tmpfile_callback"] = tmpfile_callback
            return {"outtmpl": "x"}

        class FakeYDL:
            def __init__(self, opciones):
                self.opciones = opciones

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def download(self, urls):
                capturado["urls"] = urls

        monkeypatch.setattr(core, "_construir_opciones_descarga", fake_construir)
        monkeypatch.setattr(core.yt_dlp, "YoutubeDL", FakeYDL)

        ok, mensaje, tipo = descargar_musica(
            "https://youtube.com/watch?v=x", str(tmp_path), "audio", "128",
            format_id="140-1", pista_label="Spanish (US)",
        )
        assert ok is True
        assert capturado["format_id"] == "140-1"
        assert capturado["pista_label"] == "Spanish (US)"
        assert capturado["postprocessor_callback"] is None


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
        assert core.debe_revisar_update(prefs, ahora=10_000_000) is False

    def test_revisa_si_nunca_se_reviso(self):
        assert core.debe_revisar_update({}, ahora=10_000_000) is True

    def test_no_revisa_dentro_del_intervalo(self):
        prefs = {"ultima_revision_update": 9_000_000}
        assert core.debe_revisar_update(prefs, ahora=9_000_000 + 3600) is False

    def test_revisa_pasado_el_intervalo(self):
        prefs = {"ultima_revision_update": 9_000_000}
        assert core.debe_revisar_update(prefs, ahora=9_000_000 + 25 * 3600) is True

    def test_ultima_revision_invalida(self):
        prefs = {"ultima_revision_update": "no-es-numero"}
        assert core.debe_revisar_update(prefs, ahora=10_000_000) is True


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

