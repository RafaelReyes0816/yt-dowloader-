#!/usr/bin/env python3
__version__ = "2.2.1"

import yt_dlp
import os
import sys
import re
import json
import math
import time
import shutil
import queue
import subprocess
import tkinter
import threading
import urllib.request
import customtkinter as ctk

from tkinter import filedialog, messagebox

GITHUB_REPO = "RafaelReyes0816/yt-dowloader-"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".yt-downloader")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PLATFORM_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:'
    r'youtube\.com|youtu\.be|'
    r'instagram\.com|instagr\.am|'
    r'facebook\.com|fb\.watch|'
    r'tiktok\.com|vm\.tiktok\.com'
    r')'
)

COLORS = {
    "bg.base": "#0B0F1A",
    "bg.surface": "#141B2D",
    "bg.surface-hover": "#1B2438",
    "border.subtle": "#232D45",
    "text.primary": "#E8ECF4",
    "text.secondary": "#8B96AE",
    "accent.brand": "#FF4F6E",
    "accent.brand-hover": "#E03A58",
    "accent.success": "#35D499",
    "accent.progress": "#FFB454",
    "accent.error": "#FF5D5D",
}

FONTS = {
    "display": ("Segoe UI", 22, "bold"),
    "subtitle": ("Segoe UI", 13),
    "body": ("Segoe UI", 13),
    "body_bold": ("Segoe UI", 13, "bold"),
    "small": ("Segoe UI", 11),
    "small_bold": ("Segoe UI", 11, "bold"),
    "mono": ("Consolas", 12),
    "tag": ("Segoe UI", 10),
}


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
    dominios = {
        "youtube.com": "YouTube", "youtu.be": "YouTube",
        "instagram.com": "Instagram", "instagr.am": "Instagram",
        "facebook.com": "Facebook", "fb.watch": "Facebook",
        "tiktok.com": "TikTok", "vm.tiktok.com": "TikTok",
    }
    url_lower = url.lower()
    for dominio, nombre in dominios.items():
        if dominio in url_lower:
            return nombre
    return "Otra"


def es_youtube(url):
    return detectar_plataforma(url) == "YouTube"


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
        ("extractor", r"unable to extract|nsig|signature extraction|no video formats|did not get a match|failed to resolve|precondition check failed"),
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
        "extractor": "Actualiza yt-dlp desde el Diagnostico o ejecuta: python -m pip install -U yt-dlp",
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


def extraer_info_video(url, navegador=None):
    try:
        opciones = {"quiet": True, "no_warnings": True, "skip_download": True}
        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            opciones["ffmpeg_location"] = ffmpeg_path
        opciones.update(construir_opciones_cookies(navegador))
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


def verificar_url(url, navegador=None):
    resultado = {"reconocida": False, "info": None, "restriccion": None}
    if not url or not PLATFORM_REGEX.search(url):
        return resultado
    resultado["reconocida"] = True
    try:
        opciones = {"quiet": True, "no_warnings": True, "skip_download": True}
        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            opciones["ffmpeg_location"] = ffmpeg_path
        opciones.update(construir_opciones_cookies(navegador))
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
    except yt_dlp.utils.DownloadError as e:
        resultado["restriccion"] = ClasificadorErrores.clasificar(e, detectar_plataforma(url))
        return resultado
    except Exception:
        return resultado


def descargar_musica(url, carpeta, modo, calidad, subtitulos=False, playlist=False, progress_callback=None, speed_callback=None, navegador=None):
    plataforma = detectar_plataforma(url)
    try:
        os.makedirs(carpeta, exist_ok=True)

        def progress_hook(d):
            if d["status"] == "downloading" and progress_callback:
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                elapsed = d.get("elapsed", 0)
                speed = downloaded / elapsed if elapsed > 0 else 0
                if total > 0:
                    progress_callback(downloaded / total)
                if speed_callback:
                    speed_callback(speed, downloaded, total)
            elif d["status"] == "finished" and progress_callback:
                progress_callback(1.0)

        ffmpeg_path = find_ffmpeg()
        youtube = plataforma == "YouTube"

        opciones = {
            "outtmpl": os.path.join(carpeta, "%(title)s.%(ext)s"),
            "noplaylist": not playlist,
            "progress_hooks": [progress_hook],
        }
        if ffmpeg_path:
            opciones["ffmpeg_location"] = ffmpeg_path
        opciones.update(construir_opciones_cookies(navegador))

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
                    "preferredquality": "192",
                }]
                opciones["prefer_ffmpeg"] = True
        else:
            if youtube:
                resoluciones = {
                    "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/mp4",
                    "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/mp4",
                    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/mp4",
                    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/mp4",
                }
                opciones["format"] = resoluciones.get(calidad, resoluciones["720p"])
                opciones["merge_output_format"] = "mp4"
                opciones["prefer_ffmpeg"] = True
            else:
                opciones["format"] = "best"
                opciones["merge_output_format"] = "mp4"
                opciones["prefer_ffmpeg"] = True

        with yt_dlp.YoutubeDL(opciones) as ydl:
            ydl.download([url])
        return True, "Descarga completada", None

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
    except Exception:
        return False, "Ocurrio un error inesperado. Si persiste, intenta con otra URL o reinicia la app.", None


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


