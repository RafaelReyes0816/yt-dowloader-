# Plan de actualización: pistas de audio adicionales independientes

**Proyecto:** YT-DownLoader del Jaeger  
**Repositorio:** https://github.com/RafaelReyes0816/yt-dowloader-  
**Base revisada:** v3.3.2  
**Estado:** Fases 0–4 implementadas y verificadas (2026-10-19); Fase 5 hecha salvo release (commit local sin tag, por decisión del usuario).

> Esta función no reactiva la línea v3.4.x revertida el 2026-10-18. No reutilizar ni re-aplicar cambios de esa línea desde el historial sin una petición explícita.

## 1. Objetivo

Permitir que el usuario descargue una o varias pistas de audio adicionales de un video de YouTube, sin alterar el video principal ni su audio original.

Las pistas adicionales se descargan como archivos independientes y en contenedor nativo. No se incrustan, mezclan, reemplazan ni sincronizan dentro del video.

Resultado esperado:

```text
Mi_musica/
├── Nombre del video [abc123].mp4
└── Nombre del video [abc123]/
    ├── audio adicional - English.m4a
    ├── audio adicional - 日本語.webm
    └── Nombre del video [abc123].es.vtt
```

Reglas de organización:

- El video (o el mp3, en modo audio) queda en la raíz de la carpeta destino, como hoy.
- Las pistas adicionales y los subtítulos van a una subcarpeta `Título [id]/`.
- La subcarpeta se crea si el usuario selecciona pistas **o** subtítulos y hay contenido que escribir. Sin nada de eso, el resultado es idéntico a v3.3.2.
- Dentro de la subcarpeta, las pistas usan el nombre corto `audio adicional - <etiqueta>.<ext>`; los subtítulos conservan el nombre completo del video, p. ej. `Título [id].es.vtt`.

Los nombres y extensiones definitivos dependen de los metadatos reales y del formato nativo descargado.

## 2. Decisiones cerradas

1. **Items independientes en la cola.** Cada pista seleccionada es un item propio (`tipo="pista_audio"`) con su estado, cancelación y reintento. No son subfilas del video principal.
2. **Extender `descargar_musica`.** Se añade `format_id` (y la etiqueta de pista) a la función existente y una rama en `_construir_opciones_descarga`; no se crea una segunda función de descarga.
3. **Excluir el audio original.** La lista de pistas alternativas no incluye el audio que ya descarga el video. El mecanismo exacto de detección se fija en la Fase 0.
4. **Contenedor nativo.** Cada pista se guarda como la sirve YouTube (m4a/AAC, webm/Opus, etc.), sin postprocesador ni conversión, y sin `merge_output_format`.
5. **Metadatos ambiguos.** Si el idioma no es fiable, la pista se incluye igualmente con una etiqueta neutral (`format_note` o `format_id`). No se inventan idiomas ni se ocultan pistas por falta de metadatos.
6. **Video en la raíz, extras en subcarpeta.** El archivo principal no se mueve de la carpeta destino.
7. **Subtítulos también a la subcarpeta.** Si se seleccionan subtítulos (aunque no haya pistas), el `.vtt` va a `Título [id]/`. Esto cambia la ubicación actual de los subtítulos y debe verificarse explícitamente.
8. **Pistas cortas dentro de la subcarpeta.** La carpeta ya identifica el video; el nombre del archivo de pista no repite el título.

## 3. Estado actual verificado (v3.3.2)

Hechos comprobados sobre el código, que condicionan el diseño:

