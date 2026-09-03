#!/usr/bin/env python3
__version__ = "3.1.0"

import os
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
    cargar_preferencias,
    guardar_preferencias,
    verificar_url,
    descargar_musica,
    check_for_update,
    obtener_ultima_version_ytdlp,
    comparar_versiones,
    elegir_navegador_sesion,
)

from theme import (
    COLORS,
    FONTS,
    SPACING,
    RADII,
    PLATAFORMA_BADGE,
    PLATAFORMA_INICIAL,
)

ESTADOS = {
    "en_cola":      ("En cola",         COLORS["text.secondary"]),
    "verificando":  ("Verificando...",  COLORS["accent.progress"]),
    "descargando":  ("Descargando",     COLORS["accent.progress"]),
    "convirtiendo": ("Convirtiendo...", COLORS["accent.progress"]),
    "listo":        ("Listo",           COLORS["accent.success"]),
    "error":        ("Error",           COLORS["accent.error"]),
    "cancelado":    ("Cancelado",       COLORS["text.secondary"]),
}

ACCION_BOTON = {
    "en_cola": "Cancelar",
    "verificando": "Cancelar",
    "descargando": "Cancelar",
    "convirtiendo": "Cancelar",
    "error": "Reintentar",
    "cancelado": "Reintentar",
    "listo": "Restaurar",
}


class SegmentedControl(ctk.CTkFrame):
    def __init__(self, master, options, variable, command=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.options = options
        self.variable = variable
        self.command = command
        self.buttons = []
        self._build()
        self.variable.trace_add("write", lambda *_: self._update_style())

    def _build(self):
        for i, option in enumerate(self.options):
            btn = ctk.CTkButton(
                self,
                text=option,
                font=FONTS["small"],
                corner_radius=RADII["input"],
                height=32,
                command=lambda o=option: self._select(o),
            )
            btn.pack(side="left", padx=(0, SPACING["xs"]))
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
                         corner_radius=RADII["pill"], command=self._toggle, **kwargs)
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
    def __init__(self, master, url, plataforma, modo, on_cancel=None, on_retry=None,
                 on_remove=None, **kwargs):
        super().__init__(master, fg_color=COLORS["bg.surface"], corner_radius=RADII["card"],
                         height=76, **kwargs)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)
        self.url = url
        self.plataforma = plataforma
        self.modo = modo
        self.estado = "en_cola"
        self.progress_value = 0
        self.on_cancel = on_cancel
        self.on_retry = on_retry
        self.on_remove = on_remove

        self.canvas = tkinter.Canvas(self, width=44, height=44,
                                     bg=COLORS["bg.surface"], highlightthickness=0)
        self.canvas.grid(row=0, column=0, rowspan=3, padx=(12, 8), pady=12)
        self._draw_ring(0)

        badge_color = PLATAFORMA_BADGE.get(plataforma, PLATAFORMA_BADGE["Otra"])
        self.badge = ctk.CTkLabel(self, text=PLATAFORMA_INICIAL.get(plataforma, "??"),
                                  font=FONTS["tag"], text_color="#0B0F1A", width=26, height=20,
                                  corner_radius=6, fg_color=badge_color)
        self.badge.grid(row=0, column=0, sticky="ne", padx=(46, 0), pady=(8, 0))

        self.title_label = ctk.CTkLabel(self, text=self._truncate(url),
                                        font=FONTS["body_bold"], text_color=COLORS["text.primary"],
                                        anchor="w")
        self.title_label.grid(row=0, column=1, sticky="sw", padx=(0, 8), pady=(10, 0))

        self.url_label = ctk.CTkLabel(self, text=self._truncate_url(url), font=FONTS["mono_small"],
                                      text_color=COLORS["text.secondary"], anchor="w")
        self.url_label.grid(row=1, column=1, sticky="nw", padx=(0, 8), pady=(0, 2))

        self.micro_bar = ctk.CTkProgressBar(self, height=2, corner_radius=1,
                                            progress_color=COLORS["accent.progress"],
                                            fg_color=COLORS["border.subtle"])
        self.micro_bar.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(2, 10))
        self.micro_bar.set(0)

        self.metrica_label = ctk.CTkLabel(self, text="", font=FONTS["mono_small"],
                                          text_color=COLORS["text.secondary"], width=130, anchor="e")
        self.metrica_label.grid(row=0, column=2, rowspan=2, padx=(0, 8), pady=10)

        self.status_label = ctk.CTkLabel(self, text=ESTADOS["en_cola"][0], font=FONTS["small_bold"],
                                         text_color=ESTADOS["en_cola"][1], width=110, anchor="e")
        self.status_label.grid(row=0, column=3, rowspan=2, padx=(0, 8), pady=10)

        self.action_btn = ctk.CTkButton(
            self, text="Cancelar", command=self._accion,
            font=FONTS["small"], width=84, height=30,
            fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
            border_color=COLORS["border.subtle"], border_width=1,
            text_color=COLORS["text.secondary"],
        )
        self.action_btn.grid(row=0, column=4, rowspan=2, padx=(0, 6), pady=10)

        self.remove_btn = ctk.CTkButton(
            self, text="x", command=lambda: self.on_remove() if self.on_remove else None,
            font=FONTS["small_bold"], width=24, height=24, corner_radius=6,
            fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
            text_color=COLORS["text.secondary"],
        )
        self.remove_btn.grid(row=0, column=5, rowspan=2, padx=(0, 10), pady=10)

        self._aplicar_estado("en_cola")

    def _accion(self):
        if self.estado in ("error", "cancelado"):
            if self.on_retry:
                self.on_retry()
        elif self.estado == "listo":
            if self.on_retry:
                self.on_retry()
        else:
            if self.on_cancel:
                self.on_cancel()

    def _truncate_url(self, url):
        return url if len(url) <= 48 else url[:45] + "..."

    def _truncate(self, texto):
        if not texto:
            return ""
        return texto if len(texto) <= 52 else texto[:49] + "..."

    def set_titulo(self, titulo):
        def _f():
            if not self.winfo_exists():
                return
            self.title_label.configure(text=self._truncate(titulo))
        self.after(0, _f)

    def _draw_ring(self, pct, color=None):
        if not self.winfo_exists():
            return
        self.canvas.delete("all")
        cx, cy, r = 22, 22, 17
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                outline=COLORS["border.subtle"], width=3)
        if pct > 0:
            extent = max(1, int(pct * 360))
            self.canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                   start=90, extent=-extent,
                                   outline=color or COLORS["accent.progress"], width=3, style="arc")
        self.canvas.create_text(cx, cy, text=f"{int(pct * 100)}%",
                                fill=COLORS["text.primary"], font=FONTS["small"])

    def _draw_error_icon(self):
        if not self.winfo_exists():
            return
        self.canvas.delete("all")
        cx, cy = 22, 22
        self.canvas.create_text(cx, cy, text="!",
                                fill=COLORS["accent.error"], font=FONTS["body_bold"])

    def update_progress(self, pct):
        self.progress_value = pct

        def _f():
            if not self.winfo_exists():
                return
            self.micro_bar.set(pct)
            self._draw_ring(pct)
        self.after(0, _f)

    def set_metricas(self, speed_str=None, eta_str=None):
        def _f():
            if not self.winfo_exists():
                return
            partes = []
            if speed_str:
                partes.append(speed_str)
            if eta_str:
                partes.append("ETA " + eta_str)
            self.metrica_label.configure(text=" · ".join(partes))
        self.after(0, _f)

    def set_error_detalle(self, mensaje):
        if not mensaje:
            return
        linea = next((l for l in mensaje.splitlines() if l.strip()), "").strip()
        if not linea:
            linea = "Error al descargar"

        def _f():
            if not self.winfo_exists():
                return
            self.metrica_label.configure(text=linea[:28])
        self.after(0, _f)

    def _aplicar_estado(self, estado):
        self.estado = estado
        texto, color = ESTADOS.get(estado, ESTADOS["en_cola"])

        def _f():
            if not self.winfo_exists():
                return
            self.status_label.configure(text=texto, text_color=color)
            if estado == "listo":
                self._draw_ring(1.0, COLORS["accent.success"])
                self.micro_bar.set(1.0)
                self.configure(border_width=2, border_color=COLORS["accent.success"])
            elif estado == "error":
                self._draw_error_icon()
                self.configure(border_width=2, border_color=COLORS["accent.error"])
            elif estado == "cancelado":
                self._draw_ring(self.progress_value, COLORS["border.subtle"])
                self.configure(border_width=0)
            else:
                self._draw_ring(self.progress_value)
                self.configure(border_width=0)
            self.action_btn.configure(text=ACCION_BOTON.get(estado, "Cancelar"))
        self.after(0, _f)

    def set_estado(self, estado):
        self._aplicar_estado(estado)


