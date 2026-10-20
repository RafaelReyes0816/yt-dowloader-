# AGENTS.md

## Communication

Reply to the user **in Spanish** (explanations, plans, questions, commit messages). Code identifiers stay English; UI strings are Spanish.

## Project overview

Python desktop app: CustomTkinter UI (`yt-dowloader.py`) + pure logic (`core.py`) on yt-dlp. Downloads mp3/mp4 from 8 platforms (YouTube, Instagram, Facebook, TikTok, Twitch, Vimeo, Twitter/X, Reddit) with quality selection, a cancellable optionally-parallel queue, browser-session auth, and auto-update via GitHub Releases.

## Repo quirks

- Repo path contains **spaces** (`.../Proyectos web/yt-dowloader-`) — quote paths in shell commands.
- A `.venv/` with dev deps already exists (pytest, customtkinter 6.0.0, yt-dlp 2026.8.19, pyinstaller, curl_cffi). Prefer `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/pyinstaller`. Pillow is NOT in the venv (only used for the window icon, wrapped in `try/except`) — install `requirements.txt` if you need it.
- No linter/formatter/typecheck is configured. Verification = pytest + `py_compile`.
- The entry module has hyphens (`yt-dowloader.py`) and cannot be imported by name; tests only import `core`/`theme`. Run the app as a script.

## Run

```bash
pip install -r requirements.txt   # or: requirements-dev.txt (adds pytest)
python yt-dowloader.py
```

System deps: `ffmpeg` on PATH (mp3 conversion + mp4 muxing). Debian/Ubuntu: `sudo apt install python3-tk` if tkinter is missing. Download target `Mi_musica/` is created at runtime.

## Tests

```bash
.venv/bin/python -m pytest                # offline suite: 220 passed, 16 live deselected (v3.6.2)
.venv/bin/python -m pytest core_tests/test_core.py -k <nombre> -q   # single test
.venv/bin/python -m py_compile yt-dowloader.py core.py theme.py     # syntax check (run before committing)
```

- `pytest.ini` sets `testpaths = core_tests`, `pythonpath = .`, `addopts = -m "not live"` → live tests are skipped by default and **CI only runs this offline suite** (on Linux, before `pyinstaller`; failure blocks the release).
- Live suite: `core_tests/test_plataformas_live.py` — 16 tests over 8 real public URLs, marked `@pytest.mark.live`. Run manually only when needed: `.venv/bin/python -m pytest core_tests/test_plataformas_live.py -m live -v`. No CI job.
- CI cannot catch real-download bugs — the AV1/VLC regression shipped that way. Before tagging a release, manually verify one real mp3 + one mp4 download (expect `h264/avc1` + `aac` in the mp4).

## Build standalone executable

```bash
pyinstaller yt-dowloader.spec    # output in dist/
```

Spec is **multiplatform** (no `target_arch`; PyInstaller autodetects). Its `hiddenimports` must keep `curl_cffi`/`curl_cffi.requests` (TikTok impersonation) and it bundles CustomTkinter data files.

## Release flow

1. Bump `__version__` (line 2 of `yt-dowloader.py`). Commit style: `feat vX.Y.Z: ...` / `fix vX.Y.Z: ...` (message in Spanish).
2. Verify: pytest + py_compile (+ the manual real-download check above).
3. `git tag vX.Y.Z && git push origin vX.Y.Z` — push **the tag itself**; lightweight tags are not pushed by `--follow-tags`.
4. Tag `v*` triggers `.github/workflows/build.yml`: builds Linux/Windows/macOS (Python 3.12), runs the offline suite on Linux, packages NSIS `.exe` + portable zip, `.deb` + tar.gz, `.dmg` + `.app` zip (Windows CI bundles `ffmpeg.exe`/`ffprobe.exe`), publishes via `softprops/action-gh-release`. Also runnable manually via `workflow_dispatch`.
5. Update `MEMORY.md` on the final commit of the batch (its header states the rule: version, commit/tag hash, CI status, test count).

Note: `core_tests/pre_release_check.py` (automated pre-release E2E download) existed in v3.4.x and was **removed in the 2026-10-18 revert** — recreate it if you want that automation back.

## Architecture