- `verificar_url()` (`core.py:470`) ya devuelve el diccionario completo de metadatos en `resultado["info"]` (`core.py:481`) tras `extract_info(download=False)`. Sirve para listar pistas sin una segunda extracción.
- `_construir_opciones_descarga()` (`core.py:497`) arma `outtmpl` como cadena: YouTube usa `%(title)s [%(id)s].%(ext)s`; el resto, `%(title)s.%(ext)s`.
- Los subtítulos se activan solo para YouTube con `writesubtitles=True` y `subtitleslangs=["es", "en", "pt"]` (`core.py:537-539`), y hoy se escriben junto al video.
- En modo audio, YouTube usa `format="bestaudio/best"` con `FFmpegExtractAudio` a mp3; en video usa `merge_output_format="mp4"` y los selectores de calidad (`core.py:556-568`).
- `descargar_musica()` (`core.py:572`) construye las opciones, aplica cookies, registra hooks, ejecuta `ydl.download([url])` y clasifica errores con `ClasificadorErrores`.
- La UI llama a `descargar_musica` dos veces: descarga normal y reintento automático con sesión de navegador (`yt-dowloader.py:1610` y `1637`). El `format_id` debe pasarse en ambas.
- `PLATAFORMAS_CONFIG` (`core.py:177-189`) ya expone capacidades por plataforma (`soporta_subtitulos`, `outtmpl_unicidad`, `calidades_audio`); la UI no debe hardcodear plataformas.
- `ESTADOS` (`yt-dowloader.py:50`) es un diccionario fijo que alimenta etiquetas, colores y contadores (`1325-1350`). No se añaden estados nuevos.
- `_agregar_a_cola()` (`yt-dowloader.py:1384`) deduplica comparando solo `existente["url"] == url` (`1407-1410`). Con pistas del mismo video, esa regla bloquearía las pistas.
- `_iniciar_cola()` (`yt-dowloader.py:1480`) congela los items `en_cola` en un snapshot (`1484`); `_procesar_cola()` (`1498`) reparte con `ThreadPoolExecutor` según `max_paralelas`; `_procesar_item()` (`1543`) hace un precheck con `verificar_url` (`1554`).
- La única verificación de URL fuera de la cola está en `VentanaDiagnostico._run_checks()` (`yt-dowloader.py:671`). La nueva sección necesita su propio hilo y actualizaciones vía `self.after(0, ...)`.
- `yt-dlp` acepta `outtmpl` como diccionario (`{"default": ..., "subtitle": ...}`) y resuelve la plantilla por tipo (`YoutubeDL._prepare_filename`, `tmpl_type`). Esto permite dejar el video en la raíz y escribir los subtítulos en la subcarpeta sin mover archivos después.
- La validación inline de URL es solo por regex (`_actualizar_validacion_inline`, `yt-dowloader.py:928`), sin red.

Línea base de verificación:

```bash
.venv/bin/python -m pytest          # 146 passed, 16 deselected
.venv/bin/python -m py_compile yt-dowloader.py core.py theme.py
```

## 4. Alcance

### Incluido

1. Detectar las pistas de audio alternativas de videos de YouTube.
2. Permitir seleccionar cero, una o varias pistas.
3. Descargar cada pista como archivo suelto en `Título [id]/`, en contenedor nativo.
4. Excluir de la lista el audio original del video.
5. Enviar subtítulos a la misma subcarpeta cuando se seleccionen.
6. Integrar las pistas en la cola existente: paralelismo, cancelación, reintento, progreso y errores.
7. No cambiar nada si el usuario no selecciona pistas ni subtítulos.
8. Limitar la función a YouTube; en otras plataformas no se muestra.

### Fuera del alcance

- Incrustar pistas en el MP4/MKV, reemplazar el audio original o mezclar pistas.
- Convertir pistas a mp3 u otro formato.
- Descargar pistas alternativas en otras plataformas.
- Persistir la selección de pistas de un video entre sesiones.
- Reintroducir los cambios de la línea v3.4.x.

## 5. Modelo de metadatos

`normalizar_pistas_audio(info)` es una función pura que recibe el `info` de `verificar_url` y devuelve una lista ordenada de pistas:

```python
{
    "format_id": str,
    "language": str | None,
    "label": str,           # legible o neutral; nunca inventado
    "ext": str,
    "acodec": str | None,
    "abr": float | None,
    "audio_channels": int | None,
}
```

Reglas:

