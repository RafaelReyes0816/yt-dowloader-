# MEMORY.md — Memoria de sesión (borrable cuando no haga falta)

> Resumen para retomar el trabajo **sin re-descubrir** lo de hoy. Reusa la estructura de `AGENTS.md` y `SKILLS_PROYECTO.md` y el approach *red → green → refactor*. Este archivo es **temporal**: se puede borrar del workspace cuando se quiera. No está en git (no se committed).

> ⚠️ **REGLA OBLIGATORIA:** cada vez que se haga **el commit final de una tanda de cambios y se lance la build/release**, actualizar este `MEMORY.md` ANTES de cerrar sesión: bump de `__version__`, hash del commit/tag, estado de la build (CI), conteo de tests y cualquier detalle nuevo (quirks, decisiones, pendientes abiertos). Si no se actualiza, la próxima sesión arranca con contexto desincronizado y se pierde trazabilidad.

---

## 0. Stack y cómo arrancar

- Proyecto: `/home/rafaelreyes/Documentos/Proyectos web/yt-dowloader-` (ruta con **espacios**: usar quotes en bash). Responder al usuario **en español**.
- **Usar `grep`** (prohibido `rg` en esta sesión).
- Ejecutar: `pip install -r requirements.txt && python yt-dowloader.py`
- Dependencia de sistema: `ffmpeg` en PATH (mp3/mp4). Debian: `sudo apt install python3-tk`.

## 1. Checkpoint — dónde estamos

- **Última release: v3.3.1** (commit `2cb32a8`, tag `v3.3.1` pusheado a `master` de GitHub, repo `RafaelReyes0816/yt-dowloader-`). El CI de GitHub Actions (`.github/workflows/build.yml`) se dispara en tag push `v*` y publica ejecutables de Linux/Windows/macOS con `softprops/action-gh-release`. **CI v3.3.1: `success`, release publicada** con `yt-dowloader-linux.{deb,tar.gz}`, `yt-dowloader-macos.{dmg,zip}`, `yt-dowloader-windows-portable.zip` y `YT-DownLoader-Jaeger-Setup.exe`.
- **Tests: 133 unitarios verdes** (`core_tests/test_core.py`; 127 previos + 6 nuevos de anti-hang y cancel en postproceso) + **16 live verdes** (8 plataformas × verificación + detección). `py_compile` OK y smoke UI (`/tmp/opencode/smoke_bugs.py`) → `SMOKE OK`.
- **INCLUIDO EN v3.3.1 (2026-09-15):**
  - **(1) Anti-hang** — `socket_timeout=TIMEOUT_RED` (20s) en verificación y descarga + `_opciones_base` fuerza `noplaylist=True` (la verificación ya NO crawlea una playlist completa; antes podía colgarse para siempre).
  - **(2) Cancel también aborta en postproceso** — `postprocessor_hook` chequea `cancel_flag` (antes la conversión ignoraba la cancelación y el botón quedaba atascado en "Descargando"). `_limpiar_cola` ahora aborta fuerte (`_cancelar_item_fuerte` = flag + `ydl._download_retcode`) + `stop_all` y resetea botones al instante. Guard anti-carrera `_cola_run_id`: el `finally` de un worker viejo no pisa los botones de una corrida nueva.
  - **(3) `VentanaDiagnostico` se abre encima** — `transient(master)` + `_encima()` diferido 120 ms (`deiconify`+`lift`+`focus_force`+`-topmost` 300 ms). Llamar `lift()` en `__init__` antes de que la ventana esté mapeada falla en silencio → se abría detrás de la ventana principal.
- **Fases 0–3 completadas** (seguridad → validación/privacy → UX/limpieza). Nada pendiente de implementar excepto los "open items" de seguridad (sección 6).
- `__version__ = "3.3.1"` en **`yt-dowloader.py:2`**. `GITHUB_REPO = "RafaelReyes0816/yt-dowloader-"` en `core.py:10` (debe coincidir con el remoto o el auto-update del GITHUB_REPO no funciona).

## 2. Arquitectura (mapa mental rápido)

