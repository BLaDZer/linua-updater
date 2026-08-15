# Task 12 — Cross-platform application data paths (paths.py)

## How it works now

- `AppPaths.BASE_DIR = Path.home() / "AppData" / "Local" / "LinuaUpdater"` (`linua_updater/paths.py:13`) hardcodes the Windows `%LOCALAPPDATA%\LinuaUpdater` layout on every OS. On Linux/macOS this creates an ugly `~/AppData/Local/LinuaUpdater` hierarchy with `logs\updater.log`-style subpaths.
- All other modules centralize through `AppPaths`, so a single `BASE_DIR` change fixes everything:
  - `ConfigManager` (`linua_updater/utils/config.py:9`)
  - `ImprovedLogger` (`linua_updater/logging_util.py:34-36`)
  - `DownloadQueue` (`linua_updater/persistence/download_queue.py:9`)
  - `DownloadState` (`linua_updater/persistence/download_state.py:10`)
  - `UpdateChecker` (`linua_updater/workers/update_checker.py:20-21`)
  - the main-window diag cache
- The module docstring (`paths.py:1-5`) and class docstring (`paths.py:11`) explicitly document `%LOCALAPPDATA%\LinuaUpdater`.
- `docs/architecture.md` §7 documents "%LOCALAPPDATA%\LinuaUpdater\" (`architecture.md:152`) and §10 (`architecture.md:241`) lists "Windows-only paths".

## How it should work

- `BASE_DIR` resolves per-platform:
  - **Windows:** `%LOCALAPPDATA%\LinuaUpdater` — honor the `LOCALAPPDATA` env var when set, fall back to `Path.home() / "AppData" / "Local"` when unset. Backward compatible: existing users' data stays byte-for-byte identical.
  - **macOS:** `~/Library/Application Support/LinuaUpdater` (the correct per-user location).
  - **Linux:** `$XDG_DATA_HOME/linua-updater`, falling back to `~/.local/share/linua-updater` when `XDG_DATA_HOME` is unset (XDG Base Directory spec).
- `LOG_DIR` and all `*_FILE` class attributes (`paths.py:14-22`) keep their existing relative names under `BASE_DIR` so callers are unchanged.
- `ensure()` (`paths.py:29-33`) keeps its behavior (mkdir parents).
- Prefer lazy resolution (a helper function or property) over import-time side effects so tests can monkeypatch `os.environ` / `Path.home()`, and document that choice.

## What needs fixing

1. `linua_updater/paths.py:13` — replace the hardcoded Windows path with platform-specific resolution: `LOCALAPPDATA` (Windows) → `~/Library/Application Support` (macOS) → `XDG_DATA_HOME` / `~/.local/share` (Linux), matching the spec above.
2. `linua_updater/paths.py:1-5` and `paths.py:11` — update the module and class docstrings so they describe the XDG/macOS/Windows layouts instead of only `%LOCALAPPDATA%`.
3. `docs/architecture.md:152` (§7) and `architecture.md:241` — document the per-platform base dir (Windows/macOS/Linux) instead of "%LOCALAPPDATA%\LinuaUpdater\" as if universal. Keep a note that Windows retains the legacy `%LOCALAPPDATA%\LinuaUpdater` path.
4. Add tests (new file `tests/test_paths.py`, following the existing `monkeypatch` style from `tests/test_config.py:7-11`):
   - Monkeypatch `os.environ` (unset `LOCALAPPDATA` / `XDG_DATA_HOME`) and/or `Path.home()` so `BASE_DIR` equals the expected per-platform value on the current host; guard the expectation with `sys.platform` or compute the expected value the same way the module does.
   - Assert all derived attributes (`LOG_DIR`, `CONFIG_FILE`, `DOWNLOAD_STATE_FILE`, `logs/updater.log`, ...) sit under the resolved `BASE_DIR`.
   - Assert the exact Windows legacy path is reproduced when `LOCALAPPDATA` is set to a temp dir.
5. Docs impact: `docs/architecture.md:152` and `architecture.md:241` must be updated in the same PR. No arg changes are needed anywhere — the 3-hour diag cache, config, and download-state files all automatically migrate because they resolve through `AppPaths`.