- `core.py` — pure business logic, **no UI/network on import** (testable): `PLATFORM_REGEX`, `extraer_url_completa`, `detectar_plataforma`, `ClasificadorErrores` (yt-dlp errors → friendly Spanish + `detalle` field, sanitized via `sanitizar_detalle`), `verificar_url(url, navegador=None, cancel_flag=None)`, `extraer_info_video`, `descargar_musica(..., cancel_flag, ydl_holder, postprocessor_callback)`, `find_ffmpeg`, prefs load/save, `comparar_versiones`, `check_for_update()` (GitHub Releases) + `obtener_ultima_version_ytdlp()` (PyPI), `PLATAFORMAS_CONFIG`, `RESOLUCIONES_YOUTUBE`, `RESOLUCIONES_GENERICAS`, `CALIDADES_AUDIO`/`CALIDADES_VIDEO` (**the UI must not hardcode qualities**), `TIMEOUT_RED`, `ORDEN_NAVEGADORES`.
- `yt-dowloader.py` — UI: `App`, `VentanaDiagnostico`, `QueueCard`, `SegmentedControl`, `PillToggle`, `Annunciador` (transient HUD), `SpinnerRing`. **All UI updates must go through `self.after(0, ...)`** — Tkinter is not thread-safe; worker threads never touch widgets directly.
- `theme.py` — design tokens (colors/fonts/radii) + `GLYPHS`.
- YouTube selectors (do NOT "simplify" — `RESOLUCIONES_YOUTUBE` in `core.py:161-168`): 360p–1080p prefer H.264 `[vcodec^=avc1]` + AAC `[ext=m4a]` with plain-mp4 fallback, because yt-dlp defaults to AV1/VP9 which VLC/WMP cannot open inside mp4 (GitHub issues #1/#2, "VLC es incapaz de abrir el MRL"). **1440p/2160p must NOT use `[ext=mp4]` or the avc1 filter** — 2K/4K are only served as VP9/AV1.
- Filenames: YouTube uses `%(title)s [%(id)s].%(ext)s` (uniqueness); other platforms `%(title)s.%(ext)s`.
- Cancel: `cancel_flag` (`threading.Event`) is checked in **both** the progress hook and the postprocessor hook (convert phase is cancellable); `ydl_holder` exposes the active `YoutubeDL` for an immediate stop; `_limpiar_cola` hard-aborts items via `_cancelar_item_fuerte`, and `_cola_run_id` stops a stale worker's `finally` from re-disabling buttons of a newer run. `verificar_url` catches `DescargaCancelada` → `restriccion={"tipo": "cancelada"}`.
- Parallel queue: pref `max_paralelas` (1–3, default 1); `_procesar_cola` uses `ThreadPoolExecutor` when >1, `_procesar_item` handles one item.
- Anti-hang: `_opciones_base()` (used by `verificar_url`) forces `noplaylist=True`; verify + download set `socket_timeout=TIMEOUT_RED` (20 s).
- Auth: optional `cookiesfrombrowser` session (`detectar_navegadores()` + `construir_opciones_cookies()`); **no credentials ever stored**. Auto-retry once with the first detected browser (`ORDEN_NAVEGADORES`: firefox > chrome > brave > edge) on private/sign_in/bot/age_restricted/members_only/cookies errors when the session pref is off. Prefs `usar_sesion_navegador`/`navegador`.
- Diagnostics window: `lift()` in `__init__` fails silently before a Toplevel is mapped → `VentanaDiagnostico` uses `transient(self.master)` + `self.after(120, self._encima)` (`deiconify`+`lift`+`focus_force`+`-topmost` for 300 ms). Same trap applies to any new dialog.
- TikTok: needs `yt-dlp[default,curl-cffi]>=2026.8.19` (requirements) + `curl_cffi` hiddenimports in the spec (impersonation); the classifier maps extraction/impersonation errors to a friendly `extractor` message.
- Privacy: pref `ocultar_urls` (default ON) + `enmascarar_url()` masks URLs in queue/diagnostics/history/copy; error logging goes through `_registrar_error` with sanitized detail.
- Deliberately reverted (2026-10-18, at user request): the whole v3.4.x line (audio/subtitle language selectors, embedded subtitles, tmpdir "sin restos", `[id]` suffix on all platforms, `pre_release_check.py`). **Do not re-apply it from git history without asking** — it caused issues #1/#2 and the root cause was never confirmed. v3.5.0 re-added a *different* feature (YouTube additional audio tracks / doblajes, `pista_label`/`tmpfile_callback` params) — that one is intentional and stays.
- Skills live in `.opencode/skills/` and are indexed in `SKILLS_PROYECTO.md` (loaded via `.opencode/opencode.json`); invoke by exact name via the `skill` tool. Restart opencode after changing `.opencode/`.

## Notes

- Filename typo `dowloader` (missing 'n') is intentional — it matches the PyInstaller spec output name. Do not rename without updating the spec.
- UI is 100% Spanish; input hints in sentence case ("Pega una URL para empezar", "URL no compatible · …").
- `GITHUB_REPO` in `core.py` must match the actual GitHub repo path or auto-update breaks. Auto-update (v3.6.0+) downloads the release asset, verifies it against `SHA256SUMS` (`verificar_sha256`), and runs `comando_actualizacion` (silent NSIS / `pkexec dpkg` / opens the .dmg). v3.5.0 and earlier installs have **no** auto-update — they must be upgraded manually once.
- `MEMORY.md` is the versioned session checkpoint: read it before starting (it also holds CustomTkinter 6.0.0 widget quirks — `CTkEntry.bind` only fires on the inner `_entry`, `cola_scroll`/root use `grid` not `pack`) and update it on the final commit of a release batch.
- `bfg-*.jar` files are BFG Repo-Cleaner (git-history secret purging), not part of the app. They appear in `.gitignore` but are still **tracked in git** (`git rm --cached` was never run) — don't reference them from code or the spec.
- Open security items (2026-09-14 audit): **SEC-03** — anchor `PLATFORM_REGEX`/`extraer_url_completa` to the real host (substring matching currently accepts `youtube.com.evil.example`); **SEC-04** — `os.chmod(CONFIG_FILE, 0o600)` on save and validate `saved` is a dict on load. SEC-05 (`cookiesfrombrowser`) needs no change.
