# AGENTS.md

## Communication

**Always reply to the user in Spanish**, regardless of the language they write in: every explanation, summary, question, plan, commit message and code comment in the conversation must be written in Spanish. Code identifiers and file contents keep the project's existing convention (English identifiers, Spanish UI strings).

## Project overview

Python desktop app (CustomTkinter UI in `yt-dowloader.py` + pure business logic in `core.py`, using yt-dlp) that downloads audio (mp3) or video (mp4) from many platforms with quality selection, a download queue with cancel/parallel support, and auto-update checking via GitHub Releases API.

## Run

```bash
pip install -r requirements.txt   # or: pip install -r requirements-dev.txt (includes pytest)
python yt-dowloader.py
```

System dependency: `ffmpeg` must be installed and on PATH (required by yt-dlp for mp3 conversion and mp4 muxing). On Debian/Ubuntu: `sudo apt install python3-tk` if tkinter is missing.

## Tests

```bash
.venv/bin/python -m pytest        # 133 offline tests (pytest.ini defaults to -m "not live")
```

- Offline unit tests: `core_tests/test_core.py` (platform detection, regex, classifier, options, cancel hook, prefs, anti-hang).
- Live integration tests: `core_tests/test_plataformas_live.py` hits 8 real URLs, marked `@pytest.mark.live` and **skipped by default**. Run manually only when needed: `.venv/bin/python -m pytest core_tests/test_plataformas_live.py -m live -v`. No CI job for them.
- Dev deps in `requirements-dev.txt`. CI runs `pytest` on the Linux build before `pyinstaller`; a failure blocks the release.

## Build standalone executable

```bash
pip install pyinstaller yt-dlp customtkinter
pyinstaller yt-dowloader.spec
```

Output goes to `dist/`. The spec is **multiplatform** — no `target_arch` hardcoded. PyInstaller autodetects the platform. The spec's `hiddenimports` must keep `curl_cffi`/`curl_cffi.requests` (TikTok impersonation) and bundle CustomTkinter data files.

## CI/CD

GitHub Actions workflow at `.github/workflows/build.yml` builds for Linux, Windows (x64), and macOS (Intel + ARM) on tag push (`v*`). Uses `softprops/action-gh-release` to publish executables + installers (NSIS `.exe`, `.deb`, `.dmg`). Windows CI bundles `ffmpeg.exe`/`ffprobe.exe` into the dist.

To trigger a release:
```bash
git tag v1.0.0
git push origin v1.0.0
```

## Architecture

