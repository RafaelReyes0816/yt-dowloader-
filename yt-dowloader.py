#!/usr/bin/env python3
__version__ = "1.0.0"

import yt_dlp
import os
import sys
import threading
import urllib.request
import json
import tkinter as tk
from tkinter import messagebox

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    HAS_BOOTSTRAP = True
except ImportError:
    from tkinter import ttk
    HAS_BOOTSTRAP = False


GITHUB_REPO = "RafaelReyes0816/yt-dowloader-"


def descargar_musica(url, carpeta="Mi_musica", modo="audio", calidad="192", progress_callback=None):
    try:
        if not os.path.exists(carpeta):
            os.makedirs(carpeta)

        def progress_hook(d):
            if d["status"] == "downloading" and progress_callback:
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    progress_callback(downloaded / total)
            elif d["status"] == "finished" and progress_callback:
                progress_callback(1.0)

        if modo == "audio":
            opciones = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(carpeta, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": calidad,
                }],
                "postprocessor_args": ["-ar", "44100"],
                "prefer_ffmpeg": True,
                "progress_hooks": [progress_hook],
            }
        else:
            resoluciones = {
                "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/mp4",
                "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/mp4",
                "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/mp4",
                "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/mp4",
            }
            opciones = {
                "format": resoluciones.get(calidad, resoluciones["720p"]),
                "outtmpl": os.path.join(carpeta, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "merge_output_format": "mp4",
                "prefer_ffmpeg": True,
                "progress_hooks": [progress_hook],
            }

        with yt_dlp.YoutubeDL(opciones) as ydl:
            ydl.download([url])
        return True, f"{('Audio' if modo=='audio' else 'Video')} descargado correctamente"

    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if "private video" in msg or "unavailable" in msg:
            return False, "El video es privado o no está disponible."
        elif "geo" in msg or "not available in your country" in msg:
            return False, "El video no está disponible en tu región."
        elif "sign in" in msg or "login" in msg:
            return False, "El video requiere iniciar sesión en YouTube."
        elif "is not a valid url" in msg or "invalid url" in msg:
            return False, "La URL ingresada no es válida."
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
        self.root.geometry("700x700")
        self.root.minsize(700, 700)
        self.root.resizable(True, True)

        if HAS_BOOTSTRAP:
            self.root.style = ttk.Style("darkly")
        else:
            self.root.configure(bg="#181818")
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("TFrame", background="#232323")
            style.configure("TLabel", background="#232323", foreground="#fff", font=("Segoe UI", 12))
            style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), background="#232323", foreground="#fff")
            style.configure("TButton", font=("Segoe UI", 13, "bold"), padding=10)
            style.configure("Status.TLabel", font=("Segoe UI", 11), background="#232323", foreground="#1e90ff")
            style.configure("TRadiobutton", background="#232323", foreground="#fff", font=("Segoe UI", 12))
            style.configure("TCombobox", font=("Segoe UI", 14), padding=6)

        self._build_ui()
        self._check_update_async()

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=32)
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        title = ttk.Label(frame, text="YT Audio/Video Downloader", font=("Segoe UI", 20, "bold"))
        title.pack(pady=(0, 24))

        ttk.Label(frame, text="Pega la URL del video de YouTube:").pack(pady=(0, 12))

        self.url_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.url_var, font=("Segoe UI", 12), width=38)
        entry.pack(pady=(0, 16))
        entry.focus()

        self.modo_var = tk.StringVar(value="audio")
        radio_frame = ttk.Frame(frame)
        ttk.Radiobutton(radio_frame, text="Audio (mp3)", variable=self.modo_var, value="audio",
                         command=self._actualizar_calidades).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(radio_frame, text="Video (mp4)", variable=self.modo_var, value="video",
                         command=self._actualizar_calidades).pack(side=tk.LEFT, padx=10)
        radio_frame.pack(pady=(0, 16))

        ttk.Label(frame, text="Calidad:").pack(pady=(0, 6))
        self.calidad_var = tk.StringVar()
        self.calidad_combo = ttk.Combobox(frame, textvariable=self.calidad_var, font=("Segoe UI", 14),
                                           width=12, state="readonly")
        self.calidad_combo.pack(pady=(0, 16))
        self._actualizar_calidades()

        self.btn_descargar = ttk.Button(frame, text="Descargar", command=self._descargar)
        self.btn_descargar.pack(pady=(0, 12))

        if HAS_BOOTSTRAP:
            self.progress = ttk.Progressbar(frame, bootstyle="info-striped", length=400, mode="determinate")
        else:
            self.progress = ttk.Progressbar(frame, length=400, mode="determinate")
        self.progress.pack(pady=(0, 12))

        self.estado_var = tk.StringVar()
        self.estado = ttk.Label(frame, textvariable=self.estado_var)
        self.estado.pack()

        self.version_var = tk.StringVar(value=f"v{__version__}")
        ttk.Label(frame, textvariable=self.version_var, font=("Segoe UI", 9)).pack(pady=(12, 0))

    def _actualizar_calidades(self):
        if self.modo_var.get() == "audio":
            self.calidad_combo["values"] = ("128", "192", "256", "320")
            self.calidad_var.set("320")
        else:
            self.calidad_combo["values"] = ("360p", "480p", "720p", "1080p")
            self.calidad_var.set("1080p")

    def _on_progress(self, value):
        self.progress["value"] = value * 100
        self.root.update_idletasks()

    def _descargar(self):
        url = self.url_var.get()
        modo = self.modo_var.get()
        calidad = self.calidad_var.get()

        if not url.strip():
            messagebox.showwarning("Advertencia", "Por favor ingresa una URL.")
            return

        self.btn_descargar.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self.estado_var.set(f"Descargando {'audio' if modo == 'audio' else 'video'}...")
        self.root.update()

        def run():
            exito, mensaje = descargar_musica(url, modo=modo, calidad=calidad,
                                               progress_callback=self._on_progress)
            self.root.after(0, lambda: self._resultado(exito, mensaje))

        threading.Thread(target=run, daemon=True).start()

    def _resultado(self, exito, mensaje):
        self.btn_descargar.config(state=tk.NORMAL)
        if exito:
            self.progress["value"] = 100
            self.estado_var.set(mensaje)
            messagebox.showinfo("Éxito", mensaje)
        else:
            self.progress["value"] = 0
            self.estado_var.set(mensaje)
            messagebox.showerror("Error", mensaje)

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
