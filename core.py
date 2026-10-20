import os
import re
import json
import sys
import shutil
import hashlib
import platform
import urllib.request
from collections import Counter

import yt_dlp

GITHUB_REPO = "RafaelReyes0816/yt-dowloader-"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".yt-downloader")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
UPDATE_DIR = os.path.join(CONFIG_DIR, "updates")
PLATFORM_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:'
    r'youtube\.com|youtu\.be|'
    r'instagram\.com|instagr\.am|'
    r'facebook\.com|fb\.watch|'
    r'tiktok\.com|vm\.tiktok\.com|'
    r'twitch\.tv|'
    r'vimeo\.com|'
    r'twitter\.com|x\.com|'
    r'reddit\.com'
    r')'
)

_URL_COMPLETA_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:'
    r'youtube\.com|youtu\.be|'
    r'instagram\.com|instagr\.am|'
    r'facebook\.com|fb\.watch|'
    r'tiktok\.com|vm\.tiktok\.com|'
    r'twitch\.tv|'
    r'vimeo\.com|'
    r'twitter\.com|x\.com|'
    r'reddit\.com'
    r')[^\s<>"\']*'
)

_TRAILING_URL_NO_VALIDO = ".,;:!?)]}\u00ab\u00bb\u201d\u201c\u2026"

_URL_GENERICA_REGEX = re.compile(
    r"(?:https?://[^\s<>\"']+|"
    r"(?:www\.)?(?:youtube\.com|youtu\.be|instagram\.com|instagr\.am|facebook\.com|fb\.watch|"
    r"tiktok\.com|vm\.tiktok\.com|twitch\.tv|vimeo\.com|twitter\.com|x\.com|reddit\.com)"
    r"[^\s<>\"']*)"
)
_PARAMETRO_SENSIBLE_REGEX = re.compile(
    r"((?:access_?token|token|code|key|signature|sig|sessionid|api[_-]?key)=)[^\s&\"']+",
    re.IGNORECASE,
)


_CONTROL_REGEX = re.compile(r"[\x00-\x1f\x7f\u200b-\u200f\u2060\ufeff]+")


def sanear_texto_clipboard(texto):
    """Limpia caracteres de control y normaliza espacios antes de extraer una URL."""
    if not texto:
        return ""
    limpio = _CONTROL_REGEX.sub(" ", str(texto))
    return re.sub(r"\s+", " ", limpio).strip()


def extraer_url_completa(texto):
    """Extrae una URL completa desde un texto/portapapeles, o None si no hay."""
    if not texto:
        return None
    m = _URL_COMPLETA_REGEX.search(texto)
    if not m:
        return None
    url = m.group(0)
    return url.rstrip(_TRAILING_URL_NO_VALIDO) or None


def enmascarar_url(url):
    """Devuelve una version segura de la URL para mostrar en la UI (solo host)."""
    if not url:
        return ""
    sin_esquema = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url.strip())
    if "@" in sin_esquema.split("/", 1)[0]:
        sin_esquema = sin_esquema.split("@", 1)[-1]
    partes = re.split(r"[/?#]", sin_esquema, maxsplit=1)
    host = partes[0]
    if host.startswith("www."):
        host = host[4:]
    if len(partes) == 2 and partes[1].strip("?"):
        return host + "/\u00b7\u00b7\u00b7"
    return host


def enmascarar_texto(texto):
    """Enmascara cualquier URL y elimina parametros sensibles dentro de un texto."""
    if not texto:
        return ""
    limpio = _URL_GENERICA_REGEX.sub(
        lambda m: enmascarar_url(m.group(0)), str(texto)
    )
    limpio = _PARAMETRO_SENSIBLE_REGEX.sub(
        lambda m: m.group(1) + "\u2026", limpio
    )
    return limpio.strip()


def sanitizar_detalle(texto):
    """Elimina informacion sensible (tokens, query strings) de un mensaje tecnico."""
    limpio = enmascarar_texto(texto)
    if len(limpio) > 400:
        limpio = limpio[:400] + "..."
    return limpio

TIPOS_BLOQUEANTES = {
    "private", "members_only", "age_restricted", "sign_in", "geo",
    "unavailable", "not_found", "cookies", "bot",
}

TIMEOUT_RED = 20

TIPOS_REINTENTO_SESION = {"private", "members_only", "age_restricted", "sign_in", "cookies", "bot"}

ORDEN_NAVEGADORES = ["brave", "firefox", "chrome", "edge"]

PERFIL_CHROMIUM = "Local State"
PERFIL_FIREFOX = "profiles.ini"