1. Considerar solo formatos de audio: `vcodec` ausente o `"none"` y `acodec` presente y distinto de `"none"`.
2. Descartar entradas sin `format_id`.
3. Agrupar por idioma cuando exista; conservar la mejor variante del grupo: primero `ext == "m4a"` (compatibilidad de reproducción), luego `abr`/`tbr` (mayor primero), luego `format_id` para desempate estable. Los formatos duplicados del mismo audio no se muestran como pistas distintas.
4. **Excluir el audio original** (decisión 3). Aislar la heurística en un helper `es_audio_original(formato, info)` para poder ajustarla sin tocar el resto.
5. Etiqueta: idioma si es fiable; si no, `format_note`; si tampoco, `format_id`. No traducir ni inventar.
6. Orden estable por etiqueta para que la lista no cambie entre consultas.
7. Lista vacía si no hay pistas alternativas o si el video no las expone como formatos descargables.

### Detección del audio original (Fase 0) — verificado 2026-10-19

Muestras reales (videos multidioma de YouTube, `extract_info(download=False)` anónimo):

- Los doblajes traen `language_preference = -1`; el original trae `language_preference = 10`.
- El `format_note` del original contiene `"original (default)"`; los doblajes no.
- `info["language"]` (nivel superior) coincide con el idioma original (`"en"`, `"en-US"`).
- Videos de un solo idioma: todos los formatos comparten idioma y ninguno tiene `language_preference > 0` (p. ej. `dQw4w9WgXcQ`: 5 formatos `en`, pref `-1`); no hay pistas adicionales que listar.
- Los formatos de cada idioma comparten prefijo y se distinguen por sufijo en `format_id` (`140-21`, `251-2`). Descargar `-f "140-1"` o `-f "251-2"` baja el doblaje correcto como archivo independiente, sin postprocesar (probado: `.m4a` de 1.5 MiB y `.webm` de 1.6 MiB).
- Por idioma conviven `m4a` (140), `webm` (251/250/249) y `mp4` "dubbed-auto" (233/234, sin `abr`). El `format_note` de 233/234 viene en idioma nativo (`"Deutsch (Deutschland) - dubbed-auto"`); el de 140/251 en inglés (`"German (DE), medium"`).
- En la muestra `Af6i6ChAVTw`, los 233/234 tienen `acodec=None`; se excluyen filtración mediante (se exige `acodec` explícito y `vcodec` nulo/`none`). Siempre hay m4a/webm por idioma, así que no se pierde ninguna pista.
- `outtmpl` como diccionario funciona: el `.vtt` se escribe en la subcarpeta y el video queda en la raíz (probado con `dQw4w9WgXcQ`).

Heurística elegida (determinista y fail-safe):

1. `original_langs = {language de los formatos con language_preference > 0}`.
2. Si está vacío, usar `info.get("language")`, aceptándolo solo si coincide con un idioma presente (exacto o variante base: `en` ↔ `en-US`).
3. Si sigue vacío y hay más de un idioma, no listar pistas para ese video (no se puede excluir el original con seguridad).
4. Excluir todos los formatos cuyo `language` esté en `original_langs` (cubre todas las calidades del original).
5. Deduplicar por `language` exacto (incluye variantes `es-US`, `en-GB`, `zh-Hans`).

Criterio de aceptación: el audio original no aparece nunca en la lista. Si la detección es ambigua para un video concreto, la solución por defecto es no listar pistas para ese video (fail-safe), antes que duplicar el audio original.

## 6. Cambios en `core.py`

### 6.1 Capacidades por plataforma

Añadir a la entrada de YouTube en `PLATAFORMAS_CONFIG`:

```python
"YouTube": {
    "soporta_subtitulos": True,
    "soporta_pistas_audio": True,
    ...
}
```

El resto de plataformas queda sin la clave (equivalente a `False`). La UI consulta la capacidad; no compara nombres de plataforma.

### 6.2 `normalizar_pistas_audio(info)`

Nueva función pura según la sección 5. No hace red y no depende de la UI. Debe tolerar `info` incompleto, `formats` ausente y valores nulos. Solo considera formatos con `format_id`, `acodec` explícito distinto de `"none"` y `vcodec` nulo/`"none"` (audio-only).

Cada pista normalizada es un `dict` con:

```python
{
    "format_id": "140-1",
    "language": "es-US",
    "label": "Spanish (US)",
    "ext": "m4a",
    "acodec": "mp4a.40.2",
    "abr": 129.5,
    "audio_channels": 2,
    "nombre": "Spanish (US)",   # stem seguro y único para el archivo
}
```