- Skills (v3.3+): project skills live in `.opencode/skills/` (`security-best-practices`, `tdd`, `frontend-design`, `web-design-guidelines`) and are indexed in `SKILLS_PROYECTO.md`. Invoke them by exact name via the `skill` tool. (`~/.agents/skills` and `~/.claude/skills` auto-load the rest of the installed catalog.)
- `yt-dowloader.py` — CustomTkinter UI (`App`, `VentanaDiagnostico`, `QueueCard`, `SegmentedControl`, `PillToggle`, `Annunciador`, `SpinnerRing`). Imports business logic from `core.py`.
- `theme.py` — design tokens (colors, fonts, radii) + `GLYPHS`. `Annunciador` shows transient HUD status; `SpinnerRing` is the indeterminate animated ring. All UI feedback is threaded through `self.after(0, ...)`.
- `core.py` — pure business logic, **no UI/network on import** (testable): `PLATFORM_REGEX`, `extraer_url_completa` (extracts a full URL from pasted text, cleaning query strings/parentheses/punctuation), `detectar_plataforma`, `ClasificadorErrores`, `verificar_url(url, navegador=None, cancel_flag=None)`, `extraer_info_video`, `descargar_musica(..., cancel_flag, ydl_holder, postprocessor_callback, idioma_audio, idioma_subtitulos, subtitulos_auto)`, `find_ffmpeg`, prefs load/save, `comparar_versiones`, `elegir_navegador_sesion`, `obtener_ultima_version_ytdlp`, `check_for_update()`, `PLATAFORMAS_CONFIG`, `RESOLUCIONES_YOUTUBE`, `RESOLUCIONES_GENERICAS`, `CALIDADES_AUDIO`/`CALIDADES_VIDEO` (UI must not hardcode them), `TIMEOUT_RED`, `IDIOMAS_CODIGOS`/`IDIOMAS_NOMBRES`/`IDIOMAS_AUDIO`/`IDIOMAS_SUBTITULOS`/`SUBTITULOS_AUTO_FALLBACK`/`IDIOMA_AUTO`, `aplicar_idioma_a_selector`, `_patrones_subtitulos`, `listar_idiomas_audio`/`listar_idiomas_subtitulos` (take an `info` dict), `listar_restos`/`listar_subtitulos_huerfanos`/`limpiar_restos`. `Mi_musica/` folder is created at runtime as download target.
- Platforms: YouTube, Instagram, Facebook, TikTok, Twitch, Vimeo, Twitter/X (`twitter.com`/`x.com`), Reddit.
- Filenames: every platform uses `%(title)s [%(id)s].%(ext)s` (the `[id]` suffix avoids collisions between same-titled videos and matches the `existing_file` skip check).
- Language prefs: `idioma_audio` (audio-track preference, `auto` = original) and `idioma_subtitulos` (`auto` = Spanish/English/Portuguese fallback) + `subtitulos_auto` (write auto-captions). Subtitle options are applied only in video mode and only for platforms with `soporta_subtitulos`; non-YouTube picks the audio language via `[language=xx]` (selector keeps its `/best` fallback). Video subs are **embedded** into the mp4 (`FFmpegEmbedSubtitle`) and the loose `.vtt` is deleted by yt-dlp; audio mode never writes subtitles.
- Anti-leftovers/tmpdir: downloads run inside a `.tmp-<rand>` dir created with `tempfile.mkdtemp` in the destination folder (used as `outtmpl["temp"]`/`["subtitle"]`), so `.part`, fragments and ffmpeg temps never touch the destination; `descargar_musica` always `shutil.rmtree`s it in `finally`. Manual cleanup: "Limpiar restos" button → `listar_restos` preview → confirmation → `limpiar_restos(carpeta, incluir_subtitulos=...)`; loose subtitles are only deleted with explicit opt-in and only when their base name matches an existing media file.
- Cancel: each `QueueCard` has "Cancelar" plus a global "Detener todo". `descargar_musica()` takes `cancel_flag` (`threading.Event`) checked in both the progress hook and the postprocessor hook (so cancel works during convert); raises `DescargaCancelada`. `ydl_holder` exposes the active `YoutubeDL` for immediate stop. `_limpiar_cola` aborts items hard via `_cancelar_item_fuerte`; `_cola_run_id` guards against a stale worker re-disabling buttons of a newer run.
- Parallelism: optional `max_paralelas` pref (1-3, default 1). `_procesar_cola` uses `ThreadPoolExecutor` when >1; `_procesar_item` handles one item. **All UI updates must go through `self.after(0, ...)`** (Tkinter is not thread-safe).
- Errors: `ClasificadorErrores` maps yt-dlp errors / `availability` to friendly Spanish messages + suggestions + a `detalle` field (truncated raw message, sanitized via `sanitizar_detalle`). Non-`DownloadError` exceptions also go through it.
- Auth: optional browser-session downloads via `cookiesfrombrowser` (`detectar_navegadores()` + `construir_opciones_cookies()`). No credentials are ever stored. Auto-retry once with the first detected browser (Firefox > Chrome > Brave > Edge) on private/sign_in/bot/age_restricted/members_only/cookies errors when session is disabled.
- Quality: non-YouTube audio honors the `calidad` bitrate (`preferredquality`); non-YouTube video uses `RESOLUCIONES_GENERICAS`. **YouTube 1440p/2160p selectors must NOT use `[ext=mp4]`** (4K/2K are only served as VP9/AV1); 360p–1080p keep the mp4 filter.
- Anti-hang: `_opciones_base()` (used by `verificar_url`) forces `noplaylist=True`; verification and download set `socket_timeout=TIMEOUT_RED` (20 s). `verificar_url` catches `DescargaCancelada` and returns `restriccion={"tipo": "cancelada"}`.
- TikTok: requires `yt-dlp[default,curl-cffi]>=2026.8.19` in `requirements.txt` plus `curl_cffi` hiddenimports in the spec; classifier maps TikTok extraction/impersonation errors to a friendly `extractor` message.
- Privacy in UI: pref `ocultar_urls` (default ON) + `enmascarar_url()` masks URLs in queue cards, diagnostics, history and copy; error logging goes through `_registrar_error` with sanitized detail.
- Diagnostics window: `VentanaDiagnostico` calls `transient(self.master)` and schedules `_encima()` at 120 ms (`deiconify`+`lift`+`focus_force`+`-topmost` for 300 ms). Calling `lift()` in `__init__` before the Toplevel is mapped silently fails. It also lists the detected audio/subtitle languages (`listar_idiomas_audio`/`listar_idiomas_subtitulos` on the `info` already fetched by `verificar_url`) plus the current preference.
- Shortcuts/a11y: Ctrl+Return add, Ctrl+L clear, Ctrl+D toggle auto-URL; `_detectar_motion_reducida()` (macOS `osascript`) slows the spinner interval.

## Notes

- Filename typo `dowloader` (missing 'n') is intentional — matches the PyInstaller spec output name. Do not rename without updating the spec.
- UI is entirely in Spanish.
- `GITHUB_REPO` constant in `core.py` must match the actual GitHub repo path for auto-update to work.
- `bfg-*.jar` files in repo are BFG Repo-Cleaner (used to purge secrets from git history). Not part of the app. Ignored by `.gitignore` for new files.
- Open security items (2026-09-14 audit): **SEC-03** — anchor `PLATFORM_REGEX`/`extraer_url_completa` to the real host (current substring matching accepts `youtube.com.evil.example`). **SEC-04** — `os.chmod(CONFIG_FILE, 0o600)` on save and validate `saved` is a dict on load. SEC-05 (`cookiesfrombrowser`) needs no change — credentials are never stored.