- **`core.py`** — Lógica pura, **sin UI ni network en import** (testable). Piezas clave: `PLATFORM_REGEX`, `extraer_url_completa` (extrae URL completa —query strings, paréntesis y puntuación limpiados— desde texto/portapapeles), `detectar_plataforma`, `ClasificadorErrores` (errores → mensaje amigable ES + `detalle` sanitizado), `verificar_url(url, navegador=None, cancel_flag=None)` (devuelve `restriccion={"tipo":"cancelada"}` si cancelan), `extraer_info_video`, `descargar_musica(..., cancel_flag, ydl_holder, postprocessor_callback)`, `find_ffmpeg`, prefs load/save, `comparar_versiones`, `elegir_navegador_sesion`, `obtener_ultima_version_ytdlp`, `check_for_update`, `PLATAFORMAS_CONFIG`, `RESOLUCIONES_YOUTUBE`, `RESOLUCIONES_GENERICAS`, y **`CALIDADES_AUDIO`/`CALIDADES_VIDEO` (v3.3: la UI ya NO hardcodea calidades; las lee de core)**, `TIMEOUT_RED` (v3.3.1: `socket_timeout` 20s en verificación+descarga, `noplaylist=True` forzado en `_opciones_base`)**. `Mi_musica/` se crea en runtime como destino de descargas.
- **`yt-dowloader.py`** — UI CustomTkinter. Clases: `App` (raíz), `VentanaDiagnostico`, `QueueCard`, `SegmentedControl`, `PillToggle`, `Annunciador` (HUD transitorio), `SpinnerRing` (anillo animado). Guard anti-carrera `_cola_run_id` (el `finally` del worker solo resetea botones si `run_id == self._cola_run_id`). Módulo con **guiones en el nombre** → importarlo por `importlib` o ruta (no `import yt_dowloader`). Smoke test de bugs 2026-09-15 (`/tmp/opencode/smoke_bugs.py`) → `SMOKE OK` (agregar, diagnostico encima, limpiar resetea botón).
- **`theme.py`** — Design tokens (colores/fuentes/radios) + `GLYPHS`. `Annunciador`/`SpinnerRing` resuelven todo el feedback visual; todas las actualizaciones de UI van por `self.after(0, ...)` (threading seguro).
- Plataformas (v3.0+): YouTube, Instagram, Facebook, TikTok, Twitch, Vimeo, Twitter/X, Reddit. Filenames: YouTube = `%(title)s [%(id)s].%(ext)s`; resto = `%(title)s.%(ext)s`.

## 3. Comandos de verificación (siempre antes de commitear)

```bash
.venv/bin/python -m pytest core_tests/test_core.py -m "not live" -q      # 133 passed
.venv/bin/python -m py_compile yt-dowloader.py core.py theme.py          # OK
.venv/bin/python -m pytest core_tests/test_plataformas_live.py -m live -v  # 16 passed (solo si hace falta, golpe a red real)
```

- `pytest.ini`: `addopts = -m "not live"`, `testpaths = core_tests` → el **CI corre el default (nunca live)**; un fallo bloquea la release.
- Smoke UI (require pantalla): `python /tmp/opencode/smoke_ui.py /ruta/yt-dowloader.py`.
- Smoke bugs 2026-09-15 (anti-hang, limpiar, diagnostico): `python /tmp/opencode/smoke_bugs.py` → `SMOKE OK`.

## 4. Los 6 pasos clave de la técnica red→verde→refactor (la que nos llevó hasta v3.3.0)

Para **cualquier cambio futuro**, seguir este loop (no perderlo; es lo que mantiene lógica != UI y todo testeado):

1. **RED — escribir primero el test que falla** en `core_tests/test_core.py` sobre `core.py` (lógica pura, sin UI). Nombrar bien el test (ej: `TestConstantesCalidades`, `TestPrefsLimpiaTema`). Correr `.venv/bin/python -m pytest -k <test>` → ver que falla por el motivo correcto.
2. **GREEN — implementación mínima** en `core.py`/`yt-dowloader.py` hasta que pase. **Nada de UI/red en import de `core.py`** (si se necesita network/cancel, parametrizar: `cancel_flag`, `ydl_holder`, `postprocessor_callback`).
3. **REFACTOR — consolidar después de verde**: mover constantes a `core.py` (la UI no hardcodea), purgar legacy (claves viejas de prefs), unificar patrones repetidos (spinners → `_pintar_anillo(canvas, cx, cy, r, width, angle, color, con_fondo=True)`), borrar código muerto (`ACCION_BOTON` fue eliminado).
4. **VERIFY — suite completa**: 133 tests + `py_compile`. Si el cambio toca UI, smoke test; si toca plataformas, live tests manuales.
5. **REGISTER — commit + tag + push y PROBAR el ciclo completo una vez más antes de la release** (la suite actual tiene 133 tests verdes; recordar que un tag *lightweight* NO sube con `--follow-tags` → subirlo con `git push origin tag vX.Y.Z`).
6. **UPDATE — actualizar `MEMORY.md` en el commit final / tras la build** (ver regla al inicio): nuevo `__version__`, hash del commit/tag, resultado de CI, nº de tests y pendientes/quirks nuevos. Esto evita arrancar la próxima sesión con contexto desincronizado.

## 5. Detalles críticos de customtkinter 6.0.0 (costaron el smoke test)