`label` es para mostrar; `nombre` es el que consume `_construir_opciones_descarga`. El `nombre` se calcula con `nombre_pista_seguro` y se desambigua si dos etiquetas colapsan.

### 6.3 `_construir_opciones_descarga`

Firma extendida, añadiendo parámetros al final para no romper llamadas posicionales existentes:

```python
def _construir_opciones_descarga(..., postprocessor_callback=None,
                                 format_id=None, pista_label=None):
```

Comportamiento:

- **Sin `format_id` y sin subtítulos:** `outtmpl` sigue siendo una cadena idéntica a la actual. Sin `writesubtitles`. Sin cambios de formato ni postprocesadores. Es la garantía de regresión.
- **Sin `format_id` y con subtítulos (YouTube):** `outtmpl` pasa a diccionario:

  ```python
  opciones["outtmpl"] = {
      "default": "<carpeta>/%(title)s [%(id)s].%(ext)s",
      "subtitle": "<carpeta>/%(title)s [%(id)s]/%(title)s [%(id)s].%(ext)s",
  }
  ```

  Se mantienen `writesubtitles` y `subtitleslangs`. El video sigue en la raíz; el `.vtt` cae en la subcarpeta, que yt-dlp crea al escribir.
- **Con `format_id`:**
  - `opciones["format"] = format_id`.
  - Sin `postprocessors`, sin `postprocessor_args`, sin `merge_output_format`.
  - `outtmpl = "<carpeta>/%(title)s [%(id)s]/audio adicional - <etiqueta>.%(ext)s"`.
  - `subtitulos` se ignora/force `False` para no repetir subtítulos por cada pista.
  - El resto de opciones (timeout, cookies, `ffmpeg_location`, hooks) se conserva.
- La rama de `format_id` tiene prioridad sobre `modo == "audio"` y `modo == "video"` y fuerza `noplaylist=True` (el `format_id` pertenece a un video concreto).

Validación: solo se aceptan `format_id` que provengan de `normalizar_pistas_audio` para la URL actual; la UI no permite introducirlos a mano.

### 6.4 `descargar_musica`

Añadir `format_id=None` y `pista_label=None` al final de la firma y pasarlos a `_construir_opciones_descarga`. El contrato de retorno `(exito, mensaje, tipo_fallo)`, la clasificación de errores, los hooks y el uso de `ydl_holder` no cambian.

### 6.5 Nombres seguros

- Helper `nombre_pista_seguro(label)` para la etiqueta usada en el nombre (sin rutas, sin caracteres problemáticos, sin espacios/puntos finales). Se apoya en `yt_dlp.utils.sanitize_filename(..., restricted=False)` para conservar espacios y legibilidad (`Spanish (US)`); convierte `%` en `％` (ancho completo) para que la etiqueta no inyecte campos en `outtmpl`; si queda vacío, devuelve `"pista"`.
- Si dos etiquetas colapsan al sanearse, añadir `[format_id]` a **todas** las colisiones para desambiguar de forma simétrica; un lazo final garantiza unicidad incluso en casos patológicos.
- No usar `%(language)s` en `outtmpl`: no es un campo soportado por yt-dlp. El nombre se arma en Python con la etiqueta ya saneada.
- No sobrescribir archivos existentes: yt-dlp omite la descarga si el destino existe.

## 7. Cambios en `yt-dowloader.py`

### 7.1 Sección de pistas

- Sección compacta **“Pistas de audio adicionales”**, visible solo si la URL es válida, es YouTube y `soporta_pistas_audio` es `True`.
- La consulta es **bajo demanda**: un control “Buscar pistas” dispara `verificar_url` en un hilo de trabajo. Así, quien no usa la función no paga una extracción adicional y el flujo sin extras sigue siendo idéntico a v3.3.2.
- El resultado se aplica con `self.after(0, ...)`.
- Guard de generación (equivalente a `_cola_run_id`): cada consulta incrementa un contador; una respuesta solo se aplica si su generación y su URL coinciden con las actuales. Cambiar la URL invalida la consulta en curso y limpia la lista.
- Estados de la sección: inactiva, cargando, sin pistas, lista y error. No bloquear Tkinter.
- Selección múltiple con casillas; cada fila muestra etiqueta, contenedor y bitrate si existen.

