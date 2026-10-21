# AGENTS.md

## Communication

Reply to the user **in Spanish** (explanations, plans, questions, commit messages). Code identifiers stay English; UI strings are Spanish.

## Project overview

Python desktop app: CustomTkinter UI (`yt-dowloader.py`) + pure logic (`core.py`) on yt-dlp. Downloads mp3/mp4 from 8 platforms (YouTube, Instagram, Facebook, TikTok, Twitch, Vimeo, Twitter/X, Reddit) with quality selection, a cancellable optionally-parallel queue, browser-session auth, and auto-update via GitHub Releases.

## Repo quirks

- Repo path contains **spaces** (`.../Proyectos web/yt-dowloader-`) — quote paths in shell commands.
- A `.venv/` with dev deps already exists (pytest 9.1.1, customtkinter 6.0.0, yt-dlp 2026.8.19, pyinstaller 6.22, curl_cffi 0.16.3). Prefer `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/pyinstaller`. **Pillow is NOT installed in the venv** (it is in `requirements.txt`) — the window icon falls back silently, so a missing icon is not a bug.
- No linter/formatter/typecheck is configured. Verification = pytest + `py_compile`.
- The entry module has hyphens (`yt-dowloader.py`) and cannot be imported by name; tests only import `core`/`theme`. Run the app as a script.
- Runtime paths: prefs = `~/.yt-downloader/config.json`, downloads = `~/Downloads/Mi_musica` (pref `carpeta`, created at runtime by `descargar_musica`, `core.py:981`). Update downloads = `~/.yt-downloader/updates/`.

## Run

```bash
pip install -r requirements.txt   # or: requirements-dev.txt (adds pytest)
python yt-dowloader.py
```

System deps: `ffmpeg` on PATH (mp3 conversion + mp4 muxing). Debian/Ubuntu: `sudo apt install python3-tk` if tkinter is missing.
Linux + cookies de Chrome/Edge/Brave: `secretstorage` (ya en `requirements.txt` con marcador `sys_platform == "linux"`) + `libsecret-1-0` y un gestor de claves en marcha. Firefox/Gecko no lo necesita.

## Tests

```bash
.venv/bin/python -m pytest                # offline suite: 268 passed, 1 skipped, 16 live deselected (v3.8.1)
.venv/bin/python -m pytest core_tests/test_core.py -k <nombre> -q   # single test
.venv/bin/python -m py_compile yt-dowloader.py core.py theme.py     # syntax check (run before committing)
xvfb-run -a .venv/bin/python core_tests/smoke_ui.py                 # smoke de UI (headless)
```

- `pytest.ini` sets `testpaths = core_tests`, `pythonpath = .`, `addopts = -m "not live"` → live tests are skipped by default and **CI only runs this offline suite** (on Linux, before `pyinstaller`; failure blocks the release).
- Live suite: `core_tests/test_plataformas_live.py` — 16 tests over 8 real public URLs, marked `@pytest.mark.live`. Run manually only when needed: `.venv/bin/python -m pytest core_tests/test_plataformas_live.py -m live -v`. No CI job.
- `core_tests/diagnostico_cookies.py` is **not a test** (no `test_` prefix → pytest never collects it). It is a standalone cookie/browser diagnostic script: `python core_tests/diagnostico_cookies.py [URL]`. CI compiles it via `.github/workflows/diagnostico.yml` (`workflow_dispatch` only).
- `core_tests/smoke_ui.py` is **not a test** either: standalone smoke of the UI (hermético, sin red ni portapapeles). CI lo ejecuta como paso **bloqueante** en Linux (`xvfb-run -a python core_tests/smoke_ui.py`, requiere el paquete `xvfb` en el runner) justo después de la suite offline; si la UI no arranca, la build falla.
- `core_tests/pre_release_check.py` is **not a test** either: chequeo E2E previo a una release (`--url/--res/--navegador/--solo`, exit 1 si falla). Verifica mp4 H.264+AAC, mp3, sufijo ` [id]` y `.vtt` junto al medio. **Debe ejecutarse en una red sin bloqueo de bot** (desde una IP bloqueada siempre falla). Sus checks de `ffprobe` sí están cubiertos por la suite offline (`TestPreReleaseCheckConMedioSintetico`: genera con ffmpeg un mp4 h264+aac, uno vp9, un mp3 y un pcm con extensión .mp3, y verifica que se aceptan/rechazan correctamente); se omiten si no hay `ffmpeg`/`ffprobe` (el CI de Linux los instala para que no se salten).
- CI cannot catch real-download bugs — the AV1/VLC regression shipped that way. Before tagging a release, run `core_tests/pre_release_check.py` (or manually verify one real mp3 + one real mp4 download, expect `h264/avc1` + `aac` in the mp4).

## Build standalone executable