class SegmentedControl(ctk.CTkFrame):
    def __init__(self, master, options, variable, command=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.options = options
        self.variable = variable
        self.command = command
        self.buttons = []
        self._build()

    def _build(self):
        for i, option in enumerate(self.options):
            btn = ctk.CTkButton(
                self,
                text=option,
                font=FONTS["small"],
                corner_radius=8,
                height=32,
                command=lambda o=option: self._select(o),
            )
            btn.pack(side="left", padx=(0, 4))
            self.buttons.append((option, btn))
        self._update_style()

    def _select(self, option):
        self.variable.set(option)
        self._update_style()
        if self.command:
            self.command()

    def _update_style(self):
        current = self.variable.get()
        for option, btn in self.buttons:
            if option == current:
                btn.configure(fg_color=COLORS["accent.brand"], text_color=COLORS["text.primary"])
            else:
                btn.configure(fg_color=COLORS["bg.surface"], text_color=COLORS["text.secondary"],
                              hover_color=COLORS["bg.surface-hover"])


class PillToggle(ctk.CTkButton):
    def __init__(self, master, text, variable, command=None, **kwargs):
        super().__init__(master, text=text, font=FONTS["small"], height=32,
                         corner_radius=999, command=self._toggle, **kwargs)
        self.variable = variable
        self.external_command = command
        self._update_style()
        self.variable.trace_add("write", lambda *_: self._update_style())

    def _toggle(self):
        self.variable.set(not self.variable.get())
        if self.external_command:
            self.external_command()

    def _update_style(self):
        if self.variable.get():
            self.configure(fg_color=COLORS["accent.brand"], text_color=COLORS["text.primary"],
                           hover_color=COLORS["accent.brand-hover"])
        else:
            self.configure(fg_color=COLORS["bg.surface"], text_color=COLORS["text.secondary"],
                           hover_color=COLORS["bg.surface-hover"])


class QueueCard(ctk.CTkFrame):
    def __init__(self, master, url, plataforma, modo, on_destroy=None, **kwargs):
        super().__init__(master, fg_color=COLORS["bg.surface"], corner_radius=12, height=60, **kwargs)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)
        self.url = url
        self.plataforma = plataforma
        self.modo = modo
        self.progress_value = 0
        self.on_destroy = on_destroy

        self.canvas = tkinter.Canvas(self, width=40, height=40,
                                      bg=COLORS["bg.surface"], highlightthickness=0)
        self.canvas.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=10)
        self._draw_ring(0)

        self.url_label = ctk.CTkLabel(self, text=self._truncate_url(url),
                                       font=FONTS["mono"], text_color=COLORS["text.primary"],
                                       anchor="w")
        self.url_label.grid(row=0, column=1, sticky="sw", padx=(0, 8), pady=(10, 0))

        self.micro_bar = ctk.CTkProgressBar(self, height=2, corner_radius=1,
                                             progress_color=COLORS["accent.progress"],
                                             fg_color=COLORS["border.subtle"])
        self.micro_bar.grid(row=1, column=1, sticky="nw", padx=(0, 8), pady=(2, 10))
        self.micro_bar.set(0)

        tag_text = f"[{plataforma}] "
        tag_text += "Audio" if modo == "audio" else "Video"
        self.tag_label = ctk.CTkLabel(self, text=tag_text, font=FONTS["tag"],
                                       text_color=COLORS["text.secondary"], width=120)
        self.tag_label.grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=10)

        self.status_label = ctk.CTkLabel(self, text="Pendiente", font=FONTS["small_bold"],
                                          text_color=COLORS["accent.progress"], width=100)
        self.status_label.grid(row=0, column=3, rowspan=2, padx=(0, 12), pady=10)

    def _truncate_url(self, url):
        return url if len(url) <= 50 else url[:47] + "..."

    def _draw_ring(self, pct):
        self.canvas.delete("all")
        cx, cy, r = 20, 20, 16
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 outline=COLORS["border.subtle"], width=3)
        if pct > 0:
            extent = max(1, int(pct * 360))
            self.canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                    start=90, extent=-extent,
                                    outline=COLORS["accent.progress"], width=3, style="arc")
        self.canvas.create_text(cx, cy, text=f"{int(pct * 100)}%",
                                 fill=COLORS["text.primary"], font=FONTS["small"])

    def update_progress(self, pct):
        self.progress_value = pct
        self.after(0, self._refresh_progress)

    def _refresh_progress(self):
        self.micro_bar.set(self.progress_value)
        self._draw_ring(self.progress_value)

    def set_status(self, text, color):
        self.after(0, lambda: self.status_label.configure(text=text, text_color=color))
        if color == COLORS["accent.progress"]:
            self.after(0, lambda: self._draw_ring(self.progress_value))
        elif color == COLORS["accent.success"]:
            self.after(0, lambda: self._draw_ring(1.0))
            self.after(0, lambda: self.micro_bar.set(1.0))
        elif color == COLORS["accent.error"]:
            self.after(0, lambda: self.status_label.configure(text=f"Error"))

    def set_error_color(self):
        self.after(0, lambda: self.configure(border_width=2, border_color=COLORS["accent.error"]))
        self.after(0, lambda: self.canvas.delete("all"))
        self.after(0, lambda: self._draw_error_icon())

    def _draw_error_icon(self):
        self.canvas.delete("all")
        cx, cy = 20, 20
        self.canvas.create_text(cx, cy, text="!",
                                fill=COLORS["accent.error"], font=FONTS["body_bold"])


