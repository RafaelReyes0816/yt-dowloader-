#!/usr/bin/env python3
__version__ = "1.2.3"

import yt_dlp
import os
import sys
import re
import json
import time
import shutil
import queue
import threading
import urllib.request
import customtkinter as ctk

from tkinter import filedialog, messagebox

GITHUB_REPO = "RafaelReyes0816/yt-dowloader-"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".yt-downloader")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
YOUTUBE_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})'
)

COLORS = {
    "bg": "#1a1a2e",
    "bg2": "#16213e",
    "bg3": "#0f3460",
    "accent": "#e94560",
    "accent_hover": "#c73e54",
    "text": "#ffffff",
    "text_dim": "#a0a0b0",
    "success": "#2ecc71",
    "warning": "#f39c12",
    "error": "#e74c3c",
    "input_bg": "#0f3460",
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


def cargar_preferencias():
    defaults = {
        "modo": "audio",
        "calidad": "320",
        "carpeta": os.path.join(os.path.expanduser("~"), "Downloads", "Mi_musica"),
        "subtitulos": False,
        "playlist": False,
        "clipboard_auto": True,
        "tema": "dark",
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
                    "titulo": info.get("title", "Sin título"),
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
        opciones = {
            "outtmpl": os.path.join(carpeta, "%(title)s.%(ext)s"),
            "noplaylist": not playlist,
            "progress_hooks": [progress_hook],
        }
        if ffmpeg_path:
            opciones["ffmpeg_location"] = ffmpeg_path

        if subtitulos:
            opciones["writesubtitles"] = True
            opciones["subtitleslangs"] = ["es", "en", "pt"]

        if modo == "audio":
            opciones["format"] = "bestaudio/best"
            opciones["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": calidad,
            }]
            opciones["postprocessor_args"] = ["-ar", "44100"]
            opciones["prefer_ffmpeg"] = True
        else:
            resoluciones = {
                "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/mp4",
                "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/mp4",
                "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/mp4",
                "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/mp4",
            }
            opciones["format"] = resoluciones.get(calidad, resoluciones["720p"])
            opciones["merge_output_format"] = "mp4"
            opciones["prefer_ffmpeg"] = True

        with yt_dlp.YoutubeDL(opciones) as ydl:
            ydl.download([url])
        return True, "Descarga completada"

    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if "private video" in msg or "unavailable" in msg:
            return False, "El video es privado o no está disponible."
        elif "geo" in msg or "not available in your country" in msg:
            return False, "El video no está disponible en tu región."
        elif "sign in" in msg or "login" in msg:
            return False, "El video requiere iniciar sesión."
        elif "is not a valid url" in msg or "invalid url" in msg:
            return False, "La URL ingresada no es válida."
        elif "ffmpeg" in msg:
            return False, "No se encontró ffmpeg. Instálalo y asegúrate de que esté en el PATH."
        else:
            return False, f"Error de yt-dlp: {e}"
    except Exception as e:
        return False, f"Error inesperado: {e}"


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


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YT-DownLoader del Jaeger")
        self.geometry("900x800")
        self.minsize(900, 800)
        self.resizable(True, True)
        self.configure(fg_color=COLORS["bg"])

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.prefs = cargar_preferencias()
        self.descarga_queue = queue.Queue()
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

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # --- Header ---
        header = ctk.CTkFrame(self, fg_color=COLORS["bg2"], corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="YT-DownLoader", font=("Segoe UI", 24, "bold"),
                     text_color=COLORS["accent"]).grid(row=0, column=0, padx=20, pady=15)

        ffmpeg_text = "ffmpeg OK" if self.ffmpeg_ok else "ffmpeg NO ENCONTRADO"
        ffmpeg_color = COLORS["success"] if self.ffmpeg_ok else COLORS["error"]
        ctk.CTkLabel(header, text=ffmpeg_text, font=("Segoe UI", 11),
                     text_color=ffmpeg_color).grid(row=0, column=1, sticky="e", padx=10)

        self.version_var = ctk.StringVar(value=f"v{__version__}")
        ctk.CTkLabel(header, textvariable=self.version_var, font=("Segoe UI", 11),
                     text_color=COLORS["text_dim"]).grid(row=0, column=2, padx=20)



        # --- Seccion URL ---
        url_frame = ctk.CTkFrame(self, fg_color=COLORS["bg2"], corner_radius=12)
        url_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(15, 10))
        url_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(url_frame, text="URL del Video", font=("Segoe UI", 13, "bold"),
                     text_color=COLORS["text"]).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))

        url_row = ctk.CTkFrame(url_frame, fg_color="transparent")
        url_row.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        url_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(url_row, placeholder_text="Pega la URL del video de YouTube...",
                                       font=("Segoe UI", 13), height=40,
                                       fg_color=COLORS["input_bg"], border_color=COLORS["bg3"])
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.url_entry.focus()

        ctk.CTkButton(url_row, text="Agregar", command=self._agregar_a_cola, width=80,
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"]).grid(row=0, column=1)

        # --- Seccion Opciones ---
        opt_frame = ctk.CTkFrame(self, fg_color=COLORS["bg2"], corner_radius=12)
        opt_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        opt_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(opt_frame, text="Opciones", font=("Segoe UI", 13, "bold"),
                     text_color=COLORS["text"]).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))

        row1 = ctk.CTkFrame(opt_frame, fg_color="transparent")
        row1.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 8))

        self.modo_var = ctk.StringVar(value=self.prefs.get("modo", "audio"))
        ctk.CTkRadioButton(row1, text="Audio (mp3)", variable=self.modo_var, value="audio",
                           command=self._actualizar_calidades,
                           fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"]).pack(side="left", padx=(0, 20))
        ctk.CTkRadioButton(row1, text="Video (mp4)", variable=self.modo_var, value="video",
                           command=self._actualizar_calidades,
                           fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"]).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(row1, text="Calidad:", font=("Segoe UI", 12),
                     text_color=COLORS["text"]).pack(side="left", padx=(20, 5))
        self.calidad_var = ctk.StringVar()
        self.calidad_option = ctk.CTkOptionMenu(row1, variable=self.calidad_var,
                                                 values=["128", "192", "256", "320"],
                                                 fg_color=COLORS["input_bg"],
                                                 button_color=COLORS["bg3"],
                                                 button_hover_color=COLORS["accent"],
                                                 width=100)
        self.calidad_option.pack(side="left")

        self.subtitulos_var = ctk.BooleanVar(value=self.prefs.get("subtitulos", False))
        ctk.CTkCheckBox(row1, text="Subtítulos", variable=self.subtitulos_var,
                        fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"]).pack(side="left", padx=(20, 0))

        self.playlist_var = ctk.BooleanVar(value=self.prefs.get("playlist", False))
        ctk.CTkCheckBox(row1, text="Playlist", variable=self.playlist_var,
                        fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"]).pack(side="left", padx=(10, 0))

        self.clipboard_var = ctk.BooleanVar(value=self.clipboard_auto)
        ctk.CTkCheckBox(row1, text="Auto-URL", variable=self.clipboard_var,
                        command=self._toggle_clipboard,
                        fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"]).pack(side="left", padx=(10, 0))

        # Carpeta destino
        row2 = ctk.CTkFrame(opt_frame, fg_color="transparent")
        row2.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        row2.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row2, text="Guardar en:", font=("Segoe UI", 12),
                     text_color=COLORS["text"]).grid(row=0, column=0, padx=(0, 8))
        self.carpeta_var = ctk.StringVar()
        ctk.CTkEntry(row2, textvariable=self.carpeta_var, font=("Segoe UI", 11),
                     fg_color=COLORS["input_bg"], border_color=COLORS["bg3"]).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ctk.CTkButton(row2, text="Examinar", command=self._seleccionar_carpeta, width=80,
                      fg_color=COLORS["bg3"], hover_color=COLORS["accent"]).grid(row=0, column=2)

        # --- Seccion Cola ---
        cola_frame = ctk.CTkFrame(self, fg_color=COLORS["bg2"], corner_radius=12)
        cola_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 10))
        cola_frame.grid_columnconfigure(0, weight=1)
        cola_frame.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(cola_frame, text="Cola de Descargas", font=("Segoe UI", 13, "bold"),
                     text_color=COLORS["text"]).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))

        self.cola_scroll = ctk.CTkScrollableFrame(cola_frame, fg_color=COLORS["bg"],
                                                    corner_radius=8, scrollbar_fg_color=COLORS["bg3"])
        self.cola_scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))
        self.cola_scroll.grid_columnconfigure(0, weight=1)

        btn_row = ctk.CTkFrame(cola_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

        ctk.CTkButton(btn_row, text="Iniciar descargas", command=self._iniciar_cola,
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"]).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Limpiar cola", command=self._limpiar_cola,
                      fg_color=COLORS["bg3"], hover_color=COLORS["accent"]).pack(side="left")

        # --- Seccion Progreso ---
        prog_frame = ctk.CTkFrame(self, fg_color=COLORS["bg2"], corner_radius=12)
        prog_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 15))
        prog_frame.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(prog_frame, height=12, corner_radius=6,
                                            progress_color=COLORS["accent"],
                                            fg_color=COLORS["bg3"])
        self.progress.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 5))
        self.progress.set(0)

        self.estado_var = ctk.StringVar(value="Listo")
        ctk.CTkLabel(prog_frame, textvariable=self.estado_var, font=("Segoe UI", 11),
                     text_color=COLORS["text_dim"]).grid(row=1, column=0, sticky="w", padx=15, pady=(0, 12))

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
        if self.modo_var.get() == "audio":
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
            if clipboard and YOUTUBE_REGEX.search(clipboard) and clipboard != self.url_entry.get():
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clipboard)
        except Exception:
            pass
        self.after(2000, self._monitorear_clipboard)

    def _agregar_a_cola(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Advertencia", "Ingresa una URL.")
            return

        if not YOUTUBE_REGEX.search(url):
            messagebox.showwarning("Advertencia", "La URL no parece ser de YouTube.")
            return

        modo = self.modo_var.get()
        calidad = self.calidad_var.get()
        carpeta = self.carpeta_var.get()
        subtitulos = self.subtitulos_var.get()
        playlist = self.playlist_var.get()

        display_url = url if len(url) <= 60 else url[:57] + "..."

        item_frame = ctk.CTkFrame(self.cola_scroll, fg_color=COLORS["bg3"], corner_radius=8, height=45)
        item_frame.grid(row=len(self.queue_items), column=0, sticky="ew", pady=3)
        item_frame.grid_columnconfigure(1, weight=1)

        status_label = ctk.CTkLabel(item_frame, text="Pendiente", font=("Segoe UI", 11, "bold"),
                                     text_color=COLORS["warning"], width=100)
        status_label.grid(row=0, column=0, padx=10, pady=8)

        ctk.CTkLabel(item_frame, text=display_url, font=("Segoe UI", 11),
                     text_color=COLORS["text"], anchor="w").grid(row=0, column=1, sticky="w", padx=5)

        tipo_text = "Audio" if modo == "audio" else "Video"
        ctk.CTkLabel(item_frame, text=tipo_text, font=("Segoe UI", 10),
                     text_color=COLORS["text_dim"], width=60).grid(row=0, column=2, padx=10)

        self.queue_items.append({
            "frame": item_frame,
            "status_label": status_label,
            "url": url,
            "modo": modo,
            "calidad": calidad,
            "carpeta": carpeta,
            "subtitulos": subtitulos,
            "playlist": playlist,
        })

        self.url_entry.delete(0, "end")
        self._guardar_prefs_actuales()

    def _iniciar_cola(self):
        if self.is_downloading:
            return

        pending = [item for item in self.queue_items if item["status_label"].cget("text") == "Pendiente"]
        if not pending:
            messagebox.showinfo("Cola vacía", "Agrega videos a la cola primero.")
            return

        self.is_downloading = True
        threading.Thread(target=self._procesar_cola, args=(pending,), daemon=True).start()

    def _procesar_cola(self, pending):
        for item in pending:
            if item["status_label"].cget("text") != "Pendiente":
                continue

            self.after(0, lambda i=item: i["status_label"].configure(text="Descargando...", text_color=COLORS["accent"]))
            self.after(0, lambda: self.progress.set(0))

            def on_progress(val):
                self.after(0, lambda v=val: self.progress.set(v))

            def on_speed(speed, downloaded, total):
                if speed > 1024 * 1024:
                    speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                elif speed > 1024:
                    speed_str = f"{speed / 1024:.0f} KB/s"
                else:
                    speed_str = f"{speed:.0f} B/s"
                pct = (downloaded / total * 100) if total > 0 else 0
                self.after(0, lambda s=speed_str, p=pct: self.estado_var.set(f"Descargando... {s} — {p:.0f}%"))

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
                self.after(0, lambda i=item: i["status_label"].configure(text="Completado", text_color=COLORS["success"]))
                self.historial.append({"url": item["url"], "fecha": time.strftime("%Y-%m-%d %H:%M")})
            else:
                self.after(0, lambda i=item: i["status_label"].configure(text="Error", text_color=COLORS["error"]))
                self.after(0, lambda m=mensaje: messagebox.showerror("Error", m))

            self.after(0, lambda: self.progress.set(1))
            self.after(0, lambda: self.estado_var.set("Listo"))

        self.is_downloading = False

    def _limpiar_cola(self):
        for item in self.queue_items[:]:
            item["frame"].destroy()
        self.queue_items.clear()

    def _check_update_async(self):
        def run():
            has_update, latest, url = check_for_update(__version__)
            if has_update:
                self.after(0, lambda: self._show_update(latest, url))
        threading.Thread(target=run, daemon=True).start()

    def _show_update(self, latest, url):
        respuesta = messagebox.askyesno(
            "Actualización disponible",
            f"Hay una nueva versión: v{latest}\n\n¿Deseas abrir la página de descarga?"
        )
        if respuesta and url:
            import webbrowser
            webbrowser.open(url)


if __name__ == "__main__":
    app = App()
    app.mainloop()