```bash
pyinstaller yt-dowloader.spec    # output in dist/
```

Spec is **multiplatform** (no `target_arch`; PyInstaller autodetects). Its `hiddenimports` must keep `curl_cffi`/`curl_cffi.requests` (TikTok impersonation) and it bundles CustomTkinter data files. On Linux it also does `collect_all("secretstorage")` (cookies of Chromium) — guarded by `try/except` so the build never breaks if the module is absent.

Installers are built by CI from repo sources, not by the spec: `installer.nsi` (NSIS → `YT-DownLoader-Jaeger-Setup.exe`) and `packaging/linux/` (`DEBIAN/control` + `.desktop` → `.deb`, installed to `/opt/yt-dowloader`). The `.deb` is built **only** on `ubuntu-22.04` with `Architecture: amd64` hardcoded; CI seds the version from the tag.

## Release flow

1. Bump `__version__` (line 2 of `yt-dowloader.py`). Commit style: `feat vX.Y.Z: ...` / `fix vX.Y.Z: ...` (message in Spanish).
2. Verify: pytest + py_compile (+ the manual real-download check above).
3. `git tag vX.Y.Z && git push origin vX.Y.Z` — push **the tag itself**; lightweight tags are not pushed by `--follow-tags`.
4. Tag `v*` triggers `.github/workflows/build.yml`: builds Linux/Windows/macOS (Python 3.12), runs the offline suite on Linux, packages NSIS `.exe` + portable zip, `.deb` + tar.gz, `.dmg` + `.app` zip (Windows CI bundles `ffmpeg.exe`/`ffprobe.exe`), publishes 7 assets + `SHA256SUMS` via `softprops/action-gh-release`. Also runnable manually via `workflow_dispatch` (the `release` job only runs on a tag ref, so a manual run builds but does not publish). The `Resolve version` step takes the version from the tag and falls back to `__version__` in `yt-dowloader.py` when the ref is a branch, so `dpkg-deb` never gets a non-numeric `Version`.
5. Update `MEMORY.md` on the final commit of the batch (its header states the rule: version, commit/tag hash, CI status, test count).

Note: `core_tests/pre_release_check.py` was **recreated in v3.8.1** (it had existed in v3.4.x and was removed in the 2026-10-18 revert). It is standalone, not collected by pytest, and is the automated replacement for the manual real-download check.

## Architecture

