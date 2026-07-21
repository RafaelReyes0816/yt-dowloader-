#!/usr/bin/env python3
__version__ = "2.1.3"

import yt_dlp
import os
import sys
import re
import json
import math
import time
import shutil
import queue
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


def cargar_preferencias():
    defaults = {
        "modo": "audio",
        "calidad": "320",
        "carpeta": os.path.join(os.path.expanduser("~"), "Downloads", "Mi_musica"),
        "subtitulos": False,
        "playlist": False,
        "clipboard_auto": True,
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


def extraer_info_video(url):
    try:
        opciones = {"quiet": True, "no_warnings": True, "skip_download": True}
        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            opciones["ffmpeg_location"] = ffmpeg_path
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


def descargar_musica(url, carpeta, modo, calidad, subtitulos=False, playlist=False, progress_callback=None, speed_callback=None):
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
        return True, "Descarga completada"

    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if "private video" in msg or "unavailable" in msg:
            mensajes = {
                "Instagram": "Este contenido no esta disponible. Puede ser privado o haber expirado (stories).",
                "Facebook": "Este video no esta disponible. Puede ser privado o haber sido eliminado.",
                "TikTok": "Este video no esta disponible. Puede ser de una cuenta privada.",
                "YouTube": "Este video no esta disponible. Puede que haya sido eliminado o marcado como privado.",
            }
            return False, mensajes.get(plataforma, "El contenido no esta disponible.")
        elif "sign in" in msg or "login" in msg:
            mensajes = {
                "Instagram": "Instagram requiere cuenta para ver este contenido (stories, perfiles privados).",
                "Facebook": "Facebook requiere sesion para ver este video.",
                "TikTok": "TikTok requiere sesion para este video (cuenta privada).",
                "YouTube": "Este video requiere acceso. Puede ser contenido restringido o privado.",
            }
            return False, mensajes.get(plataforma, "El contenido requiere iniciar sesion en la plataforma.")
        elif "geo" in msg or "not available in your country" in msg:
            return False, "Este contenido no esta disponible en tu region. Es posible que este restringido geographicamente."
        elif "is not a valid url" in msg or "invalid url" in msg:
            return False, "La URL no es valida. Verifica que sea un enlace correcto de YouTube, Instagram, TikTok o Facebook."
        elif "ffmpeg" in msg:
            return False, (
                "Necesitas instalar ffmpeg para descargar este video.\n\n"
                "Windows: descargalo de ffmpeg.org\n"
                "Linux: sudo apt install ffmpeg\n"
                "macOS: brew install ffmpeg"
            )
        else:
            return False, "No se pudo descargar el video. Verifica que la URL sea correcta y que el video este publico."
    except Exception as e:
        return False, "Ocurrio un error inesperado. Si persiste, intenta con otra URL o reinicia la app."


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


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YT-DownLoader del Jaeger")
        self.geometry("900x850")
        self.minsize(900, 850)
        self.resizable(True, True)
        self.configure(fg_color=COLORS["bg.base"])

        self._set_window_icon()

        ctk.set_appearance_mode("dark")

        self.prefs = cargar_preferencias()
        self.historial = []
        self.is_downloading = False
        self.clipboard_auto = self.prefs.get("clipboard_auto", True)
        self.ffmpeg_ok = find_ffmpeg() is not None
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
                    from tkinter import PhotoImage
                    self._tk_icon = PhotoImage(file=icon_path)
                    self.iconphoto(True, self._tk_icon)
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

    def _guardar_prefs_actuales(self):
        self.prefs.update({
            "modo": self.modo_var.get(),
            "calidad": self.calidad_var.get(),
            "carpeta": self.carpeta_var.get(),
            "subtitulos": self.subtitulos_var.get(),
            "playlist": self.playlist_var.get(),
            "clipboard_auto": self.clipboard_var.get(),
        })
        guardar_preferencias(self.prefs)

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
            messagebox.showwarning("URL no兼容ible",
                                    "Esta URL no es de una plataforma兼容ible.\n\n"
                                    "Plataformas: YouTube, Instagram, TikTok, Facebook.")
            return

        plataforma = detectar_plataforma(url)
        modo = "audio" if self.modo_var.get().startswith("Audio") else "video"
        calidad = self.calidad_var.get()
        carpeta = self.carpeta_var.get()
        subtitulos = self.subtitulos_var.get()
        playlist = self.playlist_var.get()

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

        self.is_downloading = True
        threading.Thread(target=self._procesar_cola, args=(pending,), daemon=True).start()

    def _procesar_cola(self, pending):
        total = len(pending)
        for idx, item in enumerate(pending):
            if item["card"].status_label.cget("text") != "Pendiente":
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

            exito, mensaje = descargar_musica(
                item["url"],
                item["carpeta"],
                item["modo"],
                item["calidad"],
                subtitulos=item["subtitulos"],
                playlist=item["playlist"],
                progress_callback=on_progress,
                speed_callback=on_speed,
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