NAVEGADORES_RUTAS = {
    "chrome": {
        "win32": [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")],
        "darwin": [os.path.expanduser("~/Library/Application Support/Google/Chrome")],
        "linux": [os.path.expanduser("~/.config/google-chrome")],
    },
    "edge": {
        "win32": [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data")],
        "darwin": [os.path.expanduser("~/Library/Application Support/Microsoft Edge")],
        "linux": [os.path.expanduser("~/.config/microsoft-edge")],
    },
    "firefox": {
        "win32": [os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox")],
        "darwin": [os.path.expanduser("~/Library/Application Support/Firefox")],
        "linux": [os.path.expanduser("~/.mozilla/firefox")],
    },
    "brave": {
        "win32": [os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data")],
        "darwin": [os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser")],
        "linux": [os.path.expanduser("~/.config/BraveSoftware/Brave-Browser")],
    },
}

NAVEGADORES_ARCHIVO_PERFIL = {
    "chrome": PERFIL_CHROMIUM,
    "edge": PERFIL_CHROMIUM,
    "brave": PERFIL_CHROMIUM,
    "firefox": PERFIL_FIREFOX,
}

PLATAFORMA_DOMINIOS = {
    "youtube.com": "YouTube", "youtu.be": "YouTube",
    "instagram.com": "Instagram", "instagr.am": "Instagram",
    "facebook.com": "Facebook", "fb.watch": "Facebook",
    "tiktok.com": "TikTok", "vm.tiktok.com": "TikTok",
    "twitch.tv": "Twitch",
    "vimeo.com": "Vimeo",
    "twitter.com": "Twitter/X", "x.com": "Twitter/X",
    "reddit.com": "Reddit",
}

RESOLUCIONES_YOUTUBE = {
    "360p": "bestvideo[height<=360][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/mp4",
    "480p": "bestvideo[height<=480][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/mp4",
    "720p": "bestvideo[height<=720][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/mp4",
    "1080p": "bestvideo[height<=1080][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/mp4",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
}

RESOLUCIONES_GENERICAS = {
    "360p": "bestvideo[height<=360][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "480p": "bestvideo[height<=480][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "720p": "bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "1080p": "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
}

CALIDADES_AUDIO = ["128", "192", "256", "320"]
CALIDADES_VIDEO = list(RESOLUCIONES_YOUTUBE.keys())

PLATAFORMAS_CONFIG = {
    "YouTube": {
        "soporta_subtitulos": True,
        "soporta_pistas_audio": True,
        "outtmpl_unicidad": True,
        "calidades_audio": ["128", "192", "256", "320"],
    },
    "Instagram": {"soporta_subtitulos": False},
    "Facebook": {"soporta_subtitulos": False},
    "TikTok": {"soporta_subtitulos": False},
    "Twitch": {"soporta_subtitulos": False},
    "Vimeo": {"soporta_subtitulos": False},
    "Twitter/X": {"soporta_subtitulos": False},
    "Reddit": {"soporta_subtitulos": False},
}


class DescargaCancelada(Exception):
    pass


def find_ffmpeg():
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        for name in ["ffmpeg.exe", "ffmpeg"]:
            if os.path.isfile(os.path.join(app_dir, name)):
                return app_dir
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return os.path.dirname(ffmpeg)
    if sys.platform == "win32":
        for path in [r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin"]:
            if os.path.isfile(os.path.join(path, "ffmpeg.exe")):
                return path
    return None


def detectar_plataforma(url):
    url_lower = url.lower()
    for dominio, nombre in PLATAFORMA_DOMINIOS.items():
        if dominio in url_lower:
            return nombre
    return "Otra"


def es_youtube(url):
    return detectar_plataforma(url) == "YouTube"


def _mtime_perfil(nombre, rutas):
    archivo = NAVEGADORES_ARCHIVO_PERFIL.get(nombre)
    if not archivo:
        return 0.0
    mejor = 0.0
    for ruta in rutas:
        if not os.path.isdir(ruta):
            continue
        try:
            mtime = os.path.getmtime(os.path.join(ruta, archivo))
        except OSError:
            continue
        if mtime > mejor:
            mejor = mtime
    return mejor


def detectar_navegadores():
    detectados = []
    for nombre, rutas in NAVEGADORES_RUTAS.items():
        rutas_so = rutas.get(sys.platform, [])
        archivo = NAVEGADORES_ARCHIVO_PERFIL.get(nombre)
        for ruta in rutas_so:
            if not os.path.isdir(ruta):
                continue
            if archivo and not os.path.isfile(os.path.join(ruta, archivo)):
                continue
            detectados.append((nombre, _mtime_perfil(nombre, [ruta])))
            break
    detectados.sort(key=lambda par: (-par[1], _orden_navegador(par[0])))
    return [nombre for nombre, _ in detectados]


def _orden_navegador(nombre):
    try:
        return ORDEN_NAVEGADORES.index(nombre)
    except ValueError:
        return len(ORDEN_NAVEGADORES)


def construir_opciones_cookies(navegador):
    if not navegador:
        return {}
    return {"cookiesfrombrowser": (navegador, None, None, None)}


class ClasificadorErrores:
    PATRONES = [
        ("members_only", r"members[- ]only|member[- ]only|subscribers?[- ]only"),
        ("age_restricted", r"age[- ]restricted|confirm your age|verify your age"),
        ("bot", r"not a bot|bot check|bot verification|unusual traffic|request complete verification|rate limit|too many requests"),
        ("cookies", r"could not extract cookies|session expired|keyring|could not copy .*cookie database|could not copy .*cookies"),
        ("sign_in", r"granted access|requires authentication|must be logged|login required|log ?in required"),
        ("geo", r"not available in your country|geo-?restricted|blocked in your country|unavailable in your (region|country)"),
        ("sign_in", r"\b(sign in|log ?in|loggin)\b"),
        ("unavailable", r"video unavailable|no longer available|has been removed|has been deleted|content is not available|ya no esta disponible|no esta disponible"),
        ("private", r"private video|video is private|this video is private|account is private|private account"),
        ("extractor", r"unable to extract|nsig|signature extraction|no video formats|did not get a match|failed to resolve|precondition check failed|unexpected response from webpage request|impersonat"),
        ("formato", r"requested format is not available"),
        ("http", r"http error 403|http error 429|forbidden"),
        ("red", r"urlerror|urlopen error|connection|getaddrinfo|temporary failure|timed? ?out|ssl|reset by peer|name or service not known"),
        ("invalid_url", r"is not a valid url|invalid url|unsupported url|not a valid"),
        ("ffmpeg", r"ffmpeg|postprocessing"),
        ("not_found", r"video not found|no such video|404|not found"),
    ]

    MENSAJES = {
        "private": {
            "YouTube": "Este video no esta disponible. Puede que haya sido eliminado o marcado como privado.",
            "Instagram": "Este contenido no esta disponible. Puede ser privado o haber expirado (stories).",
            "Facebook": "Este video no esta disponible. Puede ser privado o haber sido eliminado.",
            "TikTok": "Este video no esta disponible. Puede ser de una cuenta privada.",
        },
        "members_only": {
            "YouTube": "Este video solo esta disponible para miembros del canal.",
        },
        "age_restricted": {
            "YouTube": "Este contenido requiere iniciar sesion para confirmar la edad.",
        },
        "unavailable": {
            "YouTube": "El video ya no esta disponible. Puede que haya sido eliminado.",
            "Instagram": "El contenido ya no esta disponible. Puede ser privado o haber expirado.",
            "Facebook": "El video ya no esta disponible. Puede ser privado o haber sido eliminado.",
            "TikTok": "El video ya no esta disponible. Puede ser de una cuenta privada.",
        },
        "geo": {
            "YouTube": "Este video no esta disponible en tu region.",
        },
        "sign_in": {
            "YouTube": "Este video requiere acceso. Puede ser contenido restringido o privado.",
            "Instagram": "Instagram requiere cuenta para ver este contenido (stories, perfiles privados).",
            "Facebook": "Facebook requiere sesion para ver este video.",
            "TikTok": "TikTok requiere sesion para este video (cuenta privada).",
        },
        "bot": {
            "YouTube": "La plataforma detecto trafico inusual. Intenta de nuevo mas tarde.",
        },
        "invalid_url": {
            "YouTube": "La URL no es valida. Verifica que sea un enlace correcto de YouTube, Instagram, TikTok o Facebook.",
        },
        "extractor": {
            "TikTok": "TikTok bloqueo la extraccion (respuesta inesperada o challenge antiusuario).",
        },
        "not_found": {
            "YouTube": "No se encontro el video. Verifica que la URL sea correcta.",
        },
    }

    MENSAJES_GENERICOS = {
        "private": "Este contenido es privado.",
        "members_only": "Solo disponible para miembros.",
        "age_restricted": "Este contenido requiere iniciar sesion.",
        "unavailable": "El contenido ya no esta disponible.",
        "geo": "El contenido no esta disponible en tu region.",
        "sign_in": "El contenido requiere iniciar sesion en la plataforma.",
        "bot": "La plataforma detecto trafico inusual. Intenta mas tarde.",
        "cookies": "No se pudieron usar las cookies del navegador.",
        "invalid_url": "La URL no es valida. Verifica el enlace.",
        "not_found": "No se encontro el contenido.",
        "extractor": (
            "El motor de descarga (yt-dlp) esta desactualizado para los cambios recientes "
            "de la plataforma."
        ),
        "formato": "No se encontro un formato compatible con la version actual del motor de descarga.",
        "http": "La plataforma rechazo o limito la peticion (HTTP 403/429).",
        "red": "Problema de red al conectar con la plataforma.",
        "ffmpeg": (
            "Necesitas instalar ffmpeg para descargar este video.\n\n"
            "Windows: descargalo de ffmpeg.org\n"
            "Linux: sudo apt install ffmpeg\n"
            "macOS: brew install ffmpeg"
        ),
    }

    SUGERENCIAS = {
        "private": "Inicia sesion en tu navegador en la plataforma y activa 'Usar sesion del navegador'.",
        "members_only": "Verifica que tu cuenta tenga la membresia del canal.",
        "age_restricted": "Inicia sesion en tu navegador en la plataforma y activa 'Usar sesion del navegador'.",
        "geo": "Usa una red en la region permitida para este contenido.",
        "sign_in": "Inicia sesion en tu navegador en la plataforma y activa 'Usar sesion del navegador'.",
        "bot": "Espera unos minutos y vuelve a intentarlo. Si persiste, activa 'Usar sesion del navegador', inicia sesion en YouTube en ese navegador y reintenta.",
        "cookies": "El navegador tiene bloqueada su base de datos de cookies (suele pasar si esta abierto o si su gestor de contrasenas lo impide). Cierra el navegador por completo (revisa el Administrador de tareas: Chrome/Edge/Brave dejan procesos en segundo plano) y reintenta. Si persiste, prueba con otro navegador detectado o exporta las cookies a un archivo.",
        "not_found": "Verifica que la URL este completa y sea correcta.",
        "extractor": "Actualiza yt-dlp desde el Diagnostico o ejecuta: python -m pip install -U \"yt-dlp[default,curl-cffi]\". Si el error es de TikTok y persiste, activa 'Usar sesion del navegador' para pasar el challenge, o espera unos minutos (TikTok bloquea IPs temporalmente).",
        "formato": "Actualiza yt-dlp e intenta de nuevo; tambien puedes cambiar la calidad seleccionada.",
        "http": "Activa 'Usar sesion del navegador' y reintenta; si persiste, espera unos minutos.",
        "red": "Verifica tu conexion a internet e intenta de nuevo.",
    }

    AVAILABILITY_MAP = {
        "private": "private",
        "needs_auth": "sign_in",
        "subscriber_only": "members_only",
        "members_only": "members_only",
        "premium": "members_only",
    }

    @classmethod
    def _mensaje(cls, tipo, plataforma):
        mensaje = cls.MENSAJES.get(tipo, {}).get(plataforma)
        if not mensaje:
            mensaje = cls.MENSAJES.get(tipo, {}).get("YouTube")
        if not mensaje:
            mensaje = cls.MENSAJES_GENERICOS.get(tipo, "No se pudo descargar el video. Verifica que la URL sea correcta y que el video este publico.")
        return mensaje

    @classmethod
    def clasificar(cls, exc, plataforma):
        texto = str(exc)
        msg = texto.lower()
        detalle = sanitizar_detalle(texto)
        for tipo, patron in cls.PATRONES:
            if re.search(patron, msg):
                return {
                    "tipo": tipo,
                    "mensaje": cls._mensaje(tipo, plataforma),
                    "sugerencia": cls.SUGERENCIAS.get(tipo),
                    "detalle": detalle,
                }
        return {
            "tipo": "desconocido",
            "mensaje": "No se pudo descargar el video. Verifica que la URL sea correcta y que el video este publico.",
            "sugerencia": None,
            "detalle": detalle,
        }

    @classmethod
    def clasificar_availability(cls, availability, plataforma):
        tipo = cls.AVAILABILITY_MAP.get(availability or "")
        if not tipo:
            return None
        return {
            "tipo": tipo,
            "mensaje": cls._mensaje(tipo, plataforma),
            "sugerencia": cls.SUGERENCIAS.get(tipo),
            "detalle": "",
        }


def cargar_preferencias():
    defaults = {
        "modo": "audio",
        "calidad": "320",
        "carpeta": os.path.join(os.path.expanduser("~"), "Downloads", "Mi_musica"),
        "subtitulos": False,
        "playlist": False,
        "clipboard_auto": True,
        "usar_sesion_navegador": False,
        "navegador": "",
        "max_paralelas": 1,
        "ocultar_urls": True,
        "actualizar_automaticamente": "preguntar",
        "ultima_revision_update": 0,
        "version_avisada": "",
        "ventana_geom": "",
    }
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                defaults.update(saved)
    except Exception:
        pass
    defaults.pop("tema", None)
    if defaults.get("actualizar_automaticamente") not in ("preguntar", "auto", "desactivado"):
        defaults["actualizar_automaticamente"] = "preguntar"
    return defaults


def guardar_preferencias(prefs):
    try:
        prefs.pop("tema", None)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass


def _opciones_base(navegador=None, cancel_flag=None, impersonate=None, player_client=None):
    opciones = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": TIMEOUT_RED,
        "sleep_interval_requests": 1,
        "extractor_retries": 3,
    }
    if impersonate:
        opciones["impersonate"] = impersonate
    if player_client:
        opciones["extractor_args"] = {"youtube": {"player_client": [player_client]}}
    if cancel_flag is not None:
        def hook(d):
            if cancel_flag.is_set():
                raise DescargaCancelada()
        opciones["progress_hooks"] = [hook]
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path:
        opciones["ffmpeg_location"] = ffmpeg_path
    opciones.update(construir_opciones_cookies(navegador))
    return opciones


def extraer_info_video(url, navegador=None):
    try:
        opciones = _opciones_base(navegador)
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                duracion = info.get("duration", 0)
                mins, secs = divmod(duracion, 60)
                horas, mins = divmod(mins, 60)
                duracion_str = f"{horas}:{mins:02d}:{secs:02d}" if horas else f"{mins}:{secs:02d}"
                return {
                    "titulo": info.get("title", "Sin titulo"),
                    "uploader": info.get("uploader", "Desconocido"),
                    "duracion": duracion_str,
                    "thumbnail": info.get("thumbnail", ""),
                    "es_playlist": info.get("_type") == "playlist",
                    "num_videos": info.get("playlist_count", 1) if info.get("_type") == "playlist" else 1,
                }
    except Exception:
        pass
    return None


CLIENTES_FALLBACK_BOT = ["tv", "web_embedded", "android_vr"]


def _intentar_verificar(url, navegador, cancel_flag, impersonate=None, player_client=None):
    opciones = _opciones_base(navegador, cancel_flag, impersonate=impersonate,
                              player_client=player_client)
    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            return None, None
        plataforma = detectar_plataforma(url)
        restriccion = ClasificadorErrores.clasificar_availability(info.get("availability"), plataforma)
        return info, restriccion


def verificar_url(url, navegador=None, cancel_flag=None):
    resultado = {"reconocida": False, "info": None, "restriccion": None}
    if not url or not PLATFORM_REGEX.search(url):
        return resultado
    resultado["reconocida"] = True
    es_yt = detectar_plataforma(url) == "YouTube"
    try:
        info, restriccion = _intentar_verificar(url, navegador, cancel_flag)
        resultado["info"] = info
        resultado["restriccion"] = restriccion
        return resultado
    except DescargaCancelada:
        resultado["restriccion"] = {"tipo": "cancelada", "mensaje": "Verificacion cancelada", "sugerencia": None, "detalle": ""}
        return resultado
    except yt_dlp.utils.DownloadError as e:
        restriccion = ClasificadorErrores.clasificar(e, detectar_plataforma(url))
        if es_yt and restriccion.get("tipo") == "bot":
            for cliente in CLIENTES_FALLBACK_BOT:
                if cancel_flag is not None and cancel_flag.is_set():
                    resultado["restriccion"] = {"tipo": "cancelada", "mensaje": "Verificacion cancelada", "sugerencia": None, "detalle": ""}
                    return resultado
                try:
                    info, restr_alt = _intentar_verificar(url, navegador, cancel_flag,
                                                          impersonate="chrome", player_client=cliente)
                    resultado["info"] = info
                    resultado["restriccion"] = restr_alt
                    return resultado
                except DescargaCancelada:
                    resultado["restriccion"] = {"tipo": "cancelada", "mensaje": "Verificacion cancelada", "sugerencia": None, "detalle": ""}
                    return resultado
                except yt_dlp.utils.DownloadError:
                    continue
                except Exception:
                    continue
        resultado["restriccion"] = restriccion
        return resultado
    except Exception:
        return resultado


def _mismo_idioma(a, b):
    if not a or not b:
        return False
    a, b = str(a), str(b)
    if a.lower() == b.lower():
        return True
    a_es_base = "-" not in a
    b_es_base = "-" not in b
    if a_es_base and b.lower().startswith(a.lower() + "-"):
        return True
    if b_es_base and a.lower().startswith(b.lower() + "-"):
        return True
    return False


def _pref_positiva(formato):
    pref = formato.get("language_preference")
    if pref is None:
        return False
    try:
        return float(pref) > 0
    except (TypeError, ValueError):
        return False


def _es_formato_audio(formato):
    if not formato.get("format_id"):
        return False
    acodec = formato.get("acodec")
    if not acodec or acodec == "none":
        return False
    return formato.get("vcodec") in (None, "none")


def es_audio_original(formato, info):
    if not isinstance(formato, dict):
        return False
    if _pref_positiva(formato):
        return True
    language = formato.get("language")
    info_language = (info or {}).get("language") if isinstance(info, dict) else None
    return bool(language and info_language and _mismo_idioma(language, info_language))


def nombre_pista_seguro(label):
    texto = "" if label is None else str(label)
    nombre = yt_dlp.utils.sanitize_filename(texto, restricted=False)
    nombre = nombre.replace("%", "\uff05").strip().strip(".")
    return nombre or "pista"


def _etiqueta_pista(formato):
    nota = (formato.get("format_note") or "").strip()
    if nota:
        etiqueta = nota.split(",")[0].strip()
        sufijo = " - dubbed-auto"
        if etiqueta.lower().endswith(sufijo):
            etiqueta = etiqueta[:-len(sufijo)].strip()
        if etiqueta and etiqueta.lower() not in ("low", "medium", "high"):
            return etiqueta
    if formato.get("language"):
        return str(formato["language"])
    return str(formato.get("format_id") or "pista")


def _clave_orden_pista(formato):
    ext = str(formato.get("ext") or "").lower()
    preferencia = 0 if ext == "m4a" else 1
    bitrate = formato.get("abr")
    if bitrate is None:
        bitrate = formato.get("tbr")
    try:
        bitrate = float(bitrate or 0)
    except (TypeError, ValueError):
        bitrate = 0.0
    return (preferencia, -bitrate, str(formato.get("format_id") or ""))


def normalizar_pistas_audio(info):
    if not isinstance(info, dict):
        return []
    formatos = [
        f for f in (info.get("formats") or [])
        if isinstance(f, dict) and _es_formato_audio(f)
    ]
    if not formatos:
        return []

    hay_marca = any(_pref_positiva(f) for f in formatos)
    if hay_marca:
        originales = [
            f.get("language") for f in formatos
            if _pref_positiva(f) and f.get("language")
        ]
        if not originales:
            return []
    else:
        idioma_info = info.get("language")
        if not idioma_info:
            return []
        originales = [
            f.get("language") for f in formatos
            if f.get("language") and _mismo_idioma(f.get("language"), idioma_info)
        ]
        if not originales:
            return []

    originales_unicos = []
    for language in originales:
        if not any(_mismo_idioma(language, conocido) for conocido in originales_unicos):
            originales_unicos.append(language)

    grupos = {}
    for formato in formatos:
        language = formato.get("language")
        if language and any(_mismo_idioma(language, original) for original in originales_unicos):
            continue
        if not language and not hay_marca:
            continue
        clave = str(language).casefold() if language else f"__{formato.get('format_id') or id(formato)}"
        grupos.setdefault(clave, []).append(formato)

    pistas = []
    for candidatos in grupos.values():
        formato = min(candidatos, key=_clave_orden_pista)
        etiqueta = _etiqueta_pista(formato)
        pistas.append({
            "format_id": str(formato.get("format_id") or ""),
            "language": formato.get("language"),
            "label": etiqueta,
            "ext": formato.get("ext"),
            "acodec": formato.get("acodec"),
            "abr": formato.get("abr"),
            "audio_channels": formato.get("audio_channels"),
            "nombre": nombre_pista_seguro(etiqueta),
        })

    pistas.sort(key=lambda p: (p["label"].casefold(), p["format_id"]))

    conteo = Counter(p["nombre"].casefold() for p in pistas)
    for pista in pistas:
        if conteo[pista["nombre"].casefold()] > 1:
            pista["nombre"] = nombre_pista_seguro(
                f'{pista["nombre"]} [{pista["format_id"]}]')

    usados = set()
    for pista in pistas:
        base = pista["nombre"]
        nombre = base
        indice = 2
        while nombre.casefold() in usados:
            nombre = f"{base} ({indice})"
            indice += 1
        pista["nombre"] = nombre
        usados.add(nombre.casefold())

    return pistas


def _construir_opciones_descarga(url, carpeta, modo, calidad, subtitulos, playlist, progreso_callback=None, cancel_flag=None, postprocessor_callback=None, format_id=None, pista_label=None, tmpfile_callback=None):
    plataforma = detectar_plataforma(url)
    youtube = plataforma == "YouTube"

    def progress_hook(d):
        if tmpfile_callback is not None and d.get("status") == "downloading":
            ruta_tmp = d.get("tmpfilename") or d.get("filename")
            if ruta_tmp:
                try:
                    tmpfile_callback(ruta_tmp)
                except Exception:
                    pass
        if cancel_flag is not None and cancel_flag.is_set():
            raise DescargaCancelada()
        if d["status"] == "downloading" and progreso_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            progreso_callback(downloaded / total if total > 0 else 0)
        elif d["status"] == "finished" and progreso_callback:
            progreso_callback(1.0)

    def postprocessor_hook(d):
        if cancel_flag is not None and cancel_flag.is_set():
            raise DescargaCancelada()
        if postprocessor_callback:
            estado = d.get("status")
            if estado in ("started", "finished"):
                postprocessor_callback(estado, d.get("postprocessor") or "")

    ffmpeg_path = find_ffmpeg()

    if format_id:
        nombre = nombre_pista_seguro(pista_label or format_id)
        outtmpl = os.path.join(
            carpeta, "%(title)s [%(id)s]",
            f"audio adicional - {nombre}.%(ext)s")
    elif youtube:
        outtmpl = os.path.join(carpeta, "%(title)s [%(id)s].%(ext)s")
    else:
        outtmpl = os.path.join(carpeta, "%(title)s.%(ext)s")

    opciones = {
        "outtmpl": outtmpl,
        "noplaylist": not playlist,
        "progress_hooks": [progress_hook],
        "socket_timeout": TIMEOUT_RED,
    }
    if postprocessor_callback:
        opciones["postprocessor_hooks"] = [postprocessor_hook]
    if ffmpeg_path:
        opciones["ffmpeg_location"] = ffmpeg_path

    if youtube and subtitulos and not format_id:
        opciones["writesubtitles"] = True
        opciones["subtitleslangs"] = ["es", "en", "pt"]
        opciones["outtmpl"] = {
            "default": outtmpl,
            "subtitle": os.path.join(
                carpeta, "%(title)s [%(id)s]",
                "%(title)s [%(id)s].%(ext)s"),
        }

    if format_id:
        opciones["format"] = str(format_id)
        opciones["noplaylist"] = True
        return opciones

    if modo == "audio":
        if youtube:
            opciones["format"] = "bestaudio/best"
            opciones["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": calidad,
            }]
            opciones["postprocessor_args"] = ["-ar", "44100"]
            opciones["prefer_ffmpeg"] = True
        else:
            opciones["format"] = "bestaudio/best"
            opciones["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": calidad,
            }]
            opciones["prefer_ffmpeg"] = True
    else:
        if youtube:
            opciones["format"] = RESOLUCIONES_YOUTUBE.get(calidad, RESOLUCIONES_YOUTUBE["720p"])
            opciones["merge_output_format"] = "mp4"
            opciones["prefer_ffmpeg"] = True
        else:
            opciones["format"] = RESOLUCIONES_GENERICAS.get(calidad, RESOLUCIONES_GENERICAS["720p"])
            opciones["merge_output_format"] = "mp4"
            opciones["prefer_ffmpeg"] = True

    return opciones


def descargar_musica(url, carpeta, modo, calidad, subtitulos=False, playlist=False, progress_callback=None, speed_callback=None, navegador=None, cancel_flag=None, ydl_holder=None, postprocessor_callback=None, format_id=None, pista_label=None, tmpfile_callback=None):
    plataforma = detectar_plataforma(url)
    es_yt = plataforma == "YouTube"
    try:
        os.makedirs(carpeta, exist_ok=True)

        def blended_hook(d):
            if d["status"] == "downloading" and speed_callback:
                downloaded = d.get("downloaded_bytes", 0)
                elapsed = d.get("elapsed", 0)
                speed = downloaded / elapsed if elapsed > 0 else 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                speed_callback(speed, downloaded, total)

        opciones = _construir_opciones_descarga(
            url, carpeta, modo, calidad, subtitulos, playlist,
            progreso_callback=progress_callback, cancel_flag=cancel_flag,
            postprocessor_callback=postprocessor_callback,
            format_id=format_id, pista_label=pista_label,
            tmpfile_callback=tmpfile_callback,
        )
        opciones.update(construir_opciones_cookies(navegador))

        hooks = opciones.get("progress_hooks", [])
        if speed_callback:
            hooks.append(blended_hook)
        opciones["progress_hooks"] = hooks

        with yt_dlp.YoutubeDL(opciones) as ydl:
            if ydl_holder is not None and isinstance(ydl_holder, dict):
                ydl_holder["ydl"] = ydl
            try:
                ydl.download([url])
            finally:
                if ydl_holder is not None and isinstance(ydl_holder, dict):
                    ydl_holder["ydl"] = None
        return True, "Descarga completada", None

    except DescargaCancelada:
        return False, "Descarga cancelada", "cancelada"
    except yt_dlp.utils.DownloadError as e:
        clasificado = ClasificadorErrores.clasificar(e, plataforma)
        if es_yt and not playlist and clasificado.get("tipo") == "bot":
            return _descargar_fallback_bot(
                url, carpeta, modo, calidad, subtitulos, playlist,
                progress_callback, speed_callback, navegador, cancel_flag,
                ydl_holder, postprocessor_callback, format_id, pista_label,
                tmpfile_callback, clasificado,
            )
        mensaje = clasificado["mensaje"]
        sugerencia = clasificado.get("sugerencia")
        if sugerencia:
            mensaje += "\n\nSugerencia:\n" + sugerencia
        detalle = (clasificado.get("detalle") or "").strip()
        if detalle:
            mensaje += "\n\nDetalle tecnico:\n" + detalle
        return False, mensaje, clasificado.get("tipo")
    except Exception as e:
        clasificado = ClasificadorErrores.clasificar(e, plataforma)
        if clasificado.get("tipo") == "desconocido":
            mensaje = "Ocurrio un error inesperado. Si persiste, intenta con otra URL o reinicia la app."
            detalle = (clasificado.get("detalle") or "").strip()
            if detalle:
                mensaje += "\n\nDetalle tecnico:\n" + detalle
            return False, mensaje, None
        return False, clasificado["mensaje"], clasificado.get("tipo")


def _descargar_fallback_bot(url, carpeta, modo, calidad, subtitulos, playlist,
                            progress_callback, speed_callback, navegador, cancel_flag,
                            ydl_holder, postprocessor_callback, format_id, pista_label,
                            tmpfile_callback, clasificado_original):
    for cliente in CLIENTES_FALLBACK_BOT:
        if cancel_flag is not None and cancel_flag.is_set():
            return False, "Descarga cancelada", "cancelada"
        try:
            os.makedirs(carpeta, exist_ok=True)

            def _hook(d):
                if d["status"] == "downloading" and speed_callback:
                    downloaded = d.get("downloaded_bytes", 0)
                    elapsed = d.get("elapsed", 0)
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    speed_callback(speed, downloaded, total)

            opciones = _construir_opciones_descarga(
                url, carpeta, modo, calidad, subtitulos, playlist,
                progreso_callback=progress_callback, cancel_flag=cancel_flag,
                postprocessor_callback=postprocessor_callback,
                format_id=format_id, pista_label=pista_label,
                tmpfile_callback=tmpfile_callback,
            )
            opciones.update(construir_opciones_cookies(navegador))
            opciones["impersonate"] = "chrome"
            opciones["extractor_args"] = {"youtube": {"player_client": [cliente]}}

            hooks = opciones.get("progress_hooks", [])
            if speed_callback:
                hooks.append(_hook)
            opciones["progress_hooks"] = hooks

            with yt_dlp.YoutubeDL(opciones) as ydl:
                if ydl_holder is not None and isinstance(ydl_holder, dict):
                    ydl_holder["ydl"] = ydl
                try:
                    ydl.download([url])
                finally:
                    if ydl_holder is not None and isinstance(ydl_holder, dict):
                        ydl_holder["ydl"] = None
            return True, "Descarga completada", None
        except DescargaCancelada:
            return False, "Descarga cancelada", "cancelada"
        except yt_dlp.utils.DownloadError:
            continue
        except Exception:
            continue
    mensaje = clasificado_original["mensaje"]
    sugerencia = clasificado_original.get("sugerencia")
    if sugerencia:
        mensaje += "\n\nSugerencia:\n" + sugerencia
    detalle = (clasificado_original.get("detalle") or "").strip()
    if detalle:
        mensaje += "\n\nDetalle tecnico:\n" + detalle
    return False, mensaje, clasificado_original.get("tipo")


def check_for_update(current_version):
    release = obtener_release_latest()
    if not release:
        return False, current_version, ""
    latest = release.get("version", "")
    if latest and latest != current_version:
        return True, latest, release.get("url", "")
    return False, current_version, ""


ASSET_WINDOWS = "YT-DownLoader-Jaeger-Setup.exe"
ASSET_MACOS = "yt-dowloader-macos.dmg"
ASSET_LINUX_DEB = "yt-dowloader-linux.deb"
ASSET_LINUX_TAR = "yt-dowloader-linux.tar.gz"
ASSET_SHA256 = "SHA256SUMS"


def detectar_so():
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return "desconocido"


def detectar_arch():
    maquina = (platform.machine() or "").strip().lower()
    if maquina in ("x86_64", "amd64"):
        return "x86_64"
    if maquina in ("arm64", "aarch64"):
        return "arm64"
    return maquina or "desconocida"


def modo_ejecucion():
    return "frozen" if getattr(sys, "frozen", False) else "fuente"


def ruta_ejecutable():
    if getattr(sys, "frozen", False):
        objetivo = sys.executable
    else:
        objetivo = os.path.abspath(__file__)
    return os.path.realpath(objetivo)


def detectar_instalacion_linux(ruta_exe=None):
    ruta = os.path.realpath(ruta_exe or ruta_ejecutable())
    opt = os.path.realpath("/opt/yt-dowloader")
    if ruta == opt or ruta.startswith(opt + os.sep):
        return "deb"
    return "portable"


def obtener_release_latest():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "yt-dowloader-updater",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        assets = []
        for a in data.get("assets") or []:
            assets.append({
                "name": a.get("name", ""),
                "url": a.get("browser_download_url", ""),
                "size": int(a.get("size") or 0),
            })
        return {
            "version": (data.get("tag_name") or "").lstrip("v"),
            "url": data.get("html_url", ""),
            "assets": assets,
        }
    except Exception:
        return None


def seleccionar_asset_update(assets, so=None):
    so = so or detectar_so()
    objetivo = {
        "windows": ASSET_WINDOWS,
        "macos": ASSET_MACOS,
        "linux": ASSET_LINUX_DEB,
    }.get(so)
    if not objetivo:
        return None
    for a in assets or []:
        if a.get("name") == objetivo and a.get("url"):
            return a
    return None


def parsear_sha256sums(texto):
    hashes = {}
    for linea in (texto or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        partes = linea.split()
        if len(partes) < 2:
            continue
        digest = partes[0].strip().lower()
        nombre = partes[-1].lstrip("*").strip()
        if len(digest) == 64 and nombre:
            hashes[nombre] = digest
    return hashes


def sha256_de_archivo(ruta, bloque=1024 * 256):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while True:
            datos = f.read(bloque)
            if not datos:
                break
            h.update(datos)
    return h.hexdigest()


def verificar_sha256(ruta, esperado):
    esperado = (esperado or "").strip().lower()
    if not esperado or not os.path.isfile(ruta):
        return False
    try:
        return sha256_de_archivo(ruta) == esperado
    except OSError:
        return False


def descargar_asset(url, destino, progress_cb=None, cancel_flag=None):
    parcial = destino + ".part"
    try:
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "yt-dowloader-updater"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_RED) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            descargado = 0
            with open(parcial, "wb") as f:
                while True:
                    if cancel_flag is not None and cancel_flag.is_set():
                        raise DescargaCancelada()
                    bloque = resp.read(1024 * 256)
                    if not bloque:
                        break
                    f.write(bloque)
                    descargado += len(bloque)
                    if progress_cb:
                        progress_cb(descargado, total)
        os.replace(parcial, destino)
        return True, "", destino
    except DescargaCancelada:
        _borrar_silencioso(parcial)
        return False, "Descarga cancelada", None
    except Exception as e:
        _borrar_silencioso(parcial)
        return False, f"No se pudo descargar la actualización: {e}", None


def _borrar_silencioso(ruta):
    try:
        if ruta and os.path.isfile(ruta):
            os.remove(ruta)
    except OSError:
        pass


def comando_actualizacion(ruta_asset, so=None):
    so = so or detectar_so()
    if so == "windows":
        return {
            "args": [ruta_asset, "/S"],
            "requiere_privilegios": True,
            "descripcion": "Se instalará en silencio (Windows pedirá permiso de administrador).",
        }
    if so == "macos":
        return {
            "args": ["open", ruta_asset],
            "requiere_privilegios": False,
            "descripcion": "Se abrirá el .dmg; arrastra la app a Aplicaciones para actualizar.",
        }
    if so == "linux":
        if shutil.which("apt-get"):
            args = ["pkexec", "apt-get", "install", "-y", ruta_asset]
        else:
            args = ["pkexec", "dpkg", "-i", ruta_asset]
        return {
            "args": args,
            "requiere_privilegios": True,
            "descripcion": "Linux pedirá tu contraseña para instalar el paquete.",
        }
    return None


def debe_revisar_update(prefs, intervalo_horas=24, ahora=None):
    """Indica si conviene comprobar si hay una version nueva.

    Ya NO usa un rate-limit por horas: revisa en cada arranque, salvo que la
    actualizacion automatica este desactivada. Los parametros ``intervalo_horas``
    y ``ahora`` se conservan por compatibilidad y no afectan a la decision.
    """
    if (prefs or {}).get("actualizar_automaticamente", "preguntar") == "desactivado":
        return False
    return True


def debe_avisar(version_latest, prefs):
    """Indica si hay que avisar de ``version_latest``.

    Devuelve False si esa misma version ya se avisó (el usuario eligio
    'Mas tarde'), para no repetir la ventana en cada arranque.
    """
    if not version_latest:
        return False
    return (prefs or {}).get("version_avisada", "") != version_latest



def obtener_ultima_version_ytdlp():
    try:
        req = urllib.request.Request(
            "https://pypi.org/pypi/yt-dlp/json",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        return (data.get("info") or {}).get("version", "")
    except Exception:
        return ""


def comparar_versiones(v1, v2):
    def clave(v):
        partes = []
        for x in str(v).split("."):
            try:
                partes.append(int(x))
            except ValueError:
                break
        return tuple(partes)
    k1, k2 = clave(v1), clave(v2)
    if not k1 or not k2:
        return 0
    return (k1 > k2) - (k1 < k2)


def elegir_navegador_sesion(pref_navegador=""):
    detectados = set(detectar_navegadores())
    if pref_navegador in detectados:
        return pref_navegador
    for nav in ORDEN_NAVEGADORES:
        if nav in detectados:
            return nav
    return ""


def navegadores_para_reintento(pref_navegador="", detectados=None):
    if detectados is None:
        detectados = detectar_navegadores()
    orden = []
    if pref_navegador in detectados:
        orden.append(pref_navegador)
    for nav in detectados:
        if nav not in orden:
            orden.append(nav)
    return orden