- `core.py` — pure business logic, **no UI/network on import** (testable): `PLATFORM_REGEX`, `extraer_url_completa`, `detectar_plataforma`, `ClasificadorErrores` (yt-dlp errors → friendly Spanish + `detalle` field, sanitized via `sanitizar_detalle`), `verificar_url(url, navegador=None, cancel_flag=None)`, `extraer_info_video`, `descargar_musica(..., cancel_flag, ydl_holder, postprocessor_callback)`, `find_ffmpeg`, prefs load/save, `comparar_versiones`, `check_for_update()` (GitHub Releases) + `obtener_ultima_version_ytdlp()` (PyPI), `PLATAFORMAS_CONFIG`, `RESOLUCIONES_YOUTUBE`, `RESOLUCIONES_GENERICAS`, `CALIDADES_AUDIO`/`CALIDADES_VIDEO` (**the UI must not hardcode qualities**), `TIMEOUT_RED`=20, `ORDEN_NAVEGADORES`, `NAVEGADORES_COMPATIBLES_ABIERTOS`, `NAVEGADORES_RUTAS`, `NAVEGADORES_ARCHIVO_PERFIL`, `NAVEGADORES_GECKO`, `perfil_gecko`, `navegadores_cacheados`, `TIPOS_CUENTA`, `CLIENTES_FALLBACK_BOT`, `navegadores_para_reintento`, `TIPOS_REINTENTO_SESION`/`TIPOS_REINTENTO_CLIENTES`/`TIPOS_BLOQUEANTES` + `reintentar_con_sesion(tipo)`/`debe_abortar_descarga(tipo)` (contrato único de tipos; la UI **debe** usar los helpers, no sets inline).
- `yt-dowloader.py` — UI: `App`, `VentanaDiagnostico`, `VentanaActualizacion`, `QueueCard`, `SegmentedControl`, `PillToggle`, `Annunciador` (transient HUD), `SpinnerRing`. **All UI updates must go through `self.after(0, ...)`** — Tkinter is not thread-safe; worker threads never touch widgets directly.
- Responsive layout (v3.7.0): `_build_ui` builds `body` → `panel_izq` (input+opciones) + `panel_der` (cola); header/annunciador/statusbar stay on `self`. `<Configure>` → debounced (`_resize_job`, 80 ms) `_on_resize` → `_aplicar_layout_por_ancho`: `< BREAKPOINTS["dos_columnas"]` (1080 px, `theme.py`) → 1 columna apilada, `>=` → 2 columnas (sidebar fijo `LAYOUT["sidebar_w"]`=360 px, cola flexible). `_aplicar_layout` only re-grids the **same** panels (never recreates widgets); `_reflow_fila`/`_reflow_opciones`/`_reflow_botones_cola` re-wrap option toggles and queue buttons by `winfo_reqwidth()` vs container width; `_limitar_ancho_cards` caps `QueueCard`s at `LAYOUT["card_max_w"]`=900 px (left-aligned) via a trailing spacer column in `cola_inner`. Window geometry persisted as pref `ventana_geom` (`_geometria_actual()` on save, `_restaurar_geometria()` + `_asegurar_visible()` on start).
- `theme.py` — design tokens (colors/fonts/radii) + `GLYPHS`.
- YouTube selectors (do NOT "simplify" — `RESOLUCIONES_YOUTUBE` in `core.py:211-218`): 360p–1080p prefer H.264 `[vcodec^=avc1]` + AAC `[ext=m4a]` with plain-mp4 fallback, because yt-dlp defaults to AV1/VP9 which VLC/WMP cannot open inside mp4 (GitHub issues #1/#2, "VLC es incapaz de abrir el MRL"). **1440p/2160p must NOT use `[ext=mp4]` or the avc1 filter** — 2K/4K are only served as VP9/AV1.
- Filenames: YouTube uses `%(title)s [%(id)s].%(ext)s` (uniqueness); other platforms `%(title)s.%(ext)s`. `outtmpl` is always a **flat string** (never a dict): with subtitles enabled (`writesubtitles` + `subtitleslangs=["es","en","pt"]`, YouTube only) the `.vtt` lands next to the media file, in the same folder — no `Título [id]/` subfolder (restored to v3.3.2 behaviour in v3.8.0).
- Cancel: `cancel_flag` (`threading.Event`) is checked in **both** the progress hook and the postprocessor hook (convert phase is cancellable); `ydl_holder` exposes the active `YoutubeDL` for an immediate stop; `_limpiar_cola` hard-aborts items via `_cancelar_item_fuerte`, and `_cola_run_id` stops a stale worker's `finally` from re-disabling buttons of a newer run. `verificar_url` catches `DescargaCancelada` → `restriccion={"tipo": "cancelada"}`.
- Parallel queue: pref `max_paralelas` (1–3, default 1); `_procesar_cola` uses `ThreadPoolExecutor` when >1, `_procesar_item` handles one item.
- Anti-hang: `_opciones_base()` (used by `verificar_url`) forces `noplaylist=True`, `socket_timeout=TIMEOUT_RED` (20 s), `sleep_interval_requests=1`, `extractor_retries=3`.
- Auth: optional `cookiesfrombrowser` session (`detectar_navegadores()`/`navegadores_cacheados()` + `construir_opciones_cookies()`); **no credentials ever stored**. `bot` is resolved by exhausting `CLIENTES_FALLBACK_BOT` + detected browsers (never by cookies-only). `verificar_url` retries clients **and** browsers on `bot`/`cookies` (via `_intentos_fallback_verificacion`). Session retry is driven by `TIPOS_CUENTA` (`private`/`members_only`/`age_restricted`/`sign_in`) plus `cookies`; on those (in `_procesar_item`, even with the session pref on) auto-retry iterates **every** detected browser via `navegadores_para_reintento(pref, detectados)` — pref first if detected, otherwise `NAVEGADORES_COMPATIBLES_ABIERTOS` (Gecko: Zen/Firefox/Waterfox/LibreWolf, read while open) first, then detection order — and skips to the next silently; it stops at the first success or non-`cookies` error. A locked cookie DB (`Could not copy ... cookie database`) is classified as `cookies`; its suggestion makes "close the browser completely" the last resort and notes Firefox needs no closing. Cookies that cannot be DECRYPTED (`failed to decrypt with DPAPI` / app-bound encryption, Windows Chromium) are also `cookies` (`es_error_cookies_descifrado` + `_ERROR_COOKIES_DESCIFRADO_REGEX`): closing the browser does NOT fix it, the suggestion says to use a Gecko browser or disable the session, and `navegadores_para_reintento(pref, detectados, solo_gecko=True)` restricts the retry ladder to Gecko (`NAVEGADORES_GECKO`) — `_procesar_item` and `VentanaDiagnostico` pass `solo_gecko` from `es_error_cookies_descifrado`. Impersonation is conditional: `_impersonacion_disponible()` (cached try-import of `curl_cffi`) gates `impersonate="chrome"` in `_intentos_fallback_verificacion`/`_intentos_fallback_descarga` (without it yt-dlp raises `YoutubeDLError`, not `DownloadError`, which died silently). CI has a Windows guard step (`Verify curl_cffi bundled`) failing the build if `_internal/curl_cffi/*.pyd` is missing. `_descargar_fallback_bot` tries clients then browsers and propagates the **last real classified error** (was `except: continue`). Prefs `usar_sesion_navegador`/`navegador`/`navegadores_detectados` (cache scanned once).
- Browser support (v3.7.3): Chromium family by name (`chrome`/`edge`/`brave`/`vivaldi`/`opera`); Gecko (Firefox + forks `zen`/`waterfox`/`librewolf`) read via `("firefox", <perfil>, None, None)` because **yt-dlp does not know `zen`/`waterfox`/`librewolf` by name**. `perfil_gecko()` resolves the real profile (parses `profiles.ini` or scans `Profiles/`) and picks the newest `cookies.sqlite` — never assumes `Default`. `ORDEN_NAVEGADORES` is Gecko-first (Chromium forks break on modern Windows: DPAPI/`secretstorage`). x86_64 only matters for the runner, not the logic.
- Dialogs: `lift()` in `__init__` fails silently before a Toplevel is mapped → both `VentanaDiagnostico` and `VentanaActualizacion` use `transient(self.master)` + `self.after(120, self._encima)` (`deiconify`+`lift`+`focus_force`+`-topmost` for 300 ms). Same trap applies to any new dialog.
- TikTok: needs `yt-dlp[default,curl-cffi]>=2026.8.19` (requirements) + `curl_cffi` hiddenimports in the spec (impersonation); the classifier maps extraction/impersonation errors to a friendly `extractor` message.
- Privacy: pref `ocultar_urls` (default ON) + `enmascarar_url()` masks URLs in queue/diagnostics/history/copy; error logging goes through `_registrar_error` with sanitized detail.
- Deliberately reverted (2026-10-18, at user request): the whole v3.4.x line (audio/subtitle language selectors, embedded subtitles, tmpdir "sin restos", `[id]` suffix on all platforms). **Do not re-apply it from git history without asking** — it caused issues #1/#2 and the root cause was never confirmed. Exception approved by the user in v3.8.1: `core_tests/pre_release_check.py` was recreated **from scratch** (not cherry-picked from v3.4.x) and only checks, it does not change the app's download behaviour.
- Also removed in v3.8.0 (at user request): the v3.5.0 "pistas de audio adicionales" feature (YouTube additional audio tracks / doblajes) — `normalizar_pistas_audio`, `nombre_pista_seguro`, `es_audio_original`, `soporta_pistas_audio`, the `format_id`/`pista_label`/`tmpfile_callback` params, the `pistas_audio` UI section, the `tipo="pista_audio"` queue items and `PLAN_UPDATE_PISTAS_AUDIO_ADICIONALES.md`. **Do not re-apply it from git history without asking.** v3.8.0 = v3.3.2's download/subtitle behaviour + v3.6.x auto-update + v3.7.x responsive UI/session handling.
- Skills live in `.opencode/skills/` and are indexed in `SKILLS_PROYECTO.md` (loaded via `.opencode/opencode.json`); invoke by exact name via the `skill` tool. Restart opencode after changing `.opencode/`.

## Notes

- Filename typo `dowloader` (missing 'n') is intentional — it matches the PyInstaller spec output name. Do not rename without updating the spec.
- UI is 100% Spanish; input hints in sentence case ("Pega una URL para empezar", "URL no compatible · …").
- `GITHUB_REPO` in `core.py:13` must match the actual GitHub repo path or auto-update breaks. Auto-update (v3.6.0+) downloads the release asset, verifies it against `SHA256SUMS` (`verificar_sha256`), and runs `comando_actualizacion` (silent NSIS / `pkexec dpkg` / opens the .dmg). v3.5.0 and earlier installs have **no** auto-update — they must be upgraded manually once.
- `MEMORY.md` is the versioned session checkpoint: read it before starting (it also holds CustomTkinter 6.0.0 widget quirks — `CTkEntry.bind` only fires on the inner `_entry`, `cola_scroll`/root use `grid` not `pack`) and update it on the final commit of a release batch.
- `bfg-*.jar` files are BFG Repo-Cleaner (git-history secret purging), not part of the app. They appear in `.gitignore` but are still **tracked in git** (`git rm --cached` was never run) — don't reference them from code or the spec.
- Open security items (2026-09-14 audit): **SEC-03** — anchor `PLATFORM_REGEX`/`extraer_url_completa` to the real host (substring matching currently accepts `youtube.com.evil.example`); **SEC-04** — `os.chmod(CONFIG_FILE, 0o600)` on save (the "validate `saved` is a dict on load" half is **already done** in `cargar_preferencias`, `core.py:580`). SEC-05 (`cookiesfrombrowser`) needs no change.
