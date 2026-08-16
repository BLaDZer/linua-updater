# Linua Updater (Sims 4 DLC manager) — Agent Instructions

## Quick commands

```bash
# Setup venv + dev deps
./scripts/setup.sh

# Run tests then lint
./scripts/check.sh
```

## Tech Stack

- Language: Python
- Python Version: 3.8+

## Architecture at a glance

- `linua_updater/` — single package, flat layout
  - `__main__.py` — entry point (single-instance lock, dark palette, wiring)
  - `core/` — domain logic: `database`, `downloader`, `extractor`, `installers`, `parallel`, `detection`, `diagnostics`, `models`, `checksum`
  - `workers/` — Qt `QThread` workers: `install_worker`, `uninstall_worker`, `update_checker`, `diagnostics_worker`, `database_refresh_worker`
  - `utils/` — `config`, `single_instance`, `admin`, `disk_space`, `sevenzip`
  - `persistence/` — `download_queue`, `download_state` (JSON state files)
  - `ui/` — `main_window`, `dialogs`, `widgets`, `theme`
- `tests` - Tests folder
- `database.json` — DLC catalog that can be updated remotely
- `version.json` — update channel payload (version, download_url, changelog)
- `build.spec` — PyInstaller spec (windowed, UPX, no data/binaries)

## Key constraints

- **PyQt6 required for UI modules.** Tests that import `ui/` or `workers/` need a running Python with PyQt6, but must remain headless (no `QApplication`).
- **Tests are offline by default.** `conftest.py` isolates `AppPaths` and stubs `requests.get` to return 404. Network-dependent tests override the stub.
- **No cross-compile.** `build.sh`/`build.bat` produce a binary for the host platform. Windows `.exe` from Linux requires the CI workflow (`v*.*.*` tag → `windows_build.yml`).
- **CI triggers on `v*.*.*` tags.** Two workflows: `ubuntu-latest` → `dist/Linua-Updater`, `windows-latest` → `dist/Linua-Updater.exe`.
- **Ruff ignores many rules.** `pyproject.toml` has a long `extend-ignore` list (E501, E402, E722, BLE001, S110, S112, F841, etc.) — do not add `ruff` lint errors to PRs without checking if they are in the intentional ignore list.
- **`line-length = 160`** in ruff config.
- **Single-instance lock** uses a TCP port on `127.0.0.1`.
- **Data dir resolution:** Windows → `%LOCALAPPDATA%\LinuaUpdater`, macOS → `~/Library/Application Support/LinuaUpdater`, Linux → `$XDG_DATA_HOME/linua-updater` (default `~/.local/share/linua-updater`).

## Testing Guidelines

- Write unit tests for all new functionality
- Mock external dependencies when appropriate
- Ensure tests are deterministic and isolated
- Run check script before marking any task complete

## Refactoring Preferences

- Prefer incremental refactoring over large rewrites
- Extract logic into testable components
- Keep backward compatibility when possible
- Update tests when refactoring

## Platform Support
Tests and features must support Linux, macOS and Windows unless feature is explicitly OS-specific.

## Tasks format
Example:
```
# Task N — Implement a very usefull feature

## Context
...
## How it works now
...
## How it should work
...
## What needs fixing
...
## Tests
...
## Docs
...
```
