import os
import threading

import pytest

from core import (
    PLATFORM_REGEX,
    detectar_plataforma,
    es_youtube,
    ClasificadorErrores,
    comparar_versiones,
    _construir_opciones_descarga,
    DescargaCancelada,
    PLATAFORMAS_CONFIG,
    RESOLUCIONES_YOUTUBE,
    RESOLUCIONES_GENERICAS,
    verificar_url,
    cargar_preferencias,
    guardar_preferencias,
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