class VentanaDiagnostico(ctk.CTkToplevel):
    def __init__(self, master, url="", navegador=""):
        super().__init__(master)
        self.title("Diagnostico")
        self.geometry("520x500")
        self.resizable(False, False)
        self.transient(master)
        self.url = url.strip()
        self.navegador = navegador
        self.checks = {}
        self._build_ui()
        self.after(100, lambda: threading.Thread(target=self._run_checks, daemon=True).start())

    def _build_ui(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=12)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(frame, text="Diagnostico", font=FONTS["display"],
                     text_color=COLORS["text.primary"]).pack(anchor="w", padx=15, pady=(15, 2))
        ctk.CTkLabel(frame, text="Estado de los componentes necesarios para descargar.",
                     font=FONTS["small"], text_color=COLORS["text.secondary"]).pack(anchor="w", padx=15, pady=(0, 12))

        self.checks_list = ctk.CTkFrame(frame, fg_color="transparent")
        self.checks_list.pack(fill="x", padx=15)

        self.checks["url"] = self._crear_check("URL")
        self.checks["ffmpeg"] = self._crear_check("FFmpeg")
        self.checks["ytdlp"] = self._crear_check("yt-dlp")
        self.checks["navegador"] = self._crear_check("Navegador")
        self.checks["acceso"] = self._crear_check("Acceso al contenido")

        self.detail_label = ctk.CTkLabel(frame, text="", font=FONTS["small"],
                                         text_color=COLORS["text.secondary"], justify="left",
                                         wraplength=470, anchor="w")
        self.detail_label.pack(fill="x", padx=15, pady=(10, 4))

        self.btn_actualizar_ytdlp = ctk.CTkButton(
            frame, text="Actualizar motor yt-dlp", height=32,
            font=FONTS["small_bold"],
            fg_color=COLORS["accent.progress"],
            hover_color="#E09A3E",
            text_color="#1A1207",
            command=self._actualizar_motor,
        )

    def _crear_check(self, titulo):
        row = ctk.CTkFrame(self.checks_list, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text=titulo, font=FONTS["body_bold"],
                     text_color=COLORS["text.primary"], width=170, anchor="w").pack(side="left")
        status = ctk.CTkLabel(row, text="· Analizando...", font=FONTS["small"],
                              text_color=COLORS["text.secondary"])
        status.pack(side="right")
        return status

    def _set(self, check_id, estado, color):
        self.after(0, lambda: self.checks[check_id].configure(text=estado, text_color=color))

    def _run_checks(self):
        if self.url and PLATFORM_REGEX.search(self.url):
            self._set("url", "OK · URL compatible", COLORS["accent.success"])
        elif not self.url:
            self._set("url", "Sin URL", COLORS["text.secondary"])
        else:
            self._set("url", "ERROR · URL no compatible", COLORS["accent.error"])

        if find_ffmpeg():
            self._set("ffmpeg", "OK · encontrado", COLORS["accent.success"])
        else:
            self._set("ffmpeg", "ERROR · no encontrado", COLORS["accent.error"])

        try:
            version = yt_dlp.version.__version__
            latest = obtener_ultima_version_ytdlp()
            if latest and comparar_versiones(latest, version) > 0:
                self._set("ytdlp", f"DESACTUALIZADO · v{version} · hay v{latest}",
                          COLORS["accent.error"])
                self.after(0, lambda: self.btn_actualizar_ytdlp.pack(fill="x", padx=15, pady=(8, 0)))
            elif latest:
                self._set("ytdlp", f"v{version} · actualizado", COLORS["accent.success"])
            else:
                self._set("ytdlp", f"v{version}", COLORS["text.secondary"])
        except Exception:
            self._set("ytdlp", "ERROR · no disponible", COLORS["accent.error"])

        navegadores = detectar_navegadores()
        if navegadores:
            self._set("navegador", "OK · " + ", ".join(n.capitalize() for n in navegadores), COLORS["accent.success"])
        else:
            self._set("navegador", "Ninguno detectado", COLORS["text.secondary"])

        if not self.url:
            self._set("acceso", "Sin URL para analizar", COLORS["text.secondary"])
            return

        resultado = verificar_url(self.url, self.navegador)
        restriccion = resultado.get("restriccion")
        if restriccion:
            self._set("acceso", "RESTRINGIDO · " + restriccion["tipo"], COLORS["accent.error"])
            texto = restriccion["mensaje"]
            sugerencia = restriccion.get("sugerencia")
            if sugerencia:
                texto += "\n\nSugerencia: " + sugerencia
            detalle = (restriccion.get("detalle") or "").strip()
            if detalle:
                texto += "\n\nDetalle tecnico:\n" + detalle
            self.after(0, lambda t=texto: self.detail_label.configure(text=t))
        elif resultado.get("info"):
            self._set("acceso", "OK · acceso publico", COLORS["accent.success"])
        else:
            self._set("acceso", "Sin datos", COLORS["text.secondary"])

    def _actualizar_motor(self):
        if getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Actualizar motor yt-dlp",
                "Esta version empaquetada usa yt-dlp fijo.\n\n"
                "Descarga la ultima version de la aplicacion desde GitHub Releases.",
            )
            import webbrowser
            webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases/latest")
            return
        try:
            self.btn_actualizar_ytdlp.configure(state="disabled")
        except Exception:
            pass
        self._set("ytdlp", "Actualizando yt-dlp...", COLORS["accent.progress"])
        threading.Thread(target=self._actualizar_motor_hilo, daemon=True).start()

    def _actualizar_motor_hilo(self):
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True, text=True,
        )
        try:
            from importlib.metadata import version as version_paquete
            instalada = version_paquete("yt-dlp")
        except Exception:
            instalada = ""
        if proc.returncode == 0 and instalada:
            self._set("ytdlp", f"v{instalada} · actualizado, reinicia la app",
                      COLORS["accent.success"])
            self.after(0, lambda v=instalada: messagebox.showinfo(
                "Motor actualizado",
                f"yt-dlp se actualizo a la v{v}.\n\nReinicia la aplicacion para aplicar los cambios.",
            ))
        else:
            self._set("ytdlp", "ERROR · fallo la actualizacion", COLORS["accent.error"])
            detalle = (proc.stderr or proc.stdout or "").strip()[-400:]
            self.after(0, lambda d=detalle: messagebox.showerror(
                "No se pudo actualizar",
                f"Fallo pip upgrade.\n\nDetalle tecnico:\n{d}",
            ))
        self.after(0, lambda: self.btn_actualizar_ytdlp.configure(state="normal"))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YT-DownLoader del Jaeger")
        self.geometry("900x900")
        self.minsize(900, 900)
        self.resizable(True, True)
        self.configure(fg_color=COLORS["bg.base"])

        self._set_window_icon()

        ctk.set_appearance_mode("dark")

        self.prefs = cargar_preferencias()
        self.historial = []
        self.is_downloading = False
        self.clipboard_auto = self.prefs.get("clipboard_auto", True)
        self.ffmpeg_ok = find_ffmpeg() is not None
        self.navegadores = detectar_navegadores()
        self.queue_items = []

        self._build_ui()
        self._aplicar_preferencias()
        self._check_update_async()
        if self.clipboard_auto:
            self._monitorear_clipboard()

    def _set_window_icon(self):
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            if sys.platform == "win32":
                icon_path = os.path.join(base, "assets", "icons", "icon.ico")
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
            else:
                icon_path = os.path.join(base, "assets", "icons", "icon.png")
                if os.path.exists(icon_path):
                    from PIL import Image as PILImage
                    from tkinter import PhotoImage
                    img = PILImage.open(icon_path).resize((64, 64), PILImage.LANCZOS)
                    self._tk_icon = PhotoImage(img)
                    self.iconphoto(True, self._tk_icon)
                self.tk.call('wm', 'iconname', self._w, 'YT-DownLoader')
                self.wm_class("YT-DownLoader", "YT-DownLoader")
        except Exception:
            pass

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # --- Header ---
        header = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=0, height=70)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="YT-DownLoader del Jaeger", font=FONTS["display"],
                     text_color=COLORS["accent.brand"]).grid(row=0, column=0, padx=20, pady=(12, 0))

        ctk.CTkLabel(header, text="Descarga video o audio desde una URL",
                     font=FONTS["subtitle"], text_color=COLORS["text.secondary"]
                     ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        header_right = ctk.CTkFrame(header, fg_color="transparent")
        header_right.grid(row=0, column=1, rowspan=2, sticky="e", padx=20)

        ffmpeg_bg = COLORS["bg.surface"] if self.ffmpeg_ok else COLORS["accent.error"]
        ffmpeg_text_color = COLORS["accent.success"] if self.ffmpeg_ok else COLORS["text.primary"]
        ffmpeg_dot = COLORS["accent.success"] if self.ffmpeg_ok else COLORS["text.primary"]
        ffmpeg_label_text = "ffmpeg OK" if self.ffmpeg_ok else "ffmpeg no encontrado"

        ffmpeg_badge = ctk.CTkFrame(header_right, fg_color=ffmpeg_bg, corner_radius=999, height=28)
        ffmpeg_badge.pack(side="right", padx=(8, 0))
        ctk.CTkLabel(ffmpeg_badge, text=f"  {ffmpeg_label_text}  ",
                     font=FONTS["small"], text_color=ffmpeg_text_color).pack(padx=4, pady=2)

        ctk.CTkLabel(header_right, text=f"v{__version__}",
                     font=FONTS["small"], text_color=COLORS["text.secondary"]).pack(side="right", padx=(0, 8))

        # --- Seccion URL ---
        url_frame = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=12)
        url_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(15, 10))
        url_frame.grid_columnconfigure(0, weight=1)

        url_row = ctk.CTkFrame(url_frame, fg_color="transparent")
        url_row.grid(row=0, column=0, sticky="ew", padx=15, pady=12)
        url_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(url_row,
                                       placeholder_text="Pega la URL del video (YouTube, Instagram, TikTok, Facebook)...",
                                       font=FONTS["mono"], height=40,
                                       fg_color=COLORS["bg.base"],
                                       border_color=COLORS["border.subtle"],
                                       text_color=COLORS["text.primary"],
                                       placeholder_text_color=COLORS["text.secondary"])
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.url_entry.focus()

        ctk.CTkButton(url_row, text="Agregar", command=self._agregar_a_cola, width=90, height=40,
                      font=FONTS["body_bold"],
                      fg_color=COLORS["accent.brand"], hover_color=COLORS["accent.brand-hover"],
                      text_color=COLORS["text.primary"]).grid(row=0, column=1)

        # --- Seccion Opciones ---
        opt_frame = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=12)
        opt_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        opt_frame.grid_columnconfigure(0, weight=1)

        row1 = ctk.CTkFrame(opt_frame, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 8))

        self.modo_var = ctk.StringVar(value=self.prefs.get("modo", "audio"))
        self.modo_control = SegmentedControl(row1, ["Audio (mp3)", "Video (mp4)"],
                                              self.modo_var, command=self._actualizar_calidades)
        self.modo_control.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row1, text="Calidad:", font=FONTS["small"],
                     text_color=COLORS["text.secondary"]).pack(side="left", padx=(0, 6))
        self.calidad_var = ctk.StringVar()
        self.calidad_option = ctk.CTkOptionMenu(row1, variable=self.calidad_var,
                                                 values=["128", "192", "256", "320"],
                                                 font=FONTS["small"],
                                                 fg_color=COLORS["bg.base"],
                                                 button_color=COLORS["border.subtle"],
                                                 button_hover_color=COLORS["bg.surface-hover"],
                                                 dropdown_fg_color=COLORS["bg.surface"],
                                                 dropdown_hover_color=COLORS["bg.surface-hover"],
                                                 width=100, height=32)
        self.calidad_option.pack(side="left")

        row_toggles = ctk.CTkFrame(opt_frame, fg_color="transparent")
        row_toggles.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 12))

        self.subtitulos_var = ctk.BooleanVar(value=self.prefs.get("subtitulos", False))
        PillToggle(row_toggles, "Subtitulos", self.subtitulos_var,
                   fg_color=COLORS["bg.surface"], text_color=COLORS["text.secondary"],
                   hover_color=COLORS["bg.surface-hover"]).pack(side="left", padx=(0, 6))

        self.playlist_var = ctk.BooleanVar(value=self.prefs.get("playlist", False))
        PillToggle(row_toggles, "Playlist", self.playlist_var,
                   fg_color=COLORS["bg.surface"], text_color=COLORS["text.secondary"],
                   hover_color=COLORS["bg.surface-hover"]).pack(side="left", padx=(0, 6))

        self.clipboard_var = ctk.BooleanVar(value=self.clipboard_auto)
        PillToggle(row_toggles, "Auto-URL", self.clipboard_var, command=self._toggle_clipboard,
                   fg_color=COLORS["bg.surface"], text_color=COLORS["text.secondary"],
                   hover_color=COLORS["bg.surface-hover"]).pack(side="left")

        row2 = ctk.CTkFrame(opt_frame, fg_color="transparent")
        row2.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 12))
        row2.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row2, text="Guardar en:", font=FONTS["small"],
                     text_color=COLORS["text.secondary"]).grid(row=0, column=0, padx=(0, 8))
        self.carpeta_var = ctk.StringVar()
        ctk.CTkEntry(row2, textvariable=self.carpeta_var, font=FONTS["small"],
                     fg_color=COLORS["bg.base"], border_color=COLORS["border.subtle"],
                     text_color=COLORS["text.primary"]).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ctk.CTkButton(row2, text="Examinar", command=self._seleccionar_carpeta, width=80, height=32,
                      font=FONTS["small"],
                      fg_color=COLORS["bg.base"], hover_color=COLORS["bg.surface-hover"],
                      border_color=COLORS["border.subtle"], border_width=1,
                      text_color=COLORS["text.secondary"]).grid(row=0, column=2)

        row3 = ctk.CTkFrame(opt_frame, fg_color="transparent")
        row3.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 12))
        row3.grid_columnconfigure(2, weight=1)

        self.usar_sesion_var = ctk.BooleanVar(value=self.prefs.get("usar_sesion_navegador", False))
        PillToggle(row3, "Usar sesion del navegador", self.usar_sesion_var,
                   command=self._actualizar_estado_navegador,
                   fg_color=COLORS["bg.surface"], text_color=COLORS["text.secondary"],
                   hover_color=COLORS["bg.surface-hover"]).grid(row=0, column=0, sticky="w", padx=(0, 8))

        ctk.CTkLabel(row3, text="Navegador:", font=FONTS["small"],
                     text_color=COLORS["text.secondary"]).grid(row=0, column=1, sticky="w", padx=(0, 6))

        pref_nav = self.prefs.get("navegador", "")
        nav_inicial = pref_nav.capitalize() if pref_nav in self.navegadores else (self.navegadores[0].capitalize() if self.navegadores else "Sin detectar")
        self.navegador_var = ctk.StringVar(value=nav_inicial)
        self.navegador_option = ctk.CTkOptionMenu(row3, variable=self.navegador_var,
                                                  values=[n.capitalize() for n in self.navegadores] or ["Sin detectar"],
                                                  font=FONTS["small"],
                                                  fg_color=COLORS["bg.base"],
                                                  button_color=COLORS["border.subtle"],
                                                  button_hover_color=COLORS["bg.surface-hover"],
                                                  dropdown_fg_color=COLORS["bg.surface"],
                                                  dropdown_hover_color=COLORS["bg.surface-hover"],
                                                  width=120, height=32)
        self.navegador_option.grid(row=0, column=2, sticky="w")

        # --- Seccion Cola ---
        cola_frame = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=12)
        cola_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 10))
        cola_frame.grid_columnconfigure(0, weight=1)
        cola_frame.grid_rowconfigure(1, weight=1)

        cola_header = ctk.CTkFrame(cola_frame, fg_color="transparent")
        cola_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))
        cola_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(cola_header, text="Cola de Descargas", font=FONTS["body_bold"],
                     text_color=COLORS["text.primary"]).grid(row=0, column=0, sticky="w")

        self.cola_counter = ctk.CTkLabel(cola_header, text="0 items", font=FONTS["small"],
                                          text_color=COLORS["text.secondary"])
        self.cola_counter.grid(row=0, column=1, sticky="e")

        self.cola_scroll = ctk.CTkScrollableFrame(cola_frame, fg_color=COLORS["bg.base"],
                                                   corner_radius=8,
                                                   scrollbar_fg_color=COLORS["border.subtle"],
                                                   scrollbar_button_color=COLORS["border.subtle"],
                                                   scrollbar_button_hover_color=COLORS["bg.surface-hover"])
        self.cola_scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))
        self.cola_scroll.grid_columnconfigure(0, weight=1)

        self.empty_state_frame = ctk.CTkFrame(self.cola_scroll, fg_color="transparent")
        self.empty_state_frame.grid(row=0, column=0, sticky="nsew", pady=60)
        self.empty_state_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.empty_state_frame, text="+", font=("Segoe UI", 36),
                     text_color=COLORS["border.subtle"]).grid(row=0, column=0)
        ctk.CTkLabel(self.empty_state_frame, text="Pega una URL arriba para empezar",
                     font=FONTS["body"], text_color=COLORS["text.secondary"]).grid(row=1, column=0, pady=(8, 0))

        btn_row = ctk.CTkFrame(cola_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

        ctk.CTkButton(btn_row, text="Iniciar descargas", command=self._iniciar_cola,
                      font=FONTS["body_bold"], height=36,
                      fg_color=COLORS["accent.brand"], hover_color=COLORS["accent.brand-hover"],
                      text_color=COLORS["text.primary"]).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Limpiar cola", command=self._limpiar_cola,
                      font=FONTS["body"], height=36,
                      fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
                      border_color=COLORS["border.subtle"], border_width=1,
                      text_color=COLORS["text.secondary"]).pack(side="left")
        ctk.CTkButton(btn_row, text="Diagnostico", command=self._abrir_diagnostico,
                      font=FONTS["body"], height=36,
                      fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
                      border_color=COLORS["border.subtle"], border_width=1,
                      text_color=COLORS["text.secondary"]).pack(side="left", padx=(8, 0))

        # --- Status bar ---
        status_bar = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=0, height=36)
        status_bar.grid(row=4, column=0, sticky="ew", padx=0, pady=0)
        status_bar.grid_columnconfigure(1, weight=1)

        self.estado_var = ctk.StringVar(value="Listo")
        ctk.CTkLabel(status_bar, textvariable=self.estado_var, font=FONTS["small"],
                     text_color=COLORS["text.secondary"]).grid(row=0, column=0, sticky="w", padx=20, pady=8)

        self.status_counter = ctk.CTkLabel(status_bar, text="", font=FONTS["small"],
                                            text_color=COLORS["text.secondary"])
        self.status_counter.grid(row=0, column=1, sticky="e", padx=20, pady=8)

    def _aplicar_preferencias(self):
        self.modo_var.set(self.prefs.get("modo", "audio"))
        self._actualizar_calidades()
        self.calidad_var.set(self.prefs.get("calidad", "320"))
        self.carpeta_var.set(self.prefs.get("carpeta", os.path.join(os.path.expanduser("~"), "Downloads", "Mi_musica")))
        self.usar_sesion_var.set(self.prefs.get("usar_sesion_navegador", False))
        navegador_pref = self.prefs.get("navegador", "")
        if navegador_pref in self.navegadores:
            self.navegador_var.set(navegador_pref.capitalize())
        self._actualizar_estado_navegador()

    def _guardar_prefs_actuales(self):
        self.prefs.update({
            "modo": self.modo_var.get(),
            "calidad": self.calidad_var.get(),
            "carpeta": self.carpeta_var.get(),
            "subtitulos": self.subtitulos_var.get(),
            "playlist": self.playlist_var.get(),
            "clipboard_auto": self.clipboard_var.get(),
            "usar_sesion_navegador": self.usar_sesion_var.get(),
            "navegador": self._navegador_seleccionado(),
        })
        guardar_preferencias(self.prefs)

    def _navegador_seleccionado(self):
        if not self.usar_sesion_var.get() or not self.navegadores:
            return ""
        valor = self.navegador_var.get().lower()
        return valor if valor in self.navegadores else ""

    def _actualizar_estado_navegador(self):
        state = "normal" if (self.usar_sesion_var.get() and self.navegadores) else "disabled"
        self.navegador_option.configure(state=state)

    def _elegir_navegador_sesion(self):
        detectados = set(detectar_navegadores())
        pref = self.prefs.get("navegador", "")
        if pref in detectados:
            return pref
        for nav in ORDEN_NAVEGADORES:
            if nav in detectados:
                return nav
        return ""

    def _actualizar_calidades(self):
        if self.modo_var.get().startswith("Audio"):
            self.calidad_option.configure(values=["128", "192", "256", "320"])
            if not self.calidad_var.get() or self.calidad_var.get() not in ("128", "192", "256", "320"):
                self.calidad_var.set("320")
        else:
            self.calidad_option.configure(values=["360p", "480p", "720p", "1080p"])
            if not self.calidad_var.get() or self.calidad_var.get() not in ("360p", "480p", "720p", "1080p"):
                self.calidad_var.set("720p")

    def _seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if carpeta:
            self.carpeta_var.set(carpeta)

    def _toggle_clipboard(self):
        self.clipboard_auto = self.clipboard_var.get()
        if self.clipboard_auto:
            self._monitorear_clipboard()

    def _monitorear_clipboard(self):
        if not self.clipboard_auto:
            return
        try:
            clipboard = self.clipboard_get()
            if clipboard and PLATFORM_REGEX.search(clipboard) and clipboard != self.url_entry.get():
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clipboard)
        except Exception:
            pass
        self.after(2000, self._monitorear_clipboard)

    def _actualizar_counter(self):
        total = len(self.queue_items)
        pending = sum(1 for i in self.queue_items if i["card"].status_label.cget("text") == "Pendiente")
        downloading = sum(1 for i in self.queue_items if i["card"].status_label.cget("text") == "Descargando...")
        done = sum(1 for i in self.queue_items if i["card"].status_label.cget("text") == "Completado")
        error = sum(1 for i in self.queue_items if i["card"].status_label.cget("text") == "Error")

        self.cola_counter.configure(text=f"{total} items")

        parts = []
        if downloading > 0:
            parts.append(f"{downloading} activa{'s' if downloading > 1 else ''}")
        if pending > 0:
            parts.append(f"{pending} pendiente{'s' if pending > 1 else ''}")
        if done > 0:
            parts.append(f"{done} completada{'s' if done > 1 else ''}")
        if error > 0:
            parts.append(f"{error} con error")

        self.status_counter.configure(text=" · ".join(parts) if parts else "")

    def _toggle_empty_state(self):
        if self.queue_items:
            self.empty_state_frame.grid_forget()
        else:
            self.empty_state_frame.grid(row=0, column=0, sticky="nsew", pady=60)

    def _agregar_a_cola(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Sin URL", "Pega una URL en el campo de arriba.")
            return

        if not PLATFORM_REGEX.search(url):
            messagebox.showwarning("URL no compatible",
                                    "Esta URL no es de una plataforma compatible.\n\n"
                                    "Plataformas: YouTube, Instagram, TikTok, Facebook.")
            return

        plataforma = detectar_plataforma(url)
        modo = "audio" if self.modo_var.get().startswith("Audio") else "video"
        calidad = self.calidad_var.get()
        carpeta = self.carpeta_var.get()
        subtitulos = self.subtitulos_var.get()
        playlist = self.playlist_var.get()
        navegador = self._navegador_seleccionado()

        card = QueueCard(self.cola_scroll, url, plataforma, modo)
        card.grid(row=len(self.queue_items), column=0, sticky="ew", pady=4)

        self.queue_items.append({
            "card": card,
            "url": url,
            "plataforma": plataforma,
            "modo": modo,
            "calidad": calidad,
            "carpeta": carpeta,
            "subtitulos": subtitulos,
            "playlist": playlist,
            "navegador": navegador,
        })

        self.url_entry.delete(0, "end")
        self._toggle_empty_state()
        self._actualizar_counter()
        self._guardar_prefs_actuales()

    def _iniciar_cola(self):
        if self.is_downloading:
            return

        pending = [item for item in self.queue_items if item["card"].status_label.cget("text") == "Pendiente"]
        if not pending:
            messagebox.showinfo("Cola vacia", "Agrega videos a la cola primero.")
            return

        nav_sesion = self._navegador_seleccionado()
        self.is_downloading = True
        threading.Thread(target=self._procesar_cola, args=(pending, nav_sesion), daemon=True).start()

    def _procesar_cola(self, pending, navegador_actual):
        total = len(pending)
        for idx, item in enumerate(pending):
            if item["card"].status_label.cget("text") != "Pendiente":
                continue

            self.after(0, lambda i=item: i["card"].set_status("Verificando...", COLORS["accent.progress"]))
            self.after(0, lambda: self.estado_var.set(f"Verificando {idx + 1} de {total}..."))
            self.after(0, self._actualizar_counter)

            precheck = verificar_url(item["url"], navegador_actual)
            restriccion = precheck.get("restriccion")
            if restriccion and restriccion.get("tipo") in TIPOS_BLOQUEANTES:
                mensaje = restriccion["mensaje"]
                sugerencia = restriccion.get("sugerencia")
                if sugerencia:
                    mensaje += "\n\nSugerencia:\n" + sugerencia
                self.after(0, lambda i=item: i["card"].set_status("Error", COLORS["accent.error"]))
                self.after(0, lambda i=item: i["card"].set_error_color())
                self.after(0, lambda m=mensaje: messagebox.showerror("No se pudo descargar", m))
                self.after(0, self._actualizar_counter)
                continue

            self.after(0, lambda i=item: i["card"].set_status("Descargando...", COLORS["accent.progress"]))
            self.after(0, lambda: self.estado_var.set(f"Descargando {idx + 1} de {total}..."))
            self.after(0, self._actualizar_counter)

            def on_progress(val):
                self.after(0, lambda v=val: item["card"].update_progress(v))

            def on_speed(speed, downloaded, total_bytes):
                if speed > 1024 * 1024:
                    speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                elif speed > 1024:
                    speed_str = f"{speed / 1024:.0f} KB/s"
                else:
                    speed_str = f"{speed:.0f} B/s"
                self.after(0, lambda s=speed_str: self.estado_var.set(f"Descargando {idx + 1} de {total}... {s}"))

            exito, mensaje, tipo_fallo = descargar_musica(
                item["url"],
                item["carpeta"],
                item["modo"],
                item["calidad"],
                subtitulos=item["subtitulos"],
                playlist=item["playlist"],
                progress_callback=on_progress,
                speed_callback=on_speed,
                navegador=navegador_actual,
            )

            if not exito and tipo_fallo in TIPOS_REINTENTO_SESION and not navegador_actual:
                nav = self._elegir_navegador_sesion()
                if nav:
                    self.after(0, lambda i=item: i["card"].set_status("Reintentando con sesion...", COLORS["accent.progress"]))
                    self.after(0, lambda n=nav: self.estado_var.set(f"Reintentando {idx + 1} de {total} con sesion de {n.capitalize()}..."))
                    exito, mensaje, tipo_fallo = descargar_musica(
                        item["url"],
                        item["carpeta"],
                        item["modo"],
                        item["calidad"],
                        subtitulos=item["subtitulos"],
                        playlist=item["playlist"],
                        progress_callback=on_progress,
                        speed_callback=on_speed,
                        navegador=nav,
                    )

            if exito:
                self.after(0, lambda i=item: i["card"].set_status("Completado", COLORS["accent.success"]))
                self.historial.append({"url": item["url"], "fecha": time.strftime("%Y-%m-%d %H:%M")})
            else:
                self.after(0, lambda i=item: i["card"].set_status("Error", COLORS["accent.error"]))
                self.after(0, lambda i=item: i["card"].set_error_color())
                self.after(0, lambda m=mensaje: messagebox.showerror("No se pudo descargar", m))

            self.after(0, self._actualizar_counter)

        self.is_downloading = False
        self.after(0, lambda: self.estado_var.set("Listo"))
        self.after(0, self._actualizar_counter)

    def _limpiar_cola(self):
        for item in self.queue_items[:]:
            item["card"].destroy()
        self.queue_items.clear()
        self._toggle_empty_state()
        self._actualizar_counter()

    def _abrir_diagnostico(self):
        url = self.url_entry.get().strip()
        if not url:
            for item in self.queue_items:
                url = item["url"]
                break
        navegador = self._navegador_seleccionado()
        VentanaDiagnostico(self, url, navegador)

    def _check_update_async(self):
        def run():
            has_update, latest, url = check_for_update(__version__)
            if has_update:
                self.after(0, lambda: self._show_update(latest, url))
        threading.Thread(target=run, daemon=True).start()

    def _show_update(self, latest, url):
        respuesta = messagebox.askyesno(
            "Actualizacion disponible",
            f"Hay una nueva version: v{latest}\n\n"
            "Deseas abrir la pagina de descarga?"
        )
        if respuesta and url:
            import webbrowser
            webbrowser.open(url)


if __name__ == "__main__":
    app = App()
    app.mainloop()
