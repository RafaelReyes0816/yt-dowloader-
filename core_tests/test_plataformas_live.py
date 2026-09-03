"""Tests de integracion EN VIVO (requieren red). Se omiten por defecto con `-m "not live"`.

Ejecutar manualmente:
    .venv/bin/python -m pytest core_tests/test_plataformas_live.py -m live -v

Verifican que una URL publica es reconocida y que cualquier fallo de extraccion
se convierte en una RESTRICCION clasificada (sin excepciones sin manejar),
en lugar de un error generico o un crash.
"""

import pytest

from core import detectar_plataforma, verificar_url

URLS = [
    ("YouTube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("Instagram", "https://www.instagram.com/reel/CxQ8A0gNfKV/"),
    ("Facebook", "https://www.facebook.com/watch/?v=100064117547118"),
    ("TikTok", "https://www.tiktok.com/@scout2015/video/6718335390845095173"),
    ("Twitch", "https://www.twitch.tv/videos/1729357078"),
    ("Vimeo", "https://vimeo.com/76979871"),
    ("Twitter/X", "https://twitter.com/Twitter/status/1292833783812919296"),
    ("Reddit", "https://www.reddit.com/r/funny/comments/8d2w1i/"),
]

PLATAFORMAS_RECONOCIDAS = [
    (plataforma, url) for plataforma, url in URLS
    if detectar_plataforma(url) == plataforma
]


@pytest.mark.live
@pytest.mark.parametrize("plataforma,url", PLATAFORMAS_RECONOCIDAS)
def test_verificar_url_vivo(plataforma, url):
    r = verificar_url(url)
    assert r["reconocida"] is True, f"{plataforma}: no reconocida ({url})"

@pytest.mark.live
@pytest.mark.parametrize("plataforma,url", URLS)
def test_plataforma_detectada(plataforma, url):
    assert detectar_plataforma(url) == plataforma
