import os
import re
import json
import sys
import shutil
import hashlib
import platform
import urllib.request

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

TIMEOUT_RED = 20

# --- Contrato de tipos de restriccion -----------------------------------------
# TIPOS_CUENTA: el contenido exige una cuenta de la plataforma (privado, de
#   miembros, con limite de edad o que pide iniciar sesion).
# TIPOS_REINTENTO_SESION: la UI debe reintentar la descarga con la sesion de
#   otro navegador. NO incluye "bot": la escalera completa (clientes de yt-dlp
#   + TODOS los navegadores detectados) ya la ejecuta
#   core._descargar_fallback_bot, y repetirla en la UI solo duplicaria el
#   trabajo (cada navegador volveria a probar los 3 clientes).
# TIPOS_REINTENTO_CLIENTES: el error se combate cambiando de cliente de
#   yt-dlp. Tambien lo resuelve core (verificar_url / _descargar_fallback_bot).
# TIPOS_BLOQUEANTES: errores que impiden seguir. Un tipo de "bot" NO aborta la
#   verificacion: la descarga tiene su propia escalera y debe llegar a correr.
TIPOS_CUENTA = {"private", "members_only", "age_restricted", "sign_in"}

TIPOS_REINTENTO_SESION = TIPOS_CUENTA | {"cookies"}

TIPOS_REINTENTO_CLIENTES = {"bot"}

TIPOS_BLOQUEANTES = TIPOS_REINTENTO_SESION | TIPOS_REINTENTO_CLIENTES | {
    "geo", "unavailable", "not_found",
}


def reintentar_con_sesion(tipo):
    """True si la UI debe reintentar la descarga con la sesion de otro navegador.

    Excluye "bot" a proposito: la escalera completa ya la ejecuta core
    (clientes + todos los navegadores). Repetirla aqui duplicaria el trabajo.
    """
    return tipo in TIPOS_REINTENTO_SESION


def debe_abortar_descarga(tipo):
    """True si la verificacion debe abortar sin intentar descargar nada."""
    if tipo not in TIPOS_BLOQUEANTES:
        return False
    return tipo not in TIPOS_REINTENTO_SESION and tipo not in TIPOS_REINTENTO_CLIENTES


ORDEN_NAVEGADORES = ["zen", "firefox", "waterfox", "librewolf", "brave", "vivaldi", "opera", "chrome", "edge"]

NAVEGADORES_COMPATIBLES_ABIERTOS = ["zen", "firefox", "waterfox", "librewolf"]

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
    "zen": {
        "win32": [os.path.join(os.environ.get("APPDATA", ""), "zen")],
        "darwin": [os.path.expanduser("~/Library/Application Support/zen")],
        "linux": [os.path.expanduser("~/.zen"), os.path.expanduser("~/.var/app/app.zen_browser.zen/.zen")],
    },
    "vivaldi": {
        "win32": [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Vivaldi", "User Data")],
        "darwin": [os.path.expanduser("~/Library/Application Support/Vivaldi")],
        "linux": [os.path.expanduser("~/.config/vivaldi")],
    },
    "opera": {
        "win32": [os.path.join(os.environ.get("APPDATA", ""), "Opera Software", "Opera Stable")],
        "darwin": [os.path.expanduser("~/Library/Application Support/com.operasoftware.Opera")],
        "linux": [os.path.expanduser("~/.config/opera")],
    },
    "waterfox": {
        "win32": [os.path.join(os.environ.get("APPDATA", ""), "Waterfox")],
        "darwin": [os.path.expanduser("~/Library/Application Support/Waterfox")],
        "linux": [os.path.expanduser("~/.waterfox")],
    },
    "librewolf": {
        "win32": [os.path.join(os.environ.get("APPDATA", ""), "librewolf")],
        "darwin": [os.path.expanduser("~/Library/Application Support/librewolf")],
        "linux": [
            os.path.expanduser("~/.librewolf"),
            os.path.expanduser("~/.var/app/io.gitlab.librewolf-community/.librewolf"),
        ],
    },
}

# Navegadores Gecko (Firefox y forks) que yt-dlp no conoce por nombre:
# se leen pasando ("firefox", <ruta_perfil>, None, None).
NAVEGADORES_GECKO = {"firefox", "zen", "waterfox", "librewolf"}

