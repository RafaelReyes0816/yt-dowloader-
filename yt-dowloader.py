#!/usr/bin/env python3
__version__ = "3.0.0"

import os
import re
import subprocess
import sys
import time
import threading
import tkinter

import customtkinter as ctk
import yt_dlp

from tkinter import filedialog, messagebox

from core import (
    GITHUB_REPO,
    PLATFORM_REGEX,
    TIPOS_BLOQUEANTES,
    TIPOS_REINTENTO_SESION,
    find_ffmpeg,
    detectar_plataforma,
    detectar_navegadores,
    ClasificadorErrores,
    cargar_preferencias,
    guardar_preferencias,
    verificar_url,
    descargar_musica,
    check_for_update,
    obtener_ultima_version_ytdlp,
    comparar_versiones,
    elegir_navegador_sesion,
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

        self.cancel_btn = ctk.CTkButton(
            self, text="Cancelar", command=self._cancelar,
            font=FONTS["small"], width=70, height=28,
            fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
            border_color=COLORS["border.subtle"], border_width=1,
            text_color=COLORS["text.secondary"],
        )
        self.cancel_btn.grid(row=0, column=4, rowspan=2, padx=(0, 12), pady=10)

        self.on_cancel = None

    def _cancelar(self):
        if self.on_cancel:
            self.on_cancel()

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
            self.after(0, lambda: self.status_label.configure(text="Error"))

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
        self._hist_lock = threading.Lock()
        self.is_downloading = False
        self.stop_all = threading.Event()
        self.clipboard_auto = self.prefs.get("clipboard_auto", True)
        self.ffmpeg_ok = find_ffmpeg() is not None
        self.navegadores = detectar_navegadores()
        self.queue_items = []
        self.ydl_holders = {}

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
                                       placeholder_text="Pega la URL del video (YouTube, Instagram, TikTok, Facebook, Twitch, Vimeo, X, Reddit)...",
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

        ctk.CTkLabel(row_toggles, text="En paralelo:", font=FONTS["small"],
                     text_color=COLORS["text.secondary"]).pack(side="left", padx=(12, 6))
        self.paralelas_var = ctk.StringVar(value=str(self.prefs.get("max_paralelas", 1)))
        self.paralelas_option = ctk.CTkOptionMenu(row_toggles, variable=self.paralelas_var,
                                                  values=["1", "2", "3"],
                                                  font=FONTS["small"],
                                                  fg_color=COLORS["bg.base"],
                                                  button_color=COLORS["border.subtle"],
                                                  button_hover_color=COLORS["bg.surface-hover"],
                                                  dropdown_fg_color=COLORS["bg.surface"],
                                                  dropdown_hover_color=COLORS["bg.surface-hover"],
                                                  width=60, height=32)
        self.paralelas_option.pack(side="left")

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
        ctk.CTkButton(btn_row, text="Detener todo", command=self._detener_todo,
                      font=FONTS["body"], height=36,
                      fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
                      border_color=COLORS["accent.error"], border_width=1,
                      text_color=COLORS["accent.error"]).pack(side="left", padx=(0, 8))
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
        self.paralelas_var.set(str(self.prefs.get("max_paralelas", 1)))
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
            "max_paralelas": int(self.paralelas_var.get()) if self.paralelas_var.get().isdigit() else 1,
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
        return elegir_navegador_sesion(self.prefs.get("navegador", ""))

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
                                    "Plataformas: YouTube, Instagram, TikTok, Facebook, Twitch, Vimeo, X, Reddit.")
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

        item = {
            "card": card,
            "url": url,
            "plataforma": plataforma,
            "modo": modo,
            "calidad": calidad,
            "carpeta": carpeta,
            "subtitulos": subtitulos,
            "playlist": playlist,
            "navegador": navegador,
            "cancel_flag": threading.Event(),
            "ydl_holder": {},
            "who_removed": None,
        }
        card.on_cancel = lambda i=item: self._cancelar_item(i)
        self.queue_items.append(item)

        self.url_entry.delete(0, "end")
        self._toggle_empty_state()
        self._actualizar_counter()
        self._guardar_prefs_actuales()

    def _cancelar_item(self, item):
        item["cancel_flag"].set()
        ydl = item["ydl_holder"].get("ydl")
        if ydl is not None:
            try:
                if hasattr(ydl, "params"):
                    ydl.params["noprogress"] = True
            except Exception:
                pass

    def _detener_todo(self):
        self.stop_all.set()
        for item in self.queue_items:
            item["cancel_flag"].set()
            ydl = item["ydl_holder"].get("ydl")
            if ydl is not None:
                try:
                    if hasattr(ydl, "params"):
                        ydl.params["noprogress"] = True
                except Exception:
                    pass

    def _iniciar_cola(self):
        if self.is_downloading:
            return

        pending = [item for item in self.queue_items if item["card"].status_label.cget("text") == "Pendiente"]
        if not pending:
            messagebox.showinfo("Cola vacia", "Agrega videos a la cola primero.")
            return

        self.stop_all.clear()
        nav_sesion = self._navegador_seleccionado()
        self.is_downloading = True
        threading.Thread(target=self._procesar_cola, args=(pending, nav_sesion), daemon=True).start()

    def _procesar_cola(self, pending, navegador_actual):
        total = len(pending)
        max_paralelas = int(self.prefs.get("max_paralelas", 1) or 1)
        max_paralelas = max(1, min(max_paralelas, 3))

        if max_paralelas <= 1:
            for idx, item in enumerate(pending):
                if self.stop_all.is_set():
                    break
                self._procesar_item(item, idx, total, navegador_actual)
            self.is_downloading = False
            self.stop_all.clear()
            self.after(0, lambda: self.estado_var.set("Listo"))
            self.after(0, self._actualizar_counter)
            return

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_paralelas) as pool:
            futures = {}
            for idx, item in enumerate(pending):
                if self.stop_all.is_set():
                    break
                futures[pool.submit(self._procesar_item, item, idx, total, navegador_actual)] = idx
            for fut in futures:
                try:
                    fut.result()
                except Exception:
                    pass

        self.is_downloading = False
        self.stop_all.clear()
        self.after(0, lambda: self.estado_var.set("Listo"))
        self.after(0, self._actualizar_counter)

    def _procesar_item(self, item, idx, total, navegador_actual):
        if item["card"].status_label.cget("text") != "Pendiente":
            return
        if item["cancel_flag"].is_set():
            return

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
            return

        if self.stop_all.is_set() or item["cancel_flag"].is_set():
            return

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
            cancel_flag=item["cancel_flag"],
            ydl_holder=item["ydl_holder"],
        )

        if exito is False and tipo_fallo == "cancelada":
            self.after(0, lambda i=item: i["card"].set_status("Cancelada", COLORS["text.secondary"]))
            self.after(0, lambda i=item: i["card"].canvas.delete("all"))
            self.after(0, self._actualizar_counter)
            return

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
                    cancel_flag=item["cancel_flag"],
                    ydl_holder=item["ydl_holder"],
                )
                if exito is False and tipo_fallo == "cancelada":
                    self.after(0, lambda i=item: i["card"].set_status("Cancelada", COLORS["text.secondary"]))
                    self.after(0, lambda i=item: i["card"].canvas.delete("all"))
                    self.after(0, self._actualizar_counter)
                    return

        if exito:
            self.after(0, lambda i=item: i["card"].set_status("Completado", COLORS["accent.success"]))
            with self._hist_lock:
                self.historial.append({"url": item["url"], "fecha": time.strftime("%Y-%m-%d %H:%M")})
        else:
            self.after(0, lambda i=item: i["card"].set_status("Error", COLORS["accent.error"]))
            self.after(0, lambda i=item: i["card"].set_error_color())
            self.after(0, lambda m=mensaje: messagebox.showerror("No se pudo descargar", m))

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