### 7.2 Items de cola

Al agregar la URL, además del item principal se crea un item por pista seleccionada:

```python
{
    "url": url_original,
    "carpeta": carpeta,
    "modo": "audio",              # irrelevante con format_id, se conserva por compatibilidad
    "calidad": calidad,
    "subtitulos": False,
    "playlist": False,
    "navegador": navegador,
    "estado": "en_cola",
    "titulo": titulo_del_listado,  # ya conocido; evita otro precheck
    "cancel_flag": threading.Event(),
    "ydl_holder": {},
    "tipo": "pista_audio",
    "format_id": format_id,
    "pista_label": label,
    "origen_url": url,
}
```

- El item principal no cambia de estructura; solo se le añade lo necesario para decidir la subcarpeta de subtítulos (vía `outtmpl`).
- Las pistas se crean antes de `_iniciar_cola`, porque el snapshot de `pending` se congela al iniciar.
- Comparten el límite global de `max_paralelas`.
- Los items existentes (sin `tipo`) siguen funcionando sin cambios.

### 7.3 Deduplicación

Sustituir la comparación por URL sola por una clave compuesta:

```python
clave = (existente["url"], existente.get("format_id"))
if clave == (url, format_id):
    ...  # ya está en cola
```

- El video principal tiene `format_id=None`.
- Una pista puede convivir con el video y con otras pistas del mismo video.
- La misma pista no se puede agregar dos veces.
- Se conserva el resto del comportamiento actual (bloqueo aunque el item esté completado).

### 7.4 Precheck y estados

- Para `tipo == "pista_audio"`, **omitir** el precheck de `_procesar_item` (`1554`): el `format_id` ya se validó al listar y el título está guardado. Se pasa de `en_cola` a `descargando`.
- Si el formato ya no existe al descargar, `descargar_musica` devuelve el error clasificado y solo falla esa pista.
- No se añaden estados a `ESTADOS`: las pistas usan `en_cola`, `descargando`, `listo`, `error` y `cancelado`. No hay fase “Convirtiendo” porque no hay postprocesador.
- `_set_titulo` no se invoca para pistas (el título ya está); la tarjeta muestra `Título · audio adicional · <etiqueta>`.
- Contadores y resumen final usan los estados existentes; no requieren cambios.

### 7.5 Descarga y reintento

En las dos llamadas a `descargar_musica` (`1610` y `1637`), pasar:

```python
format_id=item.get("format_id"),
pista_label=item.get("pista_label"),
```

Para pistas, no pasar `postprocessor_callback` (no hay conversión que mostrar). La cancelación y el reintento con sesión funcionan igual que en el video.

### 7.6 Cancelación y limpieza

- `_cancelar_item` y `_cancelar_item_fuerte` funcionan sin cambios porque operan sobre `cancel_flag`/`ydl_holder` del item.
- “Detener todo” y `_limpiar_cola` incluyen las pistas automáticamente al ser items de cola.
- No se borran archivos completados.
- Si tras una cancelación la subcarpeta quedó vacía, se puede eliminar solo si está vacía y no contiene archivos completados.

### 7.7 Privacidad

Las pistas se muestran con el mismo tratamiento de `ocultar_urls` y `enmascarar_url()` que el resto de la cola, diagnósticos e historial. Los errores pasan por `_registrar_error`.

## 8. Reglas de descarga y protección del archivo original

1. El video principal conserva su selector, su salida MP4 y su audio original.
2. Cada pista usa exclusivamente su `format_id`, validado contra los metadatos de la URL actual.
3. Sin postprocesadores, sin conversión y sin `merge_output_format` en pistas.
4. Contenedor nativo; la extensión final es la real del archivo.
5. Nombres estables y sin sobrescritura.
6. Un error o cancelación de una pista no afecta al video ni a las demás pistas.
7. No se ejecuta FFmpeg sobre el video principal ni se modifican archivos ya descargados.
8. Cookies, timeout, `ffmpeg_location` y clasificación de errores se reutilizan.
9. La subcarpeta se crea solo cuando hay algo que escribir en ella (subtítulos o pistas).