NAVEGADORES_ARCHIVO_PERFIL = {
    "chrome": PERFIL_CHROMIUM,
    "edge": PERFIL_CHROMIUM,
    "brave": PERFIL_CHROMIUM,
    "vivaldi": PERFIL_CHROMIUM,
    "opera": PERFIL_CHROMIUM,
    "firefox": PERFIL_FIREFOX,
    "zen": PERFIL_FIREFOX,
    "waterfox": PERFIL_FIREFOX,
    "librewolf": PERFIL_FIREFOX,
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


def _leer_profiles_ini(ruta_ini):
    dicts = {}
    seccion = None
    try:
        with open(ruta_ini, "r", encoding="utf-8", errors="ignore") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith(";"):
                    continue
                if linea.startswith("[") and linea.endswith("]"):
                    seccion = linea[1:-1]
                    dicts[seccion] = {}
                elif seccion and "=" in linea:
                    clave, _, valor = linea.partition("=")
                    dicts[seccion][clave.strip()] = valor.strip()
    except OSError:
        return {}
    return dicts


def _candidatos_perfil_gecko(raiz):
    rutas = []
    ini = os.path.join(raiz, "profiles.ini")
    if os.path.isfile(ini):
        for seccion, datos in _leer_profiles_ini(ini).items():
            if not seccion.startswith("Profile"):
                continue
            ruta = datos.get("Path")
            if not ruta:
                continue
            if datos.get("IsRelative", "1") == "1":
                ruta = os.path.join(raiz, ruta)
            rutas.append(ruta)
    for sub in ("Profiles", ""):
        base = os.path.join(raiz, sub) if sub else raiz
        if os.path.isdir(base):
            try:
                rutas.extend(os.path.join(base, n) for n in os.listdir(base))
            except OSError:
                pass
    return rutas


def perfil_gecko(navegador):
    rutas = NAVEGADORES_RUTAS.get(navegador, {}).get(sys.platform, [])
    mejor, mejor_ts = "", -1.0
    for raiz in rutas:
        if not os.path.isdir(raiz):
            continue
        for candidato in _candidatos_perfil_gecko(raiz):
            db = os.path.join(candidato, "cookies.sqlite")
            try:
                ts = os.path.getmtime(db)
            except OSError:
                continue
            if ts > mejor_ts:
                mejor, mejor_ts = candidato, ts
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


def navegadores_cacheados(prefs=None):
    if prefs is None:
        prefs = cargar_preferencias()
    cache = prefs.get("navegadores_detectados")
    if isinstance(cache, list) and cache:
        return [n for n in cache if n in NAVEGADORES_RUTAS]
    detectados = detectar_navegadores()
    if detectados:
        prefs["navegadores_detectados"] = detectados
        guardar_preferencias(prefs)
    return detectados


def construir_opciones_cookies(navegador):
    if not navegador:
        return {}
    if navegador in NAVEGADORES_GECKO and navegador != "firefox":
        perfil = perfil_gecko(navegador)
        if perfil:
            return {"cookiesfrombrowser": ("firefox", perfil, None, None)}
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
        "bot": "La plataforma esta bloqueando la IP de esta conexion, no la app: ninguna version ni ajuste la evita. Espera unos minutos, cambia de red (VPN, datos moviles u otra conexion) o prueba desde otro equipo. La app ya probo automaticamente varios clientes de yt-dlp y todos los navegadores detectados. La sesion del navegador solo sirve para contenido que exige cuenta (privado, de miembros, con limite de edad).",
        "cookies": "El navegador tiene bloqueada su base de datos de cookies (Chrome/Edge/Brave/Vivaldi lo hacen si estan abiertos o por cifrado DPAPI en Windows). La app prueba automaticamente todos los navegadores detectados en orden (primero los Gecko: Firefox/Zen/Waterfox/LibreWolf, que se leen sin cerrarlos). Si con ninguno funciona, cierra el navegador por completo (revisa el Administrador de tareas: hay procesos en segundo plano) y reintenta.",
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
    def _sugerencia(cls, tipo, msg):
        sugerencia = cls.SUGERENCIAS.get(tipo)
        if tipo == "cookies" and re.search(r"could not copy .*cookie", msg):
            sugerencia = (sugerencia or "") + (
                " En Linux, las cookies de Chrome/Edge/Brave se descifran con el modulo "
                "'secretstorage' (libsecret): la app ya lo incluye, pero si ejecutas el codigo "
                "desde el terminal instalalo con 'python3 -m pip install secretstorage'. "
                "En cualquier sistema, Firefox/Zen/Waterfox/LibreWolf se leen sin cifrado del "
                "sistema y sin cerrar el navegador."
            )
        return sugerencia

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
                    "sugerencia": cls._sugerencia(tipo, msg),
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
        "navegadores_detectados": [],
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


def _verificar_cancelada():
    return {"tipo": "cancelada", "mensaje": "Verificacion cancelada", "sugerencia": None, "detalle": ""}


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
        resultado["restriccion"] = _verificar_cancelada()
        return resultado
    except yt_dlp.utils.DownloadError as e:
        restriccion = ClasificadorErrores.clasificar(e, detectar_plataforma(url))
        if es_yt and restriccion.get("tipo") in ("bot", "cookies"):
            for intento in _intentos_fallback_verificacion(navegador):
                if cancel_flag is not None and cancel_flag.is_set():
                    resultado["restriccion"] = _verificar_cancelada()
                    return resultado
                try:
                    info, restr_alt = _intentar_verificar(url, intento["navegador"], cancel_flag,
                                                          impersonate=intento.get("impersonate"),
                                                          player_client=intento.get("cliente"))
                    resultado["info"] = info
                    resultado["restriccion"] = restr_alt
                    return resultado
                except DescargaCancelada:
                    resultado["restriccion"] = _verificar_cancelada()
                    return resultado
                except yt_dlp.utils.DownloadError:
                    continue
                except Exception:
                    continue
        resultado["restriccion"] = restriccion
        return resultado
    except Exception:
        return resultado


def _intentos_fallback_verificacion(navegador):
    intentos = []
    for cliente in CLIENTES_FALLBACK_BOT:
        intentos.append({"navegador": navegador, "impersonate": "chrome", "cliente": cliente})
    for nav in navegadores_para_reintento(navegador or ""):
        if nav == navegador:
            continue
        intentos.append({"navegador": nav})
    return intentos


def _construir_opciones_descarga(url, carpeta, modo, calidad, subtitulos, playlist, progreso_callback=None, cancel_flag=None, postprocessor_callback=None):
    plataforma = detectar_plataforma(url)
    youtube = plataforma == "YouTube"

    def progress_hook(d):
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

    if youtube:
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

    if youtube and subtitulos:
        opciones["writesubtitles"] = True
        opciones["subtitleslangs"] = ["es", "en", "pt"]

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


def descargar_musica(url, carpeta, modo, calidad, subtitulos=False, playlist=False, progress_callback=None, speed_callback=None, navegador=None, cancel_flag=None, ydl_holder=None, postprocessor_callback=None):
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
                ydl_holder, postprocessor_callback, clasificado,
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
                            ydl_holder, postprocessor_callback, clasificado_original):
    ultimo_clasificado = clasificado_original
    for intento in _intentos_fallback_descarga(navegador):
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
            )
            navegador_intento = intento.get("navegador")
            opciones.update(construir_opciones_cookies(navegador_intento))
            if intento.get("impersonate"):
                opciones["impersonate"] = intento["impersonate"]
            if intento.get("cliente"):
                opciones["extractor_args"] = {"youtube": {"player_client": [intento["cliente"]]}}

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
        except yt_dlp.utils.DownloadError as e:
            ultimo_clasificado = ClasificadorErrores.clasificar(e, detectar_plataforma(url))
            continue
        except Exception as e:
            clasificado = ClasificadorErrores.clasificar(e, detectar_plataforma(url))
            if clasificado.get("tipo") != "desconocido":
                ultimo_clasificado = clasificado
            continue
    mensaje = ultimo_clasificado["mensaje"]
    sugerencia = ultimo_clasificado.get("sugerencia")
    if sugerencia:
        mensaje += "\n\nSugerencia:\n" + sugerencia
    detalle = (ultimo_clasificado.get("detalle") or "").strip()
    if detalle:
        mensaje += "\n\nDetalle tecnico:\n" + detalle
    return False, mensaje, ultimo_clasificado.get("tipo")


def _intentos_fallback_descarga(navegador):
    intentos = [{"navegador": navegador, "impersonate": "chrome", "cliente": cliente}
                for cliente in CLIENTES_FALLBACK_BOT]
    for nav in navegadores_para_reintento(navegador or ""):
        if nav == navegador:
            continue
        intentos.append({"navegador": nav})
    return intentos


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
    else:
        for nav in NAVEGADORES_COMPATIBLES_ABIERTOS:
            if nav in detectados and nav not in orden:
                orden.append(nav)
    for nav in detectados:
        if nav not in orden:
            orden.append(nav)
    return orden
