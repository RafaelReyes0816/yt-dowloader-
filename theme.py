#!/usr/bin/env python3
"""Tokens de diseno de YT-DownLoader del Jaeger.

Unico punto donde viven colores, tipografias, espaciado y radios.
Editar aqui cambia toda la paleta/estilo de la aplicacion.
"""

import sys


def _familia_display():
    if sys.platform == "win32":
        return ("Segoe UI Semibold", "Segoe UI", "TkDefaultFont")
    if sys.platform == "darwin":
        return ("SF Pro Display", "Helvetica Neue", "TkDefaultFont")
    return ("Noto Sans", "DejaVu Sans", "TkDefaultFont")


def _familia_ui():
    if sys.platform == "win32":
        return ("Segoe UI", "TkDefaultFont")
    if sys.platform == "darwin":
        return ("SF Pro Text", "Helvetica Neue", "TkDefaultFont")
    return ("Noto Sans", "DejaVu Sans", "TkDefaultFont")


def _familia_mono():
    if sys.platform == "win32":
        return ("Consolas", "Courier New", "TkFixedFont")
    if sys.platform == "darwin":
        return ("Menlo", "Monaco", "TkFixedFont")
    return ("DejaVu Sans Mono", "Noto Sans Mono", "TkFixedFont")


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
    "display": (_familia_display(), 24, "bold"),
    "subtitle": (_familia_ui(), 13),
    "body": (_familia_ui(), 13),
    "body_bold": (_familia_ui(), 13, "bold"),
    "small": (_familia_ui(), 11),
    "small_bold": (_familia_ui(), 11, "bold"),
    "mono": (_familia_mono(), 12),
    "mono_small": (_familia_mono(), 10),
    "tag": (_familia_ui(), 10),
}

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
}

RADII = {
    "input": 8,
    "card": 12,
    "pill": 999,
}

PLATAFORMA_BADGE = {
    "YouTube": "#FF4F6E",
    "Instagram": "#E1306C",
    "TikTok": "#00F2EA",
    "Facebook": "#1877F2",
    "Twitch": "#9146FF",
    "Vimeo": "#1AB7EA",
    "Twitter/X": "#1DA1F2",
    "Reddit": "#FF4500",
    "Otra": "#8B96AE",
}

PLATAFORMA_INICIAL = {
    "YouTube": "YT",
    "Instagram": "IG",
    "TikTok": "TT",
    "Facebook": "FB",
    "Twitch": "TW",
    "Vimeo": "VM",
    "Twitter/X": "X",
    "Reddit": "RD",
    "Otra": "??",
}
