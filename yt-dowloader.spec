# -*- mode: python ; coding: utf-8 -*-
import sys
import customtkinter
from PyInstaller.utils.hooks import collect_all

block_cipher = None

ctk_path = customtkinter.__path__[0]

datas = [
    (ctk_path, 'customtkinter'),
]
binaries = []
hiddenimports = [
    'customtkinter',
    'curl_cffi',
    'curl_cffi.requests',
]

# En Linux las cookies de Chrome/Edge/Brave se descifran con libsecret a traves
# de `secretstorage`, que es un extra opcional de yt-dlp (no viene en
# `default`). Si no se empaqueta, la app no puede copiar la base de datos de
# cookies -> "Could not copy ... cookie database".
if sys.platform.startswith('linux'):
    try:
        _d, _b, _h = collect_all('secretstorage')
    except Exception:
        _d, _b, _h = [], [], []
    datas += _d
    binaries += _b
    hiddenimports += _h
    hiddenimports.append('secretstorage')
    hiddenimports.append('jeepney')

a = Analysis(
    ['yt-dowloader.py', 'core.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='yt-dowloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='yt-dowloader',
)