- `CTkEntry.bind(<evento>, cb)` NO se aplica al widget exterior: **reenvía al Entry interno** (`_entry`). Para `event_generate` apuntar a `url_entry._entry` (el widget externo es un `Frame`). Los binds SÍ funcionan con eventos reales.
- `QueueCard.__init__(self, master, url, plataforma, modo, on_cancel=None, on_retry=None, on_remove=None, ocultar_urls=False, **kwargs)` — el label de la URL es **`url_label`** (no `_link_label`).
- `VentanaDiagnostico.__init__(self, master, url="", navegador="")` — **no** tiene kwarg `ffmpeg_ok`.
- `cola_scroll` (lista de cola) y la raíz de `App` usan **`grid`**, no `pack`.
- **VentanaDiagnostico encima (2026-09-15)**: `lift()`/`focus_force()` en `__init__` NO suben la ventana si aún no está mapeada (falla en silencio) → `self.transient(self.master)` + `self.after(120, self._encima)` (`deiconify`+`lift`+`focus_force`+`-topmost` True, luego `_quitar_topmost` a los 300 ms vía `_guard_after`).
- **Cancel + limpiar (2026-09-15)**: `_limpiar_cola` hace `self._cola_run_id += 1` + `stop_all.set()` + aborto fuerte de cada item (`_cancelar_item_fuerte`) y resetea botones al instante (sin esperar al worker). El `finally` de `_procesar_cola`/`_reintentar_item` solo resetea botones si `run_id == self._cola_run_id`.
- **Anti-hang (2026-09-15)**: verificación y descarga llevan `socket_timeout=TIMEOUT_RED` (20s); `_opciones_base` fuerza `noplaylist=True` para que `verificar_url` no recorra playlists completas. `postprocessor_hook` aborta (lanza `DescargaCancelada`) si `cancel_flag` está activo → la fase de conversión también es cancelable.

## 6. Seguridad — estado de la auditoría 2026-09-14

- **Mitigado (v3.3)**: SEC-01 (`config.json` URLs planas → pref `ocultar_urls` ON + `enmascarar_url()`/`enmascarar_texto()` en tarjetas/diagnóstico/historial/copy) y SEC-02 (`detalle` crudo → `sanitizar_detalle(detalle, url)` antes de mostrar; `_registrar_error` registra con detalle saneado).
- **Abiertos (SIGUEN SIN HACER)**: **SEC-03** — anclar `PLATFORM_REGEX`/`extraer_url_completa` al host real (hoy por subcadena acepta `youtube.com.evil.example`). **SEC-04** — `os.chmod(CONFIG_FILE, 0o600)` al guardar preferencias y validar que `saved` sea `dict` al cargar.
- **Sin cambio**: SEC-05 (`cookiesfrombrowser`) — no se almacenan credenciales.
- Fuera de código: `bfg-*.jar` para purgar historial (ignorados por `.gitignore`); el seguro vino del informe eliminado de `security_best_practices_report.md` (hallazgos plegados en AGENTS.md).

## 7. Skills del proyecto (`.opencode/skills/` — invocar por nombre exacto con la herramienta `skill`)

- `security-best-practices`, `tdd` (red→green→refactor, mocking.md, tests.md), `frontend-design`, `web-design-guidelines`. Índice en `SKILLS_PROYECTO.md`. Config `.opencode/opencode.json` (instructions = `AGENTS.md` + `SKILLS_PROYECTO.md`, `skills.paths = [".opencode/skills"]`).
- Nota: **reiniciar opencode** para que cargue `.opencode`. El resto del catálogo (infosec) vive en `~/.agents/skills` y `~/.claude/skills` (auto-load).
- TDD skill: antes de codear, leer `CONTEXT.md` si existe para que nombres de tests calcen con el dominio del proyecto.

## 8. Reglas de estilo / convenciones del repo

- UI **100% en español**, hints en sentence case ("Pega una URL para empezar", "URL no compatible · …", "Ya está en cola").
- Tipó de nombre `dowloader` (sin 'n') es **intencional** (spec de PyInstaller): no renombrar sin actualizar `yt-dowloader.spec`.
- `yt-dowloader.spec` es multiplataforma (sin `target_arch`), incluye hiddenimports `curl_cffi`/`curl_cffi.requests` (fix TikTok v3.1: yt-dlp >= 2026.8.19 con `[default,curl-cffi]`).
- Calidad YouTube: 360p–1080p con `[ext=mp4]`; 1440p/2160p **sin** `[ext=mp4]` (solo VP9/AV1).
- Cancel: `cancel_flag` (threading.Event) + `ydl_holder` (dict); paralelismo opcional `max_paralelas` (1–3) con `ThreadPoolExecutor`; toda UI update va por `self.after(0, ...)`.
- Git commit style: `feat vX.Y.Z: ...` / `fix ...` (español). Remoto: `origin` = `https://github.com/RafaelReyes0816/yt-dowloader-.git`.

## 9. Próximos pasos lógicos (si se retoma)

1. **SEC-03** (regex de plataforma anclada al host) con tests (red→green→refactor, pasos de la sección 4).
2. **SEC-04** (`chmod 0600` + validar `saved` dict) con test de redondeo de prefs.
3. Si aplica: smoke test GUI de nuevo tras esos cambios (`/tmp/opencode/smoke_ui.py`).
4. **v3.3.1 YA LANZADA** (2026-09-15, CI success, assets publicados) — ver sección 1. Próxima release tras SEC-03/SEC-04: bump a v3.3.2/v3.4.0 y **tag + push EXPLÍCITO del tag** (`git push origin vX.Y.Z`; recordar lección de `--follow-tags`).
5. **NO cerrar la sesión sin actualizar `MEMORY.md`** con el estado final (versión, commit/tag, CI, tests) — la regla obligatoria del inicio de este archivo.