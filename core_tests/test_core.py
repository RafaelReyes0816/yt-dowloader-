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