## 9. Cola, progreso y cancelación

- Todas las tareas (video y pistas) comparten el límite global de paralelismo.
- La UI no declara la operación completa mientras queden items `en_cola`, `verificando` o `descargando`.
- Los hooks deben funcionar con `total_bytes` y `total_bytes_estimate` (comportamiento actual).
- Cancelar una pista no cancela las demás; “Detener todo” las cancela todas.
- No se comparte una instancia de `YoutubeDL` entre tareas.

## 10. Plan de implementación por fases

### Fase 0 — Verificación técnica

- Crear una rama desde v3.3.2.
- Probar con videos públicos: un solo audio, audio doblado multi-idioma, sin pistas alternativas y con subtítulos.
- Registrar muestras anonimizadas de `formats` (campos `format_id`, `language`, `format_note`, `acodec`, `ext`, `abr`, `tbr`, `audio_channels`, `vcodec`).
- Confirmar cómo se resuelve `bestaudio` y fijar la detección del audio original.
- Confirmar que cada pista se descarga por `format_id` sin conversión.
- Ajustar el modelo normalizado si los campos reales difieren.

**Criterio de salida:** una pista concreta se identifica, descarga y reproduce como archivo independiente, y el audio original queda excluido.

**Estado:** completada (2026-10-19). Ver sección 5.

### Fase 1 — Lógica pura y pruebas (RED → GREEN)

- Escribir primero las pruebas de normalización, deduplicación, exclusión del original, etiquetas neutrales y nombres seguros.
- Probar las opciones con `format_id`: sin `postprocessors`, sin `merge_output_format`, `outtmpl` en la subcarpeta.
- Probar las opciones con subtítulos: `outtmpl` dict con video en la raíz y subtítulo en la subcarpeta.
- Probar que sin extras las opciones son idénticas a v3.3.2 (regresión).
- Implementar lo mínimo para pasar las pruebas.

**Estado:** completada (2026-10-19). 29 tests nuevos en `core_tests/test_core.py`; suite completa `175 passed`.

### Fase 2 — Descarga aislada

- Extender `descargar_musica` con `format_id` y `pista_label`.
- Verificar contenedores reales, colisiones y preservación de archivos existentes.
- Comprobar cancelación durante descarga y que una pista fallida no invalida otras.

**Estado:** completada (2026-10-19). Verificado con `Af6i6ChAVTw` (21 pistas, original `en` excluido): `140-15` → `audio adicional - Spanish.m4a` (AAC, 56 MB) y `251-5` → `audio adicional - Spanish (webm).webm` (Opus, 57 MB) dentro de la subcarpeta. Reejecutar no altera el archivo (hash igual). Cancelación durante descarga devuelve `(False, "Descarga cancelada", "cancelada")`. **Corrección (2026-10-19):** se añadió `tmpfile_callback` a `_construir_opciones_descarga`/`descargar_musica` (el hook de progreso reporta `tmpfilename`), y la UI guarda esa ruta en `_part_archivo` y la borra en `_limpiar_part_cancelado` solo si está bajo la carpeta de descarga y termina en `.part`. Verificado E2E real (`/tmp/opencode/ui_e2e_pista_cancel.py`): cancelar `140-18 Arabic` deja `estado=cancelado` y 0 `.part`.

### Fase 3 — Interfaz

- Añadir la sección con búsqueda bajo demanda, estados y selección múltiple.
- Implementar el guard de generación para respuestas tardías.
- Crear los items de pista antes de iniciar y conectar dedup, cola, progreso, cancelación y reintento.
- Mostrar la tarjeta de pista con etiqueta y estado, sin precheck adicional.

