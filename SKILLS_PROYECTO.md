# 🚀 Skills del Proyecto

Índice de las skills de OpenCode **instaladas en este repositorio** (`.opencode/skills/`), que son las que se usan para el desarrollo de yt-downLoader (app de escritorio Python, CustomTkinter + yt-dlp, en `yt-dowloader.py`/`core.py`).

El agente debe invocar la skill por su **nombre exacto** a través de la herramienta `skill` de opencode (no existe un comando `use-skill:`). La lista completa del entorno (catálogo de seguridad/auditoría/forensics, etc.) es externa al repo y se carga automáticamente desde `~/.agents/skills` y `~/.claude/skills`; este índice documenta únicamente las skills propias del proyecto.

---

## 🔄 TDD (Test-Driven Development)

* **`tdd`** — Referencia del ciclo red→green→refactor: qué es un buen test, dónde van, anti-patterns y reglas del loop. Úsala SIEMPRE que se construyan features o se arreglen bugs en `core.py` (lógica pura, testeable) o en los tests de `core_tests/`. Verificación: `.venv/bin/python -m pytest core_tests -m "not live"`.

## 💄 Diseño de UI

* **`frontend-design`** — Dirección estética deliberada e intencional al construir o reformar la UI: paleta, tipografía, layout y decisiones que no lean como plantillas genéricas. Aplica al diseño del tema y componentes en `yt-dowloader.py`/`theme.py`.
* **`web-design-guidelines`** — Revisión de la UI contra buenas prácticas de usabilidad y accesibilidad (foco visible, reduced motion, heurísticas). Úsala al auditar `yt-dowloader.py` ("review UI", "check accessibility", "audit design").

## 🔐 Seguridad del código

* **`security-best-practices`** — Revisión de buenas prácticas de seguridad por lenguaje/framework (Python incluido). Úsala cuando se pida una revisión o reporte de seguridad del código, o trabajo secure-by-default. Consulta `references/python-*.md` según el stack (la app usa Python estándar + yt-dlp; no hay referencia exacta de escritorio, aplicar criterio general).

---

## Notas

- Las skills viven en `.opencode/skills/<nombre>/SKILL.md` (formato estándar de opencode: carpeta por skill + `SKILL.md` con frontmatter `name`/`description`).
- Para que los cambios en `.opencode/` tengan efecto, reiniciar opencode (la config se carga al iniciar sesión).