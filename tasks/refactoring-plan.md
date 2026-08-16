# Linua Updater — Modularization Plan

**Versions this applies to:** refactor of `LinuaUpdater_v4.3.0.py` (single file, ~2656 lines, 30+ classes) into a proper Python package.
**Scope:** pure reorganization. No feature changes, no behavior changes. The byte-level behavior of every class is preserved.

---

## 1. Goals

1. Split the monolith into a package grouped by the layers already described in `docs/architecture.md` (UI / Workers / Services / Utilities / Persistence).
2. Apply standard Python project best practices:
   - `pyproject.toml` (metadata, deps, tool configs).
   - `python -m linua_updater` entry point via `__main__.py`.
   - Central `AppPaths` class for every `%LOCALAPPDATA%\LinuaUpdater` location (currently hardcoded in ~7 classes).
   - Type hints / dataclasses on core data models.
   - No bare `except:`; specific exceptions only.
   - `pytest` smoke tests for testable (non-Qt) logic; `ruff` for linting.
3. Keep PyInstaller build working with `build.spec` unchanged in invocation (`pyinstaller --noconfirm build.spec`), just retargeted to the package entry point.

---

## 2. Target Layout

Flat layout at the repo root (keeps PyInstaller `pathex` simple):

```
linua_updater/
├── __init__.py            # __version__ = "4.3.0"
├── __main__.py            # entry point: palette, single-instance, wiring (from old __main__ block)
├── constants.py           # APP_VERSION, GITHUB_REPO, DEFAULT_* endpoints/mirrors, SIZE_ESTIMATES
├── paths.py               # AppPaths — central %LOCALAPPDATA%\LinuaUpdater path resolution
├── logging_util.py        # ImprovedLogger (+ module-level _reveal_in_explorer)
├── utils/
│   ├── __init__.py
│   ├── config.py          # ConfigManager
│   ├── single_instance.py # SingleInstanceLock
│   ├── admin.py           # AdminElevator
│   ├── disk_space.py      # DiskSpaceChecker
│   └── sevenzip.py        # SevenZipFinder
├── persistence/
│   ├── __init__.py
│   ├── download_queue.py  # DownloadQueue
│   └── download_state.py  # DownloadState
├── core/
│   ├── __init__.py
│   ├── models.py          # InstallationStats (+ DLC dataclass)
│   ├── database.py        # DLCDatabase
│   ├── downloader.py      # SmartDownloader
│   ├── extractor.py       # Extractor
│   ├── detection.py       # GameDetector
│   ├── diagnostics.py     # NetworkDiagnostics
│   ├── installers.py      # SingleDLCInstaller, MultiPartInstaller
│   └── parallel.py        # ParallelInstallManager
├── workers/
│   ├── __init__.py
│   ├── update_checker.py    # UpdateChecker (QObject)
│   ├── install_worker.py    # InstallWorker (QObject)
│   ├── uninstall_worker.py  # UninstallWorker (QObject)
│   └── diagnostics_worker.py# DiagnosticsWorker (QObject)
└── ui/
    ├── __init__.py
    ├── theme.py           # dark palette + main stylesheet constants
    ├── widgets.py         # SimpleProgressBar, SimpleDetailWidget
    ├── dialogs.py         # CompletionDialog, SettingsDialog, SpaceWarningDialog, DLCSelector, UninstallDialog
    └── main_window.py     # LinuaUI
```

Supporting files:
- `pyproject.toml` — name `linua-updater`, deps `requests`, `PyQt6`; `[tool.pytest.ini_options]`, `[tool.ruff]`.
- `build.spec` — retargeted to `linua_updater/__main__.py`, `pathex` includes repo root.
- `tests/` — smoke tests (catalog count, version compare, zip-slip rejection, config round-trip, paths).
- `.github/workflows/*` — unchanged (they call `pyinstaller --noconfirm build.spec`); optional lint/test job added later.
- `LinuaUpdater_v4.3.0.py` — removed once the package is verified inside `git` history.

---

## 3. Class → Module Map (exact)