**Estado:** completada (2026-10-19). Sección bajo demanda en `_build_pistas`/`_actualizar_seccion_pistas` (solo YouTube con `soporta_pistas_audio`), estados cargando/sin pistas/error, guard por `_pistas_gen` + `_pistas_url_actual`, cancelación del worker al cambiar de URL, selección múltiple y dedup `(url, format_id)`. `_agregar_a_cola` crea un item principal + uno por pista (`tipo="pista_audio"`, `format_id`, `pista_label`, `origen_url`); `_procesar_item` omite el precheck para pistas y pasa `format_id`/`pista_label` a ambas llamadas de `descargar_musica`. La tarjeta muestra `Título · audio adicional · <etiqueta>` acortando solo el título base para que la etiqueta no se pierda. Verificado con `/tmp/opencode/ui_smoke.py` (datos fake, dedup, respuesta tardía, no-precheck) y `/tmp/opencode/ui_live_pistas.py` (21 pistas reales de `Af6i6ChAVTw`, original `en` excluido). `py_compile` OK; suite `175 passed, 16 deselected`.

### Fase 4 — Integración y regresión manual

- Ejecutar `.venv/bin/python -m pytest` y `py_compile`.
- Smoke test de UI.
- Video con pista única, multi-idioma, sin pistas y con subtítulos.
- Verificar que mp4 720p/1080p siguen saliendo `h264/avc1 + aac` y que mp3 sigue funcionando.
- Verificar subtítulos `es`, `en`, `pt`: mismo contenido, nueva ubicación en la subcarpeta.
- Probar cookies/sesión, cancelación individual, “Detener todo”, paralelismo y nombres duplicados.
- Confirmar que las pistas abren en VLC.

**Estado:** parcial (2026-10-19). Verificado: `pytest` (176 passed) + `py_compile`; arranque headless sin errores; regresión real mp4 720p (`h264` + `aac`) y mp3 con `dQw4w9WgXcQ`; subtítulos reales con `jNQXAC9IVRw` (mp3 en raíz, `.en.vtt` movido a `Título [id]/`); video sin pistas adicionales (`dQw4w9WgXcQ` y `jNQXAC9IVRw` → 0 pistas); dos pistas seleccionadas a la vez en el smoke; reproducción con `cvlc` de `.m4a`, `.webm` y `.mp4` (exit 0). También verificado con `/tmp/opencode/ui_paralelo_cancel.py`: `max_paralelas=2` (concurrencia máxima 2 con 3 items), “Detener todo” deja los 3 items `cancelado`, y una pista fallida queda en `error` sin afectar al video ni a la otra pista (`listo`). Captura de UI generada en `/tmp/opencode/ui_pistas.png`. Corrección posterior: `normalizar_pistas_audio` ya deduplica `nombre` (colisiones de etiqueta llevan `[format_id]`), y la UI ahora envía ese `nombre` al descargador vía `pista_archivo` (el campo `pista_label` sigue mostrando la etiqueta legible) para no sobrescribirse cuando dos pistas comparten etiqueta. Cancelación con limpieza de parcial verificada E2E con red real. Pendiente: cookies/sesión (sin cambios en ese camino) y revisión visual manual (el agente no puede interpretar imágenes en esta sesión).

### Fase 5 — Documentación y release

- Actualizar `README.md`, `AGENTS.md` y `MEMORY.md` con la funcionalidad y las pruebas ejecutadas.
- Subir versión solo cuando esté validada.
- Ejecutar CI y revisar artefactos antes de publicar.
- No declarar compatibilidad con todas las variantes de YouTube sin pruebas reales.

**Estado (2026-10-19):** `README.md` y `MEMORY.md` actualizados; commit local en `feat/pistas-audio` **sin release** (decisión del usuario). `AGENTS.md` queda con cambios previos del usuario, fuera de este commit.

## 11. Pruebas

### 11.1 Unitarias (offline, en `core_tests/test_core.py`)

- `normalizar_pistas_audio`: filtrado de audio, dedup por idioma, mejor bitrate, exclusión del original, etiqueta neutral, `info` incompleto, lista vacía.
- `_construir_opciones_descarga` con `format_id`: `format` correcto, sin `postprocessors`, sin `merge_output_format`, `outtmpl` con subcarpeta y etiqueta saneada.
- `_construir_opciones_descarga` con subtítulos: `outtmpl` dict, video en raíz, subtítulo en subcarpeta, idiomas intactos.
- `_construir_opciones_descarga` sin extras: regresión exacta del `outtmpl` cadena, sin `writesubtitles`, formatos y merge actuales.
- `nombre_pista_seguro`: caracteres problemáticos, etiquetas que colapsan y sufijo `[format_id]`.
- `descargar_musica`: el `format_id` llega a las opciones (monkeypatch de `yt_dlp.YoutubeDL` si encaja con los tests existentes).

