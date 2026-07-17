#!/usr/bin/env python3
__version__ = "1.1.0"

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
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    HAS_BOOTSTRAP = True
except ImportError:
    from tkinter import ttk
    HAS_BOOTSTRAP = False


GITHUB_REPO = "RafaelReyes0816/yt-dowloader-"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".yt-downloader")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
YOUTUBE_REGEX = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})'
)


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
        "tema": "darkly",
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
        return True, f"Descarga completada"

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


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("YT-DownLoader del Jaeger")
        self.root.geometry("850x750")
        self.root.minsize(850, 750)
        self.root.resizable(True, True)

        self.prefs = cargar_preferencias()
        self.descarga_queue = queue.Queue()
        self.historial = []
        self.is_downloading = False
        self.clipboard_auto = self.prefs.get("clipboard_auto", True)
        self.ffmpeg_ok = find_ffmpeg() is not None
        self.preview_data = None

        tema = self.prefs.get("tema", "darkly")
        if HAS_BOOTSTRAP:
            self.root.style = ttk.Style(tema)
        else:
            self.root.configure(bg="#181818")
            style = ttk.Style()
            style.theme_use("clam")

        self._build_ui()
        self._aplicar_preferencias()
        self._check_update_async()
        if self.clipboard_auto:
            self._monitorear_clipboard()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Seccion URL ---
        url_frame = ttk.Labelframe(main_frame, text=" URL del Video ", padding=12)
        url_frame.pack(fill=tk.X, pady=(0, 12))

        self.url_var = tk.StringVar()
        entry = ttk.Entry(url_frame, textvariable=self.url_var, font=("Segoe UI", 12), width=50)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        entry.focus()

        ttk.Button(url_frame, text="Preview", command=self._preview_video, width=10).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(url_frame, text="Agregar", command=self._agregar_a_cola, width=10).pack(side=tk.LEFT)

        # Preview area
        self.preview_frame = ttk.Frame(main_frame)
        self.preview_frame.pack(fill=tk.X, pady=(0, 12))

        self.preview_label = ttk.Label(self.preview_frame, text="", font=("Segoe UI", 10))
        self.preview_label.pack(anchor=tk.W)

        self.preview_titulo = ttk.Label(self.preview_frame, text="", font=("Segoe UI", 11, "bold"))
        self.preview_titulo.pack(anchor=tk.W)

        self.preview_info = ttk.Label(self.preview_frame, text="", font=("Segoe UI", 9))
        self.preview_info.pack(anchor=tk.W)

        # --- Seccion Opciones ---
        opt_frame = ttk.Labelframe(main_frame, text=" Opciones ", padding=12)
        opt_frame.pack(fill=tk.X, pady=(0, 12))

        top_opts = ttk.Frame(opt_frame)
        top_opts.pack(fill=tk.X, pady=(0, 8))

        self.modo_var = tk.StringVar(value=self.prefs.get("modo", "audio"))
        ttk.Radiobutton(top_opts, text="Audio (mp3)", variable=self.modo_var, value="audio",
                         command=self._actualizar_calidades).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Radiobutton(top_opts, text="Video (mp4)", variable=self.modo_var, value="video",
                         command=self._actualizar_calidades).pack(side=tk.LEFT, padx=(0, 16))

        ttk.Label(top_opts, text="Calidad:").pack(side=tk.LEFT, padx=(16, 4))
        self.calidad_var = tk.StringVar()
        self.calidad_combo = ttk.Combobox(top_opts, textvariable=self.calidad_var, width=8, state="readonly")
        self.calidad_combo.pack(side=tk.LEFT)

        self.subtitulos_var = tk.BooleanVar(value=self.prefs.get("subtitulos", False))
        ttk.Checkbutton(top_opts, text="Subtítulos", variable=self.subtitulos_var).pack(side=tk.LEFT, padx=(16, 0))

        self.playlist_var = tk.BooleanVar(value=self.prefs.get("playlist", False))
        ttk.Checkbutton(top_opts, text="Playlist", variable=self.playlist_var).pack(side=tk.LEFT, padx=(8, 0))

        self.clipboard_var = tk.BooleanVar(value=self.clipboard_auto)
        ttk.Checkbutton(top_opts, text="Auto-detectar URL", variable=self.clipboard_var,
                         command=self._toggle_clipboard).pack(side=tk.LEFT, padx=(16, 0))

        # Carpeta destino
        carpeta_row = ttk.Frame(opt_frame)
        carpeta_row.pack(fill=tk.X)

        ttk.Label(carpeta_row, text="Guardar en:").pack(side=tk.LEFT, padx=(0, 8))
        self.carpeta_var = tk.StringVar()
        ttk.Entry(carpeta_row, textvariable=self.carpeta_var, font=("Segoe UI", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(carpeta_row, text="Examinar", command=self._seleccionar_carpeta, width=10).pack(side=tk.LEFT)

        # --- Seccion Cola ---
        cola_frame = ttk.Labelframe(main_frame, text=" Cola de Descargas ", padding=12)
        cola_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        cols = ("estado", "titulo", "tipo")
        self.cola_tree = ttk.Treeview(cola_frame, columns=cols, show="headings", height=6)
        self.cola_tree.heading("estado", text="Estado")
        self.cola_tree.heading("titulo", text="Título")
        self.cola_tree.heading("tipo", text="Tipo")
        self.cola_tree.column("estado", width=100, anchor=tk.CENTER)
        self.cola_tree.column("titulo", width=450)
        self.cola_tree.column("tipo", width=80, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(cola_frame, orient=tk.VERTICAL, command=self.cola_tree.yview)
        self.cola_tree.configure(yscrollcommand=scrollbar.set)

        self.cola_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_row = ttk.Frame(cola_frame)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="Iniciar descargas", command=self._iniciar_cola).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="Limpiar cola", command=self._limpiar_cola).pack(side=tk.LEFT)

        # --- Seccion Progreso ---
        prog_frame = ttk.Labelframe(main_frame, text=" Progreso ", padding=12)
        prog_frame.pack(fill=tk.X, pady=(0, 8))

        if HAS_BOOTSTRAP:
            self.progress = ttk.Progressbar(prog_frame, bootstyle="info-striped", length=600, mode="determinate")
        else:
            self.progress = ttk.Progressbar(prog_frame, length=600, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(0, 8))

        self.estado_var = tk.StringVar(value="Listo")
        ttk.Label(prog_frame, textvariable=self.estado_var, font=("Segoe UI", 10)).pack(anchor=tk.W)

        # --- Footer ---
        footer = ttk.Frame(main_frame)
        footer.pack(fill=tk.X)

        ffmpeg_text = "ffmpeg: OK" if self.ffmpeg_ok else "ffmpeg: NO ENCONTRADO"
        ffmpeg_color = "success" if self.ffmpeg_ok else "danger"
        if HAS_BOOTSTRAP:
            ttk.Label(footer, text=ffmpeg_text, bootstyle=ffmpeg_color, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        else:
            ttk.Label(footer, text=ffmpeg_text, font=("Segoe UI", 9)).pack(side=tk.LEFT)

        self.version_var = tk.StringVar(value=f"v{__version__}")
        ttk.Label(footer, textvariable=self.version_var, font=("Segoe UI", 9)).pack(side=tk.RIGHT)

        # Boton tema
        ttk.Button(footer, text="Tema", command=self._cambiar_tema, width=6).pack(side=tk.RIGHT, padx=(0, 8))

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
            self.calidad_combo["values"] = ("128", "192", "256", "320")
            if not self.calidad_var.get() or self.calidad_var.get() not in ("128", "192", "256", "320"):
                self.calidad_var.set("320")
        else:
            self.calidad_combo["values"] = ("360p", "480p", "720p", "1080p")
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
            clipboard = self.root.clipboard_get()
            if clipboard and YOUTUBE_REGEX.search(clipboard) and clipboard != self.url_var.get():
                self.url_var.set(clipboard)
        except tk.TclError:
            pass
        self.root.after(2000, self._monitorear_clipboard)

    def _preview_video(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Advertencia", "Ingresa una URL primero.")
            return

        self.preview_titulo.set("Cargando info del video...")
        self.preview_info.set("")
        self.preview_label.set("")

        def run():
            data = extraer_info_video(url)
            self.root.after(0, lambda: self._mostrar_preview(data))

        threading.Thread(target=run, daemon=True).start()

    def _mostrar_preview(self, data):
        if data:
            self.preview_data = data
            self.preview_titulo.set(data["titulo"])
            info_parts = [data["uploader"], data["duracion"]]
            if data.get("es_playlist"):
                info_parts.insert(0, f"Playlist: {data['num_videos']} videos")
            self.preview_info.set(" | ".join(info_parts))
            self.preview_label.set("")
        else:
            self.preview_titulo.set("")
            self.preview_info.set("")
            self.preview_label.set("No se pudo obtener info del video.")

    def _agregar_a_cola(self):
        url = self.url_var.get().strip()
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

        item_id = self.cola_tree.insert("", tk.END, values=("Pendiente", url[:60] + "...",
                                         "Audio" if modo == "audio" else "Video"))
        self.descarga_queue.put({
            "item_id": item_id,
            "url": url,
            "modo": modo,
            "calidad": calidad,
            "carpeta": carpeta,
            "subtitulos": subtitulos,
            "playlist": playlist,
        })

        self.url_var.set("")
        self.preview_titulo.set("")
        self.preview_info.set("")
        self.preview_label.set("")
        self._guardar_prefs_actuales()

    def _iniciar_cola(self):
        if self.is_downloading:
            return
        if self.descarga_queue.empty():
            messagebox.showinfo("Cola vacía", "Agrega videos a la cola primero.")
            return
        self.is_downloading = True
        threading.Thread(target=self._procesar_cola, daemon=True).start()

    def _procesar_cola(self):
        while not self.descarga_queue.empty():
            item = self.descarga_queue.get()
            item_id = item["item_id"]
            self.root.after(0, lambda i=item_id: self.cola_tree.set(i, "estado", "Descargando..."))
            self.root.after(0, lambda: self.progress.configure(value=0))

            def on_progress(val):
                self.root.after(0, lambda v=val: self.progress.configure(value=v * 100))

            def on_speed(speed, downloaded, total):
                if speed > 1024 * 1024:
                    speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                elif speed > 1024:
                    speed_str = f"{speed / 1024:.0f} KB/s"
                else:
                    speed_str = f"{speed:.0f} B/s"
                pct = (downloaded / total * 100) if total > 0 else 0
                self.root.after(0, lambda s=speed_str, p=pct: self.estado_var.set(f"Descargando... {s} — {p:.0f}%"))

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
                self.root.after(0, lambda i=item_id: self.cola_tree.set(i, "estado", "Completado"))
                self.historial.append({"url": item["url"], "fecha": time.strftime("%Y-%m-%d %H:%M")})
            else:
                self.root.after(0, lambda i=item_id, m=mensaje: self.cola_tree.set(i, "estado", f"Error"))
                self.root.after(0, lambda m=mensaje: messagebox.showerror("Error", m))

            self.root.after(0, lambda: self.progress.configure(value=100))
            self.root.after(0, lambda: self.estado_var.set("Listo"))

        self.is_downloading = False

    def _limpiar_cola(self):
        for item in self.cola_tree.get_children():
            estado = self.cola_tree.set(item, "estado")
            if estado in ("Completado", "Error"):
                self.cola_tree.delete(item)

    def _cambiar_tema(self):
        if not HAS_BOOTSTRAP:
            return
        temas = ["darkly", "cosmo", "flatly", "journal", "lumen", "minty",
                 "pulse", "sandstone", "united", "yeti", "morph", "simplex", "cerculean"]
        tema_actual = self.prefs.get("tema", "darkly")
        idx = (temas.index(tema_actual) + 1) % len(temas) if tema_actual in temas else 0
        nuevo_tema = temas[idx]
        self.root.style.theme_use(nuevo_tema)
        self.prefs["tema"] = nuevo_tema
        guardar_preferencias(self.prefs)

    def _check_update_async(self):
        def run():
            has_update, latest, url = check_for_update(__version__)
            if has_update:
                self.root.after(0, lambda: self._show_update(latest, url))
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
    root = tk.Tk()
    app = App(root)
    root.mainloop()