| Class (old) | New module |
| --- | --- |
| `ImprovedLogger`, `_reveal_in_explorer` | `logging_util.py` |
| `ConfigManager` | `utils/config.py` |
| `SingleInstanceLock` | `utils/single_instance.py` |
| `AdminElevator` | `utils/admin.py` |
| `DiskSpaceChecker` | `utils/disk_space.py` |
| `SevenZipFinder` | `utils/sevenzip.py` |
| `DownloadQueue` | `persistence/download_queue.py` |
| `DownloadState` | `persistence/download_state.py` |
| `InstallationStats` | `core/models.py` |
| `DLCDatabase` | `core/database.py` |
| `SmartDownloader` | `core/downloader.py` |
| `Extractor` | `core/extractor.py` |
| `GameDetector` | `core/detection.py` |
| `NetworkDiagnostics` | `core/diagnostics.py` |
| `SingleDLCInstaller`, `MultiPartInstaller` | `core/installers.py` |
| `ParallelInstallManager` | `core/parallel.py` |
| `UpdateChecker` | `workers/update_checker.py` |
| `InstallWorker` | `workers/install_worker.py` |
| `UninstallWorker` | `workers/uninstall_worker.py` |
| `DiagnosticsWorker` | `workers/diagnostics_worker.py` |
| `SimpleProgressBar`, `SimpleDetailWidget` | `ui/widgets.py` |
| `CompletionDialog`, `SettingsDialog`, `SpaceWarningDialog`, `DLCSelector`, `UninstallDialog` | `ui/dialogs.py` |
| `LinuaUI` | `ui/main_window.py` |
| `SIZE_ESTIMATES`, `APP_VERSION`, `DEFAULT_*` | `constants.py` |

---

## 4. Import/Dependency Rules

- `constants.py` imports nothing local → import target for everything.
- `paths.py` imports only `pathlib`.
- `utils/disk_space.py` imports `DLCDatabase` from `linua_updater.core.database` (one-way, no cycle).
- `core/*` imports only from `constants`, stdlib, `requests`. No worker/UI imports.
- `workers/*` import from `core`, `utils`, `persistence`, `constants`, `logging_util`.
- `ui/*` import from `workers`, `core`, `utils`, `persistence`, `constants`, `logging_util`.
- All package-internal imports use absolute form (`from linua_updater.core.database import DLCDatabase`).
- Class signatures, `__init__` parameters, attributes, signals, and method bodies are copied verbatim — only imports and path constants change.

---

## 5. Path Centralization (`paths.py` contract)

Replace every `Path.home() / "AppData" / "Local" / "LinuaUpdater" / ...` with:

```python
class AppPaths:
    BASE_DIR = Path.home() / "AppData" / "Local" / "LinuaUpdater"
    LOG_DIR = BASE_DIR / "logs"
    CONFIG_FILE = BASE_DIR / "config.json"
    UPDATE_CACHE_FILE = BASE_DIR / "update_cache.json"
    DIAG_CACHE_FILE = BASE_DIR / "diag_cache.json"
    DOWNLOAD_QUEUE_FILE = BASE_DIR / "download_queue.json"
    DOWNLOAD_STATE_FILE = BASE_DIR / "download_state.json"
    LOG_FILE = LOG_DIR / "updater.log"

    @staticmethod
    def ensure() -> None:
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
```

Affected classes: `ImprovedLogger`, `ConfigManager`, `UpdateChecker`, `DownloadQueue`, `DownloadState`, `LinuaUI.run_diagnostics`/`_apply_diagnostics`.

---

## 6. Implementation Steps

### Phase 1 — Scaffolding
Create `pyproject.toml`, package dirs, all `__init__.py` files, `constants.py`, `paths.py`.

### Phase 2 — Utilities & persistence
Move `ImprovedLogger`, utils package, persistence package. Apply `AppPaths`.

### Phase 3 — Core services
Move `core/*`. Add type hints + dataclasses in `core/models.py`.

### Phase 4 — Workers
Move `workers/*` unchanged.

### Phase 5 — UI layer
Move `ui/*`. Extract palette + stylesheets into `ui/theme.py`.

### Phase 6 — Entry & build
Write `__main__.py` from the old `if __name__ == "__main__"` block. Update `build.spec`.

### Phase 7 — Quality gates
Add `tests/` smoke tests; run `ruff` + `pytest` locally.

### Phase 8 — Docs & version
Rewrite `docs/architecture.md`; delete monolith; bump `APP_VERSION`/`version.json`.

---

## 7. Verification

1. `python3.14/bin/python -c "import linua_updater.ui.main_window"` — full package import on the machine with PyQt6.
2. `pytest tests/` — core logic smoke tests (run with system python3, no PyQt6 needed).
3. `python -m linua_updater` launches the app (manual/headless check).
4. `pyinstaller --noconfirm build.spec` still produces a binary (CI/normal build).

---

## 8. Constraints

- Do not touch behavior: signals, settings keys, URLs, defaults, file names, `size` estimates, layout/order of dialogs, logging output format.
- No new runtime dependencies.
- Keep the repository's Git history intact; final monolith removal is a plain `git rm`.