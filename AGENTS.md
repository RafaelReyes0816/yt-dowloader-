# AGENTS.md

## Project overview

Python desktop app (CustomTkinter UI in `yt-dowloader.py` + pure business logic in `core.py`, using yt-dlp) that downloads audio (mp3) or video (mp4) from many platforms with quality selection, a download queue with cancel/parallel support, and auto-update checking via GitHub Releases API.

## Run

```bash
pip install -r requirements.txt
python yt-dowloader.py
```

System dependency: `ffmpeg` must be installed and on PATH (required by yt-dlp for mp3 conversion and mp4 muxing). On Debian/Ubuntu: `sudo apt install python3-tk` if tkinter is missing.

## Build standalone executable

```bash
pip install pyinstaller yt-dlp customtkinter
pyinstaller yt-dowloader.spec
```

Output goes to `dist/`. The spec is **multiplatform** — no `target_arch` hardcoded. PyInstaller autodetects the platform.

## CI/CD

GitHub Actions workflow at `.github/workflows/build.yml` builds for Linux, Windows (x64), and macOS (Intel + ARM) on tag push (`v*`). Uses `softprops/action-gh-release` to publish executables.

To trigger a release:
```bash
git tag v1.0.0
git push origin v1.0.0
```

## Architecture

- `yt-dowloader.py` — CustomTkinter UI (`App`, `VentanaDiagnostico`, `QueueCard`, `SegmentedControl`, `PillToggle`). Imports business logic from `core.py`.
- `core.py` — pure business logic, no UI/network on import (testable): `PLATFORM_REGEX`, `detectar_plataforma`, `ClasificadorErrores`, `verificar_url`, `extraer_info_video`, `descargar_musica`, `find_ffmpeg`, prefs load/save, `comparar_versiones`, `elegir_navegador_sesion`, `PLATAFORMAS_CONFIG`, `RESOLUCIONES_YOUTUBE`. `Mi_musica/` folder is created at runtime as download target. `check_for_update()` queries GitHub Releases API.
- Platforms (v3.0+): YouTube, Instagram, Facebook, TikTok, Twitch, Vimeo, Twitter/X (`twitter.com`/`x.com`), Reddit.
- Filenames (v3.0+): YouTube downloads use `%(title)s [%(id)s].%(ext)s` to guarantee uniqueness; other platforms use `%(title)s.%(ext)s`.
- Cancel (v3.0+): each `QueueCard` has a "Cancelar" button and there's a global "Detener todo". `descargar_musica()` accepts `cancel_flag` (a `threading.Event`) checked in the progress hook, which raises `DescargaCancelada` (in `core.py`) to abort `ydl.download()`; and `ydl_holder` (a dict) to expose the active `YoutubeDL` for immediate stop.
- Parallelism (v3.0+): optional `max_paralelas` pref (1-3, default 1). `_procesar_cola` uses a `ThreadPoolExecutor` when >1; `_procesar_item` handles a single item. All UI updates go through `self.after(0, ...)`.
- Errors (v3.0+): non-`DownloadError` exceptions now also go through `ClasificadorErrores` (with real technical message surfaced) before falling back to the generic message.
- Auth support (v2.2+): `ClasificadorErrores` maps yt-dlp errors / `availability` field to friendly Spanish messages + suggestions; `detectar_navegadores()` + `construir_opciones_cookies()` enable optional browser-session downloads (`cookiesfrombrowser`); `verificar_url()` runs a pre-download restriction check; `VentanaDiagnostico` is the modal diagnostics window. Prefs `usar_sesion_navegador` / `navegador` persist the auth config. No credentials are ever stored.
- Auth auto-retry (v2.2.1+): when a download fails with `private`/`sign_in`/`bot`/`age_restricted`/`members_only`/`cookies` error and session is disabled, the app retries automatically once with the first detected browser (order: Firefox > Chrome > Brave > Edge) unless the user has explicitly enabled session.
- Diagnostic PyPI check (v2.2.1+): `obtener_ultima_version_ytdlp()` queries PyPI to compare installed yt-dlp version against the latest; shows DESACTUALIZADO in red with an "Actualizar motor yt-dlp" button that runs `pip install -U yt-dlp` (or opens GitHub Releases for frozen builds). The old behavior comparing app releases was removed.
- Error detail surfacing (v2.2.1+): every classified error now carries a `detalle` field (truncated raw yt-dlp message) shown in error dialogs and the diagnostics window for easier troubleshooting.
- Tests (v3.0+): `core_tests/test_core.py` (pytest) covers pure logic (platform detection, regex, classifier, version compare, outtmpl/options, cancel hook). Run with `.venv/bin/python -m pytest`. Dev deps in `requirements-dev.txt`.
- CI (v3.0+): `.github/workflows/build.yml` runs `pytest` on the Linux build member before `pyinstaller`; a test failure blocks the release.
- `yt-dowloader.spec` — PyInstaller build config (multiplatform, includes CustomTkinter data files).
- `.github/workflows/build.yml` — CI/CD for 3 platforms.
- `requirements.txt` — `yt-dlp`, `customtkinter`, `pyinstaller`.

## Notes

- Filename typo `dowloader` (missing 'n') is intentional — matches the PyInstaller spec output name. Do not rename without updating the spec.
- UI is entirely in Spanish.
- `GITHUB_REPO` constant in `core.py` must match your actual GitHub repo path for auto-update to work.
- `bfg-*.jar` files in repo are BFG Repo-Cleaner (used to purge secrets from git history). Not part of the app. Ignored by `.gitignore` for new files.