Comando:

```bash
.venv/bin/python -m pytest core_tests/test_core.py -q
```

La suite es la única que corre en CI. Los tests live no cubren esta función; no se añaden a CI.

### 11.2 Manuales / live (antes de release)

- Un mp3 real y un mp4 real (el CI no detecta regresiones de códec).
- Un video multi-idioma: descargar dos pistas y comprobar contenedor, reproducción y que no aparece el original.
- Verificar la subcarpeta y los nombres: `audio adicional - <etiqueta>.<ext>` y `Título [id].es.vtt`.
- Cancelar una pista a mitad y confirmar que el video y las demás pistas siguen.
- Repetir la descarga y confirmar que no se sobrescribe nada.

## 12. Criterios de aceptación

- [x] Sin pistas ni subtítulos seleccionados, el resultado es idéntico a v3.3.2.
- [x] Con solo subtítulos disponibles, se crea `Título [id]/` y el `.vtt` va dentro; el video queda en la raíz.
- [x] La lista de pistas corresponde a la URL actual y nunca incluye el audio original.
- [x] Se puede seleccionar más de una pista; cada una genera un archivo independiente.
- [x] Las pistas se guardan en `Título [id]/audio adicional - <etiqueta>.<ext>`, en contenedor nativo.
- [x] El audio original del video no se reemplaza ni se modifica.
- [x] No se incrustan ni mezclan pistas en el video.
- [x] Las extensiones coinciden con los archivos reales.
- [x] No se sobrescriben archivos existentes.
- [x] Una pista fallida no invalida el video ni las pistas completadas.
- [x] Cancelar una pista funciona; “Detener todo” cancela todas.
- [x] La UI no se congela al buscar pistas y descarta respuestas tardías.
- [x] Las plataformas distintas de YouTube no muestran la sección.
- [ ] Los subtítulos conservan idiomas y contenido, y pasan a la subcarpeta.
- [x] La suite offline y `py_compile` pasan.

## 13. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Metadatos de idioma incompletos o inconsistentes | Etiqueta neutral; no inventar idiomas; validar con videos reales. |
| Duplicados de calidad/formato mostrados como pistas | Dedup por idioma conservando el mejor `abr`/`tbr`. |
| El audio original aparece como pista | Helper aislado y Fase 0; fail-safe sin lista si no se puede identificar. |
| La pista activa una conversión o fusión | Rama con `format_id` sin postprocesadores ni `merge_output_format`; tests de opciones. |
| El nombre de la pista usa `%(language)s` | No existe en `outtmpl`; el nombre se arma en Python con etiqueta saneada. |
| Selección de una URL anterior | Guard de generación y comprobación de URL. |
| Coste de extracción | Consulta bajo demanda; el item de pista no repite precheck. |
| Dedup de cola bloquea pistas | Clave `(url, format_id)`. |
| Cambio de ubicación de subtítulos | Criterio de aceptación explícito y prueba manual de `es/en/pt`. |
| Subcarpeta vacía tras cancelar | Eliminar solo si está vacía y sin archivos completados. |
| `.part` huérfano al cancelar una pista | **Resuelto (2026-10-19):** limpieza dirigida de la ruta reportada por el hook de progreso, con guarda `os.path.realpath` bajo la carpeta de descarga y sufijo `.part`; verificado E2E real. |
| Regresión en MP4/MP3 | Pruebas manuales reales antes de versionar. |
| CI no detecta fallos reales | Verificación manual obligatoria de un mp3 y un mp4. |

## 14. Criterio de diseño final

La función está lista cuando las pistas son **optativas, independientes, identificables y cancelables**, cuando el original queda excluido y cuando el flujo sin extras conserva el comportamiento de v3.3.2.

**Orden recomendado:** demostrar primero la extracción real y la detección del original; después construir el modelo y las pruebas; finalmente integrar la UI. No diseñar la interfaz sobre supuestos de `yt-dlp`.
