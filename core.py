import os
import re
import json
import sys
import shutil
import urllib.request

import yt_dlp

GITHUB_REPO = "RafaelReyes0816/yt-dowloader-"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".yt-downloader")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
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

TIPOS_BLOQUEANTES = {
    "private", "members_only", "age_restricted", "sign_in", "geo",
    "unavailable", "not_found", "cookies", "bot",
}

TIPOS_REINTENTO_SESION = {"private", "members_only", "age_restricted", "sign_in", "cookies", "bot"}

ORDEN_NAVEGADORES = ["firefox", "chrome", "brave", "edge"]

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
    "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/mp4",
    "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/mp4",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/mp4",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/mp4",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
}

RESOLUCIONES_GENERICAS = {
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
}

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


def detectar_navegadores():
    detectados = []
    for nombre, rutas in NAVEGADORES_RUTAS.items():
        if any(os.path.isdir(r) for r in rutas.get(sys.platform, [])):
            detectados.append(nombre)
    return detectados


def construir_opciones_cookies(navegador):
    if not navegador:
        return {}
    return {"cookiesfrombrowser": (navegador, None, None, None)}


class ClasificadorErrores:
    PATRONES = [
        ("members_only", r"members[- ]only|member[- ]only|subscribers?[- ]only"),
        ("age_restricted", r"age[- ]restricted|confirm your age|verify your age"),
        ("bot", r"not a bot|bot check|bot verification|unusual traffic|request complete verification|rate limit|too many requests"),
        ("cookies", r"could not extract cookies|session expired|keyring"),
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
        "bot": "Espera unos minutos y vuelve a intentarlo.",
        "cookies": "Abre el navegador, inicia sesion en la plataforma y reintenta. Si el navegador esta en uso, cierra su gestor de contrasenas.",
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
        detalle = texto.strip()
        if len(detalle) > 400:
            detalle = detalle[:400] + "..."
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
    }
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            defaults.update(saved)
    except Exception:
        pass
    return defaults


def guardar_preferencias(prefs):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass


def _opciones_base(navegador=None, cancel_flag=None):
    opciones = {"quiet": True, "no_warnings": True, "skip_download": True}
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


def verificar_url(url, navegador=None, cancel_flag=None):
    resultado = {"reconocida": False, "info": None, "restriccion": None}
    if not url or not PLATFORM_REGEX.search(url):
        return resultado
    resultado["reconocida"] = True
    try:
        opciones = _opciones_base(navegador, cancel_flag)
        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return resultado
            resultado["info"] = info
            plataforma = detectar_plataforma(url)
            restriccion = ClasificadorErrores.clasificar_availability(info.get("availability"), plataforma)
            if restriccion:
                resultado["restriccion"] = restriccion
            return resultado
    except DescargaCancelada:
        resultado["restriccion"] = {"tipo": "cancelada", "mensaje": "Verificacion cancelada", "sugerencia": None, "detalle": ""}
        return resultado
    except yt_dlp.utils.DownloadError as e:
        resultado["restriccion"] = ClasificadorErrores.clasificar(e, detectar_plataforma(url))
        return resultado
    except Exception:
        return resultado


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


def check_for_update(current_version):
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            latest = data.get("tag_name", "").lstrip("v")
            if latest and latest != current_version:
                return True, latest, data.get("html_url", "")
        return False, current_version, ""
    except Exception:
        return False, current_version, ""


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
