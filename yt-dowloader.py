#!/usr/bin/env python3
import yt_dlp
import os
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk


def descargar_musica(url, carpeta="Mi_musica", modo="audio", calidad="192"):
    try:
        if not os.path.exists(carpeta):
            os.makedirs(carpeta)
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
                "postprocessor_args": [
                    "-ar", "44100"
                ],
                "prefer_ffmpeg": True
            }
        else:  # modo video
            # Mapear calidad a formato de video
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
                "prefer_ffmpeg": True
            }
        with yt_dlp.YoutubeDL(opciones) as ydl:
            ydl.download([url])
        return True, f"{('Audio' if modo=='audio' else 'Video')} descargado correctamente"
    except Exception as e:
        return False, f"Error al descargar el {'audio' if modo=='audio' else 'video'}: {e}"


def descargar_desde_gui():
    url = url_var.get()
    modo = modo_var.get()
    calidad = calidad_var.get()
    if not url.strip():
        messagebox.showwarning("Advertencia", "Por favor ingresa una URL.")
        return
    btn_descargar.config(state=tk.DISABLED)
    estado_var.set(f"Descargando {'audio' if modo=='audio' else 'video'}...")
    root.update()
    exito, mensaje = descargar_musica(url, modo=modo, calidad=calidad)
    if exito:
        estado_var.set("✅ " + mensaje)
        messagebox.showinfo("Éxito", mensaje)
    else:
        estado_var.set("❌ " + mensaje)
        messagebox.showerror("Error", mensaje)
    btn_descargar.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("YT-DownLoader del Jaeger")
    root.geometry("700x700")
    root.minsize(700, 700)
    root.resizable(True, True)
    root.configure(bg="#181818")  # Fondo negro elegante

    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('TFrame', background="#232323", borderwidth=0, relief="flat")
    style.configure('TLabel', background="#232323", foreground="#fff", font=("Segoe UI", 12))
    style.configure('Title.TLabel', font=("Segoe UI", 20, "bold"), background="#232323", foreground="#fff")
    style.configure('TButton', font=("Segoe UI", 13, "bold"), padding=10, borderwidth=0, relief="flat", background="#1e90ff", foreground="#fff")
    style.map('TButton', background=[('active', '#1565c0')], foreground=[('active', '#fff')])
    style.configure('Status.TLabel', font=("Segoe UI", 11), background="#232323", foreground="#1e90ff")
    style.configure('TRadiobutton', background="#232323", foreground="#fff", font=("Segoe UI", 12))
    style.map('TRadiobutton', background=[('active', '#232323')], foreground=[('active', '#1e90ff')])
    style.configure('TCombobox', fieldbackground="#232323", background="#232323", foreground="#fff", font=("Segoe UI", 14), padding=6)
    style.map('TCombobox', fieldbackground=[('readonly', '#232323')], foreground=[('readonly', '#fff')])
    style.configure('TCombobox.Listbox', background="#232323", foreground="#fff", font=("Segoe UI", 14))

    frame = ttk.Frame(root, padding=32, style='TFrame')
    frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)
    frame.config(borderwidth=0)
    frame['style'] = 'TFrame'

    title = ttk.Label(frame, text="🎵 YouTube Audio Downloader", style='Title.TLabel')
    title.pack(pady=(0, 24))

    label = ttk.Label(frame, text="Pega la URL del video de YouTube:")
    label.pack(pady=(0, 12))

    url_var = tk.StringVar()
    entry = ttk.Entry(frame, textvariable=url_var, font=("Segoe UI", 12), width=38)
    entry.pack(pady=(0, 16))
    entry.focus()

    # Selector de modo (audio o video)
    modo_var = tk.StringVar(value="audio")
    def actualizar_calidades(*args):
        if modo_var.get() == "audio":
            calidad_combo['values'] = ("128", "192", "256", "320")
            calidad_var.set("320")
        else:
            calidad_combo['values'] = ("360p", "480p", "720p", "1080p")
            calidad_var.set("1080p")

    radio_frame = ttk.Frame(frame, style='TFrame')
    radio_audio = ttk.Radiobutton(radio_frame, text="Audio (mp3)", variable=modo_var, value="audio", command=actualizar_calidades, style='TRadiobutton')
    radio_video = ttk.Radiobutton(radio_frame, text="Video (mp4)", variable=modo_var, value="video", command=actualizar_calidades, style='TRadiobutton')
    radio_audio.pack(side=tk.LEFT, padx=10)
    radio_video.pack(side=tk.LEFT, padx=10)
    radio_frame.pack(pady=(0, 16))

    # Selector de calidad
    calidad_var = tk.StringVar()
    label_calidad = ttk.Label(frame, text="Calidad:")
    label_calidad.pack(pady=(0, 6))
    calidad_combo = ttk.Combobox(frame, textvariable=calidad_var, font=("Segoe UI", 14), width=12, state="readonly", style='TCombobox')
    calidad_combo['values'] = ("128", "192", "256", "320")
    calidad_combo.pack(pady=(0, 16))
    # Vincular cambios de modo para actualizar calidades
    modo_var.trace_add('write', lambda *args: actualizar_calidades())
    # Inicializar calidad por defecto según el modo
    actualizar_calidades()

    btn_descargar = ttk.Button(frame, text="Descargar", command=descargar_desde_gui, style='TButton')
    btn_descargar.pack(pady=(0, 20))

    estado_var = tk.StringVar()
    estado = ttk.Label(frame, textvariable=estado_var, style='Status.TLabel')
    estado.pack(pady=(0, 0))

    root.mainloop()