class VentanaDiagnostico(ctk.CTkToplevel):
    def __init__(self, master, url="", navegador=""):
        super().__init__(master)
        self.title("Diagnóstico")
        self.geometry("560x520")
        self.minsize(480, 420)
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        self.url = url.strip()
        self.navegador = navegador
        self.checks = {}
        self._build_ui()
        self.after(100, lambda: threading.Thread(target=self._run_checks, daemon=True).start())

    def _build_ui(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=RADII["card"])
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(frame, text="Diagnóstico", font=FONTS["display"],
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

        detalle_scroll = ctk.CTkScrollableFrame(frame, fg_color=COLORS["bg.base"],
                                                corner_radius=8, height=150)
        detalle_scroll.pack(fill="x", padx=15, pady=(10, 4))
        self.detail_label = ctk.CTkLabel(detalle_scroll, text="", font=FONTS["mono_small"],
                                         text_color=COLORS["text.secondary"], justify="left",
                                         anchor="w", wraplength=500)
        self.detail_label.pack(anchor="w", padx=8, pady=8)

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
                texto += "\n\nDetalle técnico:\n" + detalle
            self.after(0, lambda t=texto: self.detail_label.configure(text=t))
        elif resultado.get("info"):
            self._set("acceso", "OK · acceso público", COLORS["accent.success"])
        else:
            self._set("acceso", "Sin datos", COLORS["text.secondary"])

    def _actualizar_motor(self):
        if getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Actualizar motor yt-dlp",
                "Esta versión empaquetada usa yt-dlp fijo.\n\n"
                "Descarga la última versión de la aplicación desde GitHub Releases.",
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
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default,curl-cffi]"],
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
                f"yt-dlp se actualizó a la v{v}.\n\nReinicia la aplicación para aplicar los cambios.",
            ))
        else:
            self._set("ytdlp", "ERROR · falló la actualización", COLORS["accent.error"])
            detalle = (proc.stderr or proc.stdout or "").strip()[-400:]
            self.after(0, lambda d=detalle: messagebox.showerror(
                "No se pudo actualizar",
                f"Falló pip upgrade.\n\nDetalle técnico:\n{d}",
            ))
        self.after(0, lambda: self.btn_actualizar_ytdlp.configure(state="normal"))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YT-DownLoader del Jaeger")
        self.geometry("980x720")
        self.minsize(880, 620)
        self.resizable(True, True)
        self.configure(fg_color=COLORS["bg.base"])

        self._set_window_icon()

        ctk.set_appearance_mode("dark")

        self.prefs = cargar_preferencias()
        self.historial = self.prefs.get("historial", [])
        self._hist_lock = threading.Lock()
        self.is_downloading = False
        self.stop_all = threading.Event()
        self.clipboard_auto = self.prefs.get("clipboard_auto", True)
        self.ffmpeg_ok = find_ffmpeg() is not None
        self.navegadores = detectar_navegadores()
        self.queue_items = []

        self._build_ui()
        self._aplicar_preferencias()
        self.protocol("WM_DELETE_WINDOW", self._on_cerrar)
        self._check_update_async()
        if self.clipboard_auto:
            self._monitorear_clipboard()

    def _on_cerrar(self):
        self._guardar_prefs_actuales()
        self.destroy()

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

        self._build_header()
        self._build_input()
        self._build_options()
        self._build_cola()
        self._build_statusbar()

    # ---------- Header ----------
    def _build_header(self):
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

        ffmpeg_bg = COLORS["bg.base"] if self.ffmpeg_ok else COLORS["accent.error"]
        ffmpeg_text = COLORS["accent.success"] if self.ffmpeg_ok else COLORS["text.primary"]
        ffmpeg_label = "ffmpeg OK" if self.ffmpeg_ok else "ffmpeg no encontrado"

        ffmpeg_badge = ctk.CTkFrame(header_right, fg_color=ffmpeg_bg, corner_radius=999, height=28,
                                    border_width=1, border_color=ffmpeg_text)
        ffmpeg_badge.pack(side="right", padx=(8, 0))
        ctk.CTkLabel(ffmpeg_badge, text=f"  ◦ {ffmpeg_label}  ",
                     font=FONTS["small"], text_color=ffmpeg_text).pack(padx=4, pady=2)

        ctk.CTkLabel(header_right, text=f"v{__version__}",
                     font=FONTS["small"], text_color=COLORS["text.secondary"]).pack(side="right", padx=(0, 8))

    # ---------- Input ----------
    def _build_input(self):
        url_frame = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=RADII["card"])
        url_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(15, 10))
        url_frame.grid_columnconfigure(0, weight=1)

        url_row = ctk.CTkFrame(url_frame, fg_color="transparent")
        url_row.grid(row=0, column=0, sticky="ew", padx=15, pady=12)
        url_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(url_row, text="🔗", font=FONTS["body"], text_color=COLORS["text.secondary"]
                     ).grid(row=0, column=0, padx=(0, 8))

        self.url_entry = ctk.CTkEntry(url_row,
                                      placeholder_text="Pega la URL del video (YouTube, Instagram, TikTok, Facebook, Twitch, Vimeo, X, Reddit)...",
                                      font=FONTS["mono"], height=40,
                                      fg_color=COLORS["bg.base"],
                                      border_color=COLORS["border.subtle"],
                                      text_color=COLORS["text.primary"],
                                      placeholder_text_color=COLORS["text.secondary"])
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.url_entry.focus()

        ctk.CTkButton(url_row, text="Agregar", command=self._agregar_a_cola, width=90, height=40,
                      font=FONTS["body_bold"],
                      fg_color=COLORS["accent.brand"], hover_color=COLORS["accent.brand-hover"],
                      text_color=COLORS["text.primary"]).grid(row=0, column=2)

    # ---------- Options ----------
    def _build_options(self):
        opt_frame = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=RADII["card"])
        opt_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        opt_frame.grid_columnconfigure(0, weight=1)

        row1 = ctk.CTkFrame(opt_frame, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 8))

        self.modo_var = ctk.StringVar()
        self.modo_control = SegmentedControl(row1, ["Audio (mp3)", "Video (mp4)"],
                                             self.modo_var, command=self._actualizar_calidades)
        self.modo_control.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row1, text="Calidad:", font=FONTS["small"],
                     text_color=COLORS["text.secondary"]).pack(side="left", padx=(0, 6))
        self.calidad_var = ctk.StringVar()
        self.calidad_option = self._crear_dropdown(row1, self.calidad_var,
                                                   ["128", "192", "256", "320"], width=100)
        self.calidad_option.pack(side="left")

        row_toggles = ctk.CTkFrame(opt_frame, fg_color="transparent")
        row_toggles.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 12))

        self.subtitulos_var = ctk.BooleanVar(value=self.prefs.get("subtitulos", False))
        PillToggle(row_toggles, "Subtítulos", self.subtitulos_var,
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
        self.paralelas_option = self._crear_dropdown(row_toggles, self.paralelas_var,
                                                     ["1", "2", "3"], width=60)
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
        row3.grid_columnconfigure(1, weight=1)

        self.usar_sesion_var = ctk.BooleanVar(value=self.prefs.get("usar_sesion_navegador", False))
        PillToggle(row3, "Usar sesión del navegador", self.usar_sesion_var,
                   command=self._actualizar_estado_navegador,
                   fg_color=COLORS["bg.surface"], text_color=COLORS["text.secondary"],
                   hover_color=COLORS["bg.surface-hover"]).grid(row=0, column=0, sticky="w", padx=(0, 8))

        ctk.CTkLabel(row3, text="Navegador:", font=FONTS["small"],
                     text_color=COLORS["text.secondary"]).grid(row=0, column=1, sticky="w", padx=(0, 6))

        pref_nav = self.prefs.get("navegador", "")
        nav_inicial = pref_nav.capitalize() if pref_nav in self.navegadores else (self.navegadores[0].capitalize() if self.navegadores else "Sin detectar")
        self.navegador_var = ctk.StringVar(value=nav_inicial)
        self.navegador_option = self._crear_dropdown(row3, self.navegador_var,
                                                     [n.capitalize() for n in self.navegadores] or ["Sin detectar"],
                                                     width=120)
        self.navegador_option.grid(row=0, column=2, sticky="w")

        for var in (self.modo_var, self.calidad_var, self.carpeta_var, self.paralelas_var,
                    self.subtitulos_var, self.playlist_var, self.clipboard_var,
                    self.usar_sesion_var, self.navegador_var):
            var.trace_add("write", lambda *_: self._programar_guardado())

        self.modo_var.trace_add("write", lambda *_: self._actualizar_calidades())

    def _crear_dropdown(self, master, variable, values, width):
        return ctk.CTkOptionMenu(master, variable=variable, values=values,
                                 font=FONTS["small"],
                                 fg_color=COLORS["bg.base"],
                                 button_color=COLORS["border.subtle"],
                                 button_hover_color=COLORS["bg.surface-hover"],
                                 dropdown_fg_color=COLORS["bg.surface"],
                                 dropdown_hover_color=COLORS["bg.surface-hover"],
                                 width=width, height=32)

    def _programar_guardado(self):
        self.after(400, self._guardar_prefs_actuales)

    # ---------- Cola ----------
    def _build_cola(self):
        cola_frame = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=RADII["card"])
        cola_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 10))
        cola_frame.grid_columnconfigure(0, weight=1)
        cola_frame.grid_rowconfigure(1, weight=1)

        cola_header = ctk.CTkFrame(cola_frame, fg_color="transparent")
        cola_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))
        cola_header.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(cola_header, text="Cola de Descargas", font=FONTS["body_bold"],
                     text_color=COLORS["text.primary"]).grid(row=0, column=0, sticky="w")

        self.cola_counter = ctk.CTkLabel(cola_header, text="0 ítems", font=FONTS["small"],
                                         text_color=COLORS["text.secondary"])
        self.cola_counter.grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.actividad_btn = ctk.CTkButton(cola_header, text="Actividad", width=80, height=26,
                                           font=FONTS["small"],
                                           fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
                                           border_color=COLORS["border.subtle"], border_width=1,
                                           text_color=COLORS["text.secondary"],
                                           command=self._toggle_actividad)
        self.actividad_btn.grid(row=0, column=2, sticky="e")

        self.cola_scroll = ctk.CTkScrollableFrame(cola_frame, fg_color=COLORS["bg.base"],
                                                  corner_radius=8,
                                                  scrollbar_fg_color=COLORS["border.subtle"],
                                                  scrollbar_button_color=COLORS["border.subtle"],
                                                  scrollbar_button_hover_color=COLORS["bg.surface-hover"])
        self.cola_scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))
        self.cola_scroll.grid_columnconfigure(0, weight=1)

        self.actividad_frame = ctk.CTkFrame(cola_frame, fg_color=COLORS["bg.base"], corner_radius=8,
                                            height=140)
        self.actividad_log = ctk.CTkScrollableFrame(self.actividad_frame, fg_color="transparent",
                                                    height=120)

        self._toggle_empty_state()

        btn_row = ctk.CTkFrame(cola_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

        self.btn_iniciar = ctk.CTkButton(btn_row, text="Iniciar descargas", command=self._iniciar_cola,
                                         font=FONTS["body_bold"], height=36,
                                         fg_color=COLORS["accent.brand"], hover_color=COLORS["accent.brand-hover"],
                                         text_color=COLORS["text.primary"])
        self.btn_iniciar.pack(side="left", padx=(0, 8))

        self.btn_detener = ctk.CTkButton(btn_row, text="Detener todo", command=self._detener_todo,
                                         font=FONTS["body"], height=36,
                                         fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
                                         border_color=COLORS["accent.error"], border_width=1,
                                         text_color=COLORS["accent.error"])
        self.btn_detener.pack(side="left", padx=(0, 8))
        self.btn_detener.configure(state="disabled")

        ctk.CTkButton(btn_row, text="Limpiar cola", command=self._limpiar_cola,
                      font=FONTS["body"], height=36,
                      fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
                      border_color=COLORS["border.subtle"], border_width=1,
                      text_color=COLORS["text.secondary"]).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Diagnóstico", command=self._abrir_diagnostico,
                      font=FONTS["body"], height=36,
                      fg_color="transparent", hover_color=COLORS["bg.surface-hover"],
                      border_color=COLORS["border.subtle"], border_width=1,
                      text_color=COLORS["text.secondary"]).pack(side="left", padx=(8, 0))

    def _toggle_actividad(self):
        if self.actividad_frame.winfo_manager():
            self.actividad_frame.grid_forget()
            self.actividad_btn.configure(text="Actividad")
        else:
            self.actividad_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 6))
            self.actividad_log.pack(fill="both", expand=True, padx=8, pady=8)
            self.actividad_btn.configure(text="Actividad ▾")

    def _toggle_empty_state(self):
        if hasattr(self, "empty_state_frame"):
            self.empty_state_frame.destroy()

        if self.queue_items:
            return

        self.empty_state_frame = ctk.CTkFrame(self.cola_scroll, fg_color="transparent")
        self.empty_state_frame.grid(row=0, column=0, sticky="nsew", pady=60)
        self.empty_state_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.empty_state_frame, text="◦", font=(FONTS["display"][0], 40),
                     text_color=COLORS["border.subtle"]).grid(row=0, column=0)
        ctk.CTkLabel(self.empty_state_frame, text="Pega una URL arriba para empezar",
                     font=FONTS["body"], text_color=COLORS["text.secondary"]).grid(row=1, column=0, pady=(8, 0))

    # ---------- Status bar ----------
    def _build_statusbar(self):
        status_bar = ctk.CTkFrame(self, fg_color=COLORS["bg.surface"], corner_radius=0, height=38)
        status_bar.grid(row=4, column=0, sticky="ew", padx=0, pady=0)
        status_bar.grid_columnconfigure(1, weight=1)

        self.estado_var = ctk.StringVar(value="Listo")
        ctk.CTkLabel(status_bar, textvariable=self.estado_var, font=FONTS["small"],
                     text_color=COLORS["text.secondary"]).grid(row=0, column=0, sticky="w", padx=20, pady=9)

        self.status_counter = ctk.CTkLabel(status_bar, text="", font=FONTS["small"],
                                           text_color=COLORS["text.secondary"])
        self.status_counter.grid(row=0, column=1, sticky="e", padx=20, pady=9)

    # ---------- Prefs ----------
    def _aplicar_preferencias(self):
        modo_pref = str(self.prefs.get("modo", "audio")).lower()
        es_audio = modo_pref.startswith("audio")
        self.modo_var.set("Audio (mp3)" if es_audio else "Video (mp4)")
        self.calidad_var.set(self.prefs.get("calidad", "320"))
        self.carpeta_var.set(self.prefs.get("carpeta", os.path.join(os.path.expanduser("~"), "Downloads", "Mi_musica")))
        self.usar_sesion_var.set(self.prefs.get("usar_sesion_navegador", False))
        self.subtitulos_var.set(self.prefs.get("subtitulos", False))
        self.playlist_var.set(self.prefs.get("playlist", False))
        self.paralelas_var.set(str(self.prefs.get("max_paralelas", 1)))
        self._actualizar_calidades()
        self._actualizar_estado_navegador()

    def _guardar_prefs_actuales(self):
        self.prefs.update({
            "modo": "audio" if self.modo_var.get().startswith("Audio") else "video",
            "calidad": self.calidad_var.get(),
            "carpeta": self.carpeta_var.get(),
            "subtitulos": self.subtitulos_var.get(),
            "playlist": self.playlist_var.get(),
            "clipboard_auto": self.clipboard_var.get(),
            "usar_sesion_navegador": self.usar_sesion_var.get(),
            "navegador": self._navegador_seleccionado(),
            "max_paralelas": int(self.paralelas_var.get()) if self.paralelas_var.get().isdigit() else 1,
            "historial": self.historial[-100:],
        })
        guardar_preferencias(self.prefs)

    def _navegador_seleccionado(self):
        if not self.usar_sesion_var.get() or not self.navegadores:
            return ""
        valor = self.navegador_var.get().lower()
        return valor if valor in self.navegadores else ""

    def _actualizar_estado_navegador(self):
        activo = self.usar_sesion_var.get()
        if not activo and self.navegador_var.get() == "Sin detectar":
            pass
        state = "normal" if (activo and self.navegadores) else "disabled"
        self.navegador_option.configure(state=state)
        if activo and not self.navegadores:
            self._log("No se detectaron navegadores; la sesión no estará activa.")

    def _elegir_navegador_sesion(self):
        return elegir_navegador_sesion(self.prefs.get("navegador", ""))

    def _actualizar_calidades(self):
        if self.modo_var.get().startswith("Audio"):
            valores = ["128", "192", "256", "320"]
            self.calidad_option.configure(values=valores)
            if self.calidad_var.get() not in valores:
                self.calidad_var.set("320")
        else:
            valores = ["360p", "480p", "720p", "1080p", "1440p", "2160p"]
            self.calidad_option.configure(values=valores)
            if self.calidad_var.get() not in valores:
                self.calidad_var.set("720p")

    def _seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if carpeta:
            self.carpeta_var.set(carpeta)

    # ---------- Clipboard ----------
    def _toggle_clipboard(self):
        self.clipboard_auto = self.clipboard_var.get()
        if self.clipboard_auto:
            self._monitorear_clipboard()

    def _monitorear_clipboard(self):
        if not self.clipboard_auto:
            return
        try:
            clipboard = self.clipboard_get()
            match = PLATFORM_REGEX.search(clipboard) if clipboard else None
            if match and clipboard != self.url_entry.get():
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, match.group(0))
        except Exception:
            pass
        self.after(2000, self._monitorear_clipboard)

    # ---------- Counter / Consola ----------
    def _actualizar_counter(self):
        total = len(self.queue_items)
        counts = {e: 0 for e in ESTADOS}
        for item in self.queue_items:
            counts[item["estado"]] = counts.get(item["estado"], 0) + 1

        self.cola_counter.configure(text=f"{total} ítems")

        parts = []
        if counts["descargando"] > 0:
            parts.append(f"{counts['descargando']} activa{'s' if counts['descargando'] > 1 else ''}")
        if counts["convirtiendo"] > 0:
            parts.append(f"{counts['convirtiendo']} convirtiendo")
        if counts["verificando"] > 0:
            parts.append(f"{counts['verificando']} verificando")
        if counts["en_cola"] > 0:
            parts.append(f"{counts['en_cola']} en cola")
        if counts["listo"] > 0:
            parts.append(f"{counts['listo']} lista{'s' if counts['listo'] > 1 else ''}")
        if counts["error"] > 0:
            parts.append(f"{counts['error']} error")
        if counts["cancelado"] > 0:
            parts.append(f"{counts['cancelado']} cancelada{'s' if counts['cancelado'] > 1 else ''}")

        self.status_counter.configure(text=" · ".join(parts) if parts else "")

    def _actualizar_consola(self):
        counts = {e: 0 for e in ESTADOS}
        for item in self.queue_items:
            counts[item["estado"]] = counts.get(item["estado"], 0) + 1
        activas = counts["descargando"] + counts["convirtiendo"] + counts["verificando"]
        if activas:
            partes = []
            if counts["descargando"]:
                partes.append(f"▶ {counts['descargando']} descargando")
            if counts["convirtiendo"]:
                partes.append(f"{counts['convirtiendo']} convirtiendo")
            if counts["verificando"]:
                partes.append(f"{counts['verificando']} verificando")
            self.estado_var.set(" · ".join(partes))
        elif counts["en_cola"]:
            self.estado_var.set("En cola · listo para iniciar")
        else:
            self.estado_var.set("Listo")
        self._actualizar_counter()

    # ---------- Estado helper ----------
    def _set_estado(self, item, estado):
        item["estado"] = estado
        self.after(0, lambda i=item: i["card"].set_estado(estado))
        self.after(0, self._actualizar_consola)

    def _set_titulo(self, item, titulo):
        item["titulo"] = titulo
        self.after(0, lambda i=item: i["card"].set_titulo(titulo))

    def _log(self, texto):
        entrada = {"fecha": time.strftime("%H:%M:%S"), "texto": texto}
        with self._hist_lock:
            self.historial.append(entrada)
            self.historial = self.historial[-100:]
        self.after(0, lambda: self._rend_actividad(entrada))

    def _rend_actividad(self, entrada):
        if not self.actividad_log.winfo_exists():
            return
        ctk.CTkLabel(self.actividad_log,
                     text=f"{entrada['fecha']}  {entrada['texto']}",
                     font=FONTS["mono_small"], text_color=COLORS["text.secondary"],
                     anchor="w", justify="left").pack(fill="x", padx=4, pady=1)

    # ---------- Agregar ----------
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

        for existente in self.queue_items:
            if existente["url"] == url:
                messagebox.showinfo("Ya en cola", "Esa URL ya está en la cola de descargas.")
                return

        item = {
            "url": url,
            "carpeta": carpeta,
            "modo": modo,
            "calidad": calidad,
            "subtitulos": subtitulos,
            "playlist": playlist,
            "navegador": navegador,
            "estado": "en_cola",
            "titulo": None,
            "cancel_flag": threading.Event(),
            "ydl_holder": {},
        }

        card = QueueCard(
            self.cola_scroll, url, plataforma, modo,
            on_cancel=lambda it=item: self._cancelar_item(it),
            on_retry=lambda it=item: self._reintentar_item(it),
            on_remove=lambda it=item: self._quitar_item(it),
        )
        card.grid(row=len(self.queue_items), column=0, sticky="ew", padx=4, pady=4)
        item["card"] = card
        self.queue_items.append(item)

        self._toggle_empty_state()
        self._actualizar_counter()
        self._guardar_prefs_actuales()
        self._log(f"Agregado: {url}")

        self.url_entry.delete(0, "end")

    # ---------- Cancel / Stop ----------
    def _cancelar_item(self, item):
        item["cancel_flag"].set()
        if item["estado"] == "en_cola":
            self._set_estado(item, "cancelado")
        else:
            self._log(f"Cancelando: {item['url']}")

    def _cancelar_item_fuerte(self, item):
        item["cancel_flag"].set()
        ydl = item["ydl_holder"].get("ydl")
        if ydl is not None:
            try:
                if hasattr(ydl, "_download_retcode"):
                    ydl._download_retcode = 1
            except Exception:
                pass

    def _detener_todo(self):
        self.stop_all.set()
        for item in self.queue_items:
            self._cancelar_item_fuerte(item)
        self._log("Solicitado detener todas las descargas.")

    # ---------- Iniciar cola ----------
    def _iniciar_cola(self):
        if self.is_downloading:
            return

        pending = [item for item in self.queue_items if item["estado"] == "en_cola"]
        if not pending:
            messagebox.showinfo("Cola vacía", "Agrega videos a la cola primero.")
            return

        self.stop_all.clear()
        nav_sesion = self._navegador_seleccionado()
        self.is_downloading = True
        self.btn_iniciar.configure(state="disabled", text="Descargando...")
        self.btn_detener.configure(state="normal")
        threading.Thread(target=self._procesar_cola, args=(pending, nav_sesion), daemon=True).start()

    def _procesar_cola(self, pending, navegador_actual):
        total = len(pending)
        max_paralelas = int(self.prefs.get("max_paralelas", 1) or 1)
        max_paralelas = max(1, min(max_paralelas, 3))

        try:
            if max_paralelas <= 1:
                for idx, item in enumerate(pending):
                    if self.stop_all.is_set():
                        break
                    try:
                        self._procesar_item(item, idx, total, navegador_actual)
                    except Exception as e:
                        self._marcar_fallo_interno(item, str(e))
            else:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=max_paralelas) as pool:
                    futures = []
                    for idx, item in enumerate(pending):
                        if self.stop_all.is_set():
                            break
                        futures.append(pool.submit(self._procesar_item, item, idx, total, navegador_actual))
                    for fut in futures:
                        try:
                            fut.result()
                        except Exception as e:
                            self._log(f"Error interno de hilo: {e}")
        finally:
            self.is_downloading = False
            self.stop_all.clear()
            self.after(0, lambda: self.btn_iniciar.configure(state="normal", text="Iniciar descargas"))
            self.after(0, lambda: self.btn_detener.configure(state="disabled"))
            self.after(0, self._actualizar_consola)

    def _marcar_fallo_interno(self, item, detalle):
        def _f():
            self._set_estado(item, "error")
            self._log(f"Error inesperado: {detalle}")
        self.after(0, _f)

    def _procesar_item(self, item, idx, total, navegador_actual):
        if item["estado"] != "en_cola":
            return
        if item["cancel_flag"].is_set():
            self._set_estado(item, "cancelado")
            return

        self._set_estado(item, "verificando")
        self._log(f"Verificando {idx + 1} de {total}: {item['url']}")

        precheck = verificar_url(item["url"], navegador_actual, item["cancel_flag"])
        restriccion = precheck.get("restriccion")
        tipo = restriccion.get("tipo") if restriccion else None

        if tipo == "cancelada" or item["cancel_flag"].is_set() or self.stop_all.is_set():
            self._set_estado(item, "cancelado")
            self._log(f"Cancelado durante verificación: {item['url']}")
            return

        if tipo in TIPOS_BLOQUEANTES and tipo not in TIPOS_REINTENTO_SESION:
            mensaje = restriccion["mensaje"]
            sugerencia = restriccion.get("sugerencia")
            if sugerencia:
                mensaje += "\n\nSugerencia:\n" + sugerencia
            self._set_estado(item, "error")
            card = item["card"]
            if hasattr(card, "set_error_detalle"):
                self.after(0, lambda m=mensaje: card.set_error_detalle(m))
            self._log(f"Error en {item['url']}: {restriccion['mensaje']}")
            self.after(0, lambda m=mensaje: self._mostrar_error_amigable(m))
            return

        info = precheck.get("info")
        if info and info.get("title"):
            self._set_titulo(item, info["title"])

        if item["cancel_flag"].is_set() or self.stop_all.is_set():
            self._set_estado(item, "cancelado")
            return

        self._set_estado(item, "descargando")
        self._log(f"Descargando {idx + 1} de {total}: {item['url']}")

        def on_progress(val):
            self.after(0, lambda v=val: item["card"].update_progress(v))

        def on_speed(speed, downloaded, total_bytes):
            speed_str = _formatear_velocidad(speed)
            eta_str = ""
            if speed > 0 and total_bytes > 0:
                resto = total_bytes - downloaded
                eta = resto / speed
                eta_str = _formatear_eta(eta)
            self.after(0, lambda s=speed_str, e=eta_str: item["card"].set_metricas(s, e))

        def on_postproc(estado, nombre):
            if estado == "started":
                self._set_estado(item, "convirtiendo")
                self.after(0, lambda: item["card"].set_metricas("", ""))
                self._log(f"Convirtiendo a mp3/mp4: {item['titulo'] or item['url']}")

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
            postprocessor_callback=on_postproc,
        )

        if exito is False and tipo_fallo == "cancelada":
            self._set_estado(item, "cancelado")
            self._log(f"Cancelado: {item['url']}")
            return

        if not exito and tipo_fallo in TIPOS_REINTENTO_SESION and not navegador_actual:
            nav = self._elegir_navegador_sesion()
            if nav:
                self._set_estado(item, "verificando")
                self._log(f"Reintentando con sesión de {nav.capitalize()}: {item['url']}")
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
                    postprocessor_callback=on_postproc,
                )
                if exito is False and tipo_fallo == "cancelada":
                    self._set_estado(item, "cancelado")
                    self._log(f"Cancelado: {item['url']}")
                    return

        if exito:
            self._set_estado(item, "listo")
            self.after(0, lambda: item["card"].set_metricas("", ""))
            self._log(f"Descarga completada: {item['titulo'] or item['url']}")
        else:
            self._set_estado(item, "error")
            self._log(f"Error en {item['url']}: {mensaje.splitlines()[0] if mensaje else 'desconocido'}")
            self.after(0, lambda m=mensaje: self._mostrar_error_amigable(m))

    def _mostrar_error_amigable(self, mensaje):
        una_linea = " ".join(parte.strip() for parte in mensaje.splitlines() if parte.strip())
        self._log("Detalle: " + (una_linea[:220] or "error desconocido"))

    # ---------- Reintentar ----------
    def _reintentar_item(self, item):
        if item["estado"] not in ("error", "cancelado", "listo"):
            return
        item["cancel_flag"].clear()
        item["estado"] = "en_cola"
        self.after(0, lambda: item["card"].set_estado("en_cola"))
        self.after(0, lambda: item["card"].set_metricas("", ""))
        self._log(f"Reintentando: {item['url']}")

        if self.is_downloading:
            self._toggle_empty_state()
            self.after(0, self._actualizar_consola)
            return

        nav_sesion = self._navegador_seleccionado()
        self.is_downloading = True
        self.btn_iniciar.configure(state="disabled", text="Descargando...")
        self.btn_detener.configure(state="normal")
        threading.Thread(target=self._procesar_cola, args=([item], nav_sesion), daemon=True).start()

    # ---------- Quitar item ----------
    def _quitar_item(self, item):
        if item["estado"] in ("descargando", "verificando", "convirtiendo"):
            item["cancel_flag"].set()
        if item in self.queue_items:
            self.queue_items.remove(item)
        self.after(0, lambda i=item: i["card"].destroy())
        self._reflow_cola()
        self._toggle_empty_state()
        self._actualizar_consola()
        self._log(f"Quitado de la cola: {item['url']}")

    def _reflow_cola(self):
        for row, it in enumerate(self.queue_items):
            self.after(0, lambda i=it, r=row: i["card"].grid(row=r, column=0, sticky="ew", padx=4, pady=4))

    # ---------- Limpiar ----------
    def _limpiar_cola(self):
        if not self.queue_items:
            return
        if not messagebox.askyesno("Limpiar cola",
                                   "¿Vaciar toda la cola? Las descargas activas se detendrán."):
            return
        for item in self.queue_items[:]:
            item["cancel_flag"].set()
            self.after(0, lambda i=item: i["card"].destroy())
        self.queue_items.clear()
        self._toggle_empty_state()
        self._actualizar_consola()
        self._log("Cola limpiada.")

    def _abrir_diagnostico(self):
        url = self.url_entry.get().strip()
        if not url:
            for item in self.queue_items:
                url = item["url"]
                break
        navegador = self._navegador_seleccionado()
        VentanaDiagnostico(self, url, navegador)

    # ---------- Update ----------
    def _check_update_async(self):
        def run():
            has_update, latest, url = check_for_update(__version__)
            if has_update:
                self.after(0, lambda: self._show_update(latest, url))
        threading.Thread(target=run, daemon=True).start()

    def _show_update(self, latest, url):
        respuesta = messagebox.askyesno(
            "Actualización disponible",
            f"Hay una nueva versión: v{latest}\n\n"
            "¿Deseas abrir la página de descarga?"
        )
        if respuesta and url:
            import webbrowser
            webbrowser.open(url)


def _formatear_velocidad(speed):
    if speed > 1024 * 1024:
        return f"{speed / (1024 * 1024):.1f} MB/s"
    if speed > 1024:
        return f"{speed / 1024:.0f} KB/s"
    return f"{speed:.0f} B/s"


def _formatear_eta(segundos):
    segundos = int(segundos)
    h, m = divmod(segundos, 3600)
    m, s = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


if __name__ == "__main__":
    app = App()
    app.mainloop()
