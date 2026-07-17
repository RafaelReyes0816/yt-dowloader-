# AGENTS.md

## Project overview

Single-file Python desktop app (tkinter + ttkbootstrap + yt-dlp) that downloads YouTube audio (mp3) or video (mp4) with quality selection. Includes auto-update checking via GitHub Releases API.

## Run

```bash
pip install -r requirements.txt
python yt-dowloader.py
```

System dependency: `ffmpeg` must be installed and on PATH (required by yt-dlp for mp3 conversion and mp4 muxing). On Debian/Ubuntu: `sudo apt install python3-tk` if tkinter is missing.

## Build standalone executable

```bash
pip install pyinstaller yt-dlp ttkbootstrap
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

- `yt-dowloader.py` — entire app: `App` class handles tkinter UI, `descargar_musica()` handles download logic with yt-dlp progress hooks. `Mi_musica/` folder is created at runtime as download target. `check_for_update()` queries GitHub Releases API.
- `yt-dowloader.spec` — PyInstaller build config (multiplatform, includes ttkbootstrap hidden imports).
- `.github/workflows/build.yml` — CI/CD for 3 platforms.
- `requirements.txt` — `yt-dlp`, `ttkbootstrap`, `pyinstaller`.

## Notes

- Filename typo `dowloader` (missing 'n') is intentional — matches the PyInstaller spec output name. Do not rename without updating the spec.
- UI is entirely in Spanish.
- `GITHUB_REPO` constant in `yt-dowloader.py` must match your actual GitHub repo path for auto-update to work.
- `bfg-*.jar` files in repo are BFG Repo-Cleaner (used to purge secrets from git history). Not part of the app. Ignored by `.gitignore` for new files.
