# Linua Updater — Architecture Overview

**Version documented:** 4.3.0 LTS
**Primary source:** the `linua_updater/` package (split from the former single-file `LinuaUpdater_v4.3.0.py`)

---

## 1. Overview

Linua Updater is a lightweight Windows desktop application that installs, verifies, and removes DLC content for *The Sims 4*. It is a Python desktop application using PyQt6 for the GUI and the `requests` library for networking, organized as a modular package (see Module layout).

| Aspect | Detail |
| --- | --- |
| Language | Python 3.8+ |
| GUI framework | PyQt6 |
| Networking | `requests` (with `urllib3` TLS warnings disabled) |
| Distribution | Single executable via PyInstaller |
| Target platform | Windows 10/11 (64-bit) |
| Entry point | `linua_updater/__main__.py` (run as `python -m linua_updater` or via `build.spec`) |

The codebase is a flat-layout PyPI-style package (`pyproject.toml`, entry point in `__main__.py`). Concerns are separated by the layers below into modules under `linua_updater/`; see `docs/refactoring-plan.md` for the full class → module map.

### Module layout

```
linua_updater/
├── __main__.py            # entry point: palette, single-instance, wiring
├── constants.py           # APP_VERSION, DEFAULT_* endpoints/mirrors, SIZE_ESTIMATES
├── paths.py               # AppPaths — single source of truth for %LOCALAPPDATA%\LinuaUpdater paths & cache TTLs
├── logging_util.py        # ImprovedLogger + _reveal_in_explorer
├── utils/                 # ConfigManager, SingleInstanceLock, AdminElevator, DiskSpaceChecker, SevenZipFinder
├── persistence/           # DownloadQueue, DownloadState (JSON state files)
├── core/                  # DLCDatabase, SmartDownloader, Extractor, GameDetector, NetworkDiagnostics,
│                          #  ParallelInstallManager, SingleDLCInstaller, MultiPartInstaller, InstallationStats
├── workers/               # UpdateChecker, InstallWorker, UninstallWorker, DiagnosticsWorker (QObject/QThread)
└── ui/                    # LinuaUI (main window), dialogs, widgets, theme
```

---

## 2. High-Level Architecture

The application follows a layered design connected by Qt signals/slots:

| Layer | Responsibilities | Key Classes |
| --- | --- | --- |
| UI | Rendering, user input, feedback | `LinuaUI`, `DLCSelector`, `UninstallDialog`, `SettingsDialog`, `CompletionDialog`, `SpaceWarningDialog` |
| Worker threads | Long-running work off the UI thread | `InstallWorker`, `UninstallWorker`, `SmartDownloader`, `UpdateChecker`, `DiagnosticsWorker` |
| Services | Domain logic: detection, networking, extraction | `GameDetector`, `NetworkDiagnostics`, `Extractor`, `DLCDatabase` |
| Utilities | Cross-cutting concerns | `ConfigManager`, `SingleInstanceLock`, `AdminElevator`, `SevenZipFinder`, `DiskSpaceChecker`, `ImprovedLogger` |
| Persistence | Local JSON state under `%LOCALAPPDATA%\LinuaUpdater\` | `ConfigManager`, `DownloadQueue`, `DownloadState`, `UpdateChecker` (cache) |

Data flows: UI captures intent → worker thread performs work → worker emits Qt signals → UI updates in response. The UI thread never performs network or disk-intensive work directly; startup network operations run in background `QThread`s.

### Entry sequence

1. `SingleInstanceLock` prevents a second instance (port-based check on `127.0.0.1`).
2. Qt application is created with a dark palette.
3. `ConfigManager` loads stored settings; `DLCDatabase` loads the DLC catalog.
4. `LinuaUI` is instantiated and shown.
5. On startup several deferred operations run via `QTimer.singleShot`, with all network work on background `QThread`s: update check (~100 ms, `UpdateChecker` in a thread), fresh network diagnostics (~300 ms, `DiagnosticsWorker` in a thread, unless a valid 3-hour `diag_cache.json` exists), game auto-detection (~500 ms, plus a 1-second status rescan), and a pending-download resume prompt (~600 ms).

---

## 3. UI Layer

### Main window — `LinuaUI`

The single main window combines everything:

| Area | Widget | Purpose |
| --- | --- | --- |
| Header | `QLabel` | App title + version |
| Path input | `QLineEdit` + Browse/Auto Detect | Sims 4 installation folder |
| Status | `QLabel` | Installed vs available DLC counts |
| Progress | `SimpleProgressBar` + `SimpleDetailWidget` | Download progress and live stats |
| Actions | Buttons | Install, Uninstall, Pause, Cancel, Settings, Export Logs |
| Log | `QTextEdit` | Color-coded, timestamped log output |
| Support | `QLabel` | Donation links (Boosty, DonationAlerts) |

Signal/slot flow:
- Path changes and a 3-second `QTimer` both trigger `update_dlc_status()` which rescans the game folder for installed DLC folders (`EP*`, `GP*`, `SP*`, `FP*`).
- Install/uninstall actions connect worker signals back to UI slots (`on_install_result`, `on_progress_updated`, `on_stats_ready`, etc.) so progress is reflected live without blocking the UI. Per-DLC progress (`progress_updated`) feeds the detail widget only; the main progress bar is driven solely by `on_overall_progress_updated` with the weighted overall value computed by `ParallelInstallManager`.

### Dialogs

| Dialog | Purpose |
| --- | --- |
| `DLCSelector` | Checkbox list of available DLC with "select all"; filters out already-installed packs |
| `UninstallDialog` | Checkbox list of installed DLC; grouped confirm dialog before deletion |
| `SettingsDialog` | Parallel download count and network behavior toggles |
| `CompletionDialog` | Success screen reminding the user to run a DLC Unlocker |
| `SpaceWarningDialog` | Warns when disk space is insufficient; allows "Continue Anyway" |

All dialogs share a dark theme via inline Qt stylesheets.

---

## 4. Download & Install Engine

### Components

| Class | Responsibility |
| --- | --- |
| `SmartDownloader` | Downloads with retries (backoff), byte-level resume via `Range` header + `.part` temp files, slow-speed abort (<50 KB/s), proxy fallback, and mirror fallback; honors the `use_proxy`/`resume_downloads`/`cleanup_temp` settings and supports `pause()`/`resume()` via a `threading.Condition` in the chunk loop (also cancellable from pause) |
| `Extractor` | Extracts single ZIP archives (validated with `testzip()` and per-member path validation) or multipart 7-Zip archives via `7z.exe` |
| `SingleDLCInstaller` | Orchestrates download → extract for single-archive DLC |
| `MultiPartInstaller` | Downloads each `.7z.001/002/...` part (weighted progress across parts), then extracts via 7-Zip; supported in code but not exercised by the shipped catalog |
| `ParallelInstallManager` | Genuinely parallel: a `ThreadPoolExecutor` (sized by `Settings.max_threads`) with one future per DLC; seeds all selected DLC at 0 and computes overall progress as the average over the total selected count |
| `InstallWorker` | QThread-backed driver; submits one unit of work per DLC to the parallel manager, drains futures with `as_completed`, and emits per-DLC results and aggregated stats; exposes `pause()`/`resume()`/`cancel()` |
| `UninstallWorker` | Deletes selected DLC folders off the UI thread |
| `InstallationStats` | Records per-DLC size, duration, and errors; produces a final summary |

Each selected DLC is submitted as its own future to `ParallelInstallManager` and installs concurrently (up to `max_threads`); all selected DLC are seeded at 0, and overall progress is the average across the full selection. Per DLC:

1. Look up DLC metadata in `DLCDatabase`; if it defines a non-empty `parts[]`, route to `MultiPartInstaller` (requires 7-Zip), otherwise `SingleDLCInstaller`. No catalog entry currently defines `parts[]`, so the multipart path is supported but unused today.
2. Download to a temp path with `.part` extension, resuming from any existing partial file (a dedicated per-future `SmartDownloader`).
3. Validate: non-empty, ≥1 KB, size matches expectation.
4. Extract into the game folder.
5. Record stats/errors; remove temp files; emit `result_ready`.
6. After all DLC: emit summary stats and finish signal.

---

## 5. Online Services

| Class | Responsibility |
| --- | --- |
| `DLCDatabase` | Hardcoded in-memory catalog of 109 DLC entries (EP/GP/SP/FP) mapping IDs to names and per-entry Cloudflare Workers download URLs, each enriched with an estimated `size` (bytes) from the single module-level `SIZE_ESTIMATES` table |
| `GameDetector` | Finds the Sims 4 install path via Windows Registry keys (Maxis/EA Games) and scanning common Steam/Origin paths across drives C–H; validates via `Game\Bin\TS4_x64.exe` |
| `NetworkDiagnostics` | Detects region (RU/UA/BY via `ipapi.co`), tests reachability of GitHub/raw.githubusercontent, probes common local proxy ports, and recommends VPN (Cloudflare WARP) when blocked; its region API and proxy-port list are overridable via the `network` config section |
| `UpdateChecker` | Runs on a background `QThread`; fetches `version.json` from the configurable `version_check_url` (avoiding API rate limits), caches results for 36 hours, and compares semver strings |

---

## 6. System Utilities

| Class | Responsibility |
| --- | --- |
| `ConfigManager` | Loads/saves user config (game path + settings) to `config.json`, plus an optional `network` section overriding `version_check_url`, `region_api`, `proxy_ports`, and `mirrors` |
| `SingleInstanceLock` | Acquires a local TCP port to guarantee a single running instance |
| `AdminElevator` | Detects admin rights (`IsUserAnAdmin`) and restarts the app elevated via `ShellExecuteW` when targeting protected paths |
| `SevenZipFinder` | Locates `7z.exe`/`7za.exe` across common install paths and PATH |
| `DiskSpaceChecker` | Computes per-DLC sizes by reading the DB `size` field first, falling back to the `SIZE_ESTIMATES` table and finally a default of 500 MB; totals with a 10% temp buffer and compares against free space |
| `ImprovedLogger` | Writes timestamped color-coded lines to the UI and a rotating file logger (`updater.log`, 5 MB × 3) |
| `DownloadQueue` | JSON persistence for interrupted-download state |

---

## 7. Persistence & State

All state lives under `%LOCALAPPDATA%\LinuaUpdater\` as JSON files:

| File | Owner | Purpose |
| --- | --- | --- |
| `config.json` | `ConfigManager` | Game path + settings (threads, proxy, resume, cleanup) + optional `network` overrides; all toggles are honored at runtime |
| `update_cache.json` | `UpdateChecker` | Latest version + download URL (36-hour TTL) |
| `diag_cache.json` | `LinuaUI` | Network diagnostics result (3-hour TTL), applied on the UI thread |
| `download_queue.json` | `DownloadQueue` | In-progress download records; written on pause, cleared on finish/cancel |
| `download_state.json` | `DownloadState` | Pause/resume snapshot including `game_path` (24-hour TTL); written on pause, cleared on finish/cancel |
| `logs\updater.log` | `ImprovedLogger` | Rotating application log |

Pause/Resume is fully wired: the Pause button suspends active downloads, and a startup dialog offers to resume any remaining DLC from the saved state.

---

## 8. Build & Deployment

### Local build (PyInstaller)

- `build.spec` compiles `linua_updater/__main__.py` into `Linua-Updater` with UPX compression, windowed mode (`console=False`), no external data files.
- Manual build: `pip install pyinstaller requests PyQt6 && pyinstaller --noconfirm build.spec`.

### Running & testing from source

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .                                    # installs requests + PyQt6

python -m linua_updater                              # run the GUI
QT_QPA_PLATFORM=offscreen python -m linua_updater    # run without a display (CI/dev)

pip install -e ".[dev]"                              # pytest, ruff, pyinstaller
python -m pytest tests/                              # 18 smoke tests (core logic)
ruff check linua_updater/                            # lint
```

Tests cover the non-GUI core logic (catalog size, zip-slip rejection, disk-space math, config/persistence round-trips, semver comparison); PyQt6 is only required to import/run the UI and worker modules.

### CI/CD (GitHub Actions)

Two workflows trigger on `v*.*.*` tags:

| Workflow | Runner | Artifact |
| --- | --- | --- |
| `windows_build.yml` | `windows-latest`, Python 3.10 | `dist\Linua-Updater.exe` |
| `linux_build.yml` | `ubuntu-latest`, Python 3.10 | `dist/Linua-Updater` |

Both install `pyinstaller`, `requests`, `PyQt6`, run `pyinstaller --noconfirm build.spec`, and publish the binary to a GitHub Release via `softprops/action-gh-release`.

### Versioning & update channel

- `version.json` (repo root) holds `version`, `download_url`, and `changelog`.
- The app fetches this file at startup to notify users of new releases; downloads point to GitHub Releases.

---

## 9. Install Flow (End-to-End)

1. **Detect** — user browses or uses Auto Detect; path persisted in config.
2. **Select** — `DLCSelector` shows DLC not already installed.
3. **Validate** — path exists, `TS4_x64.exe` optional check, admin rights requested if under `Program Files`.
4. **Check space** — `DiskSpaceChecker` warns (optionally allowing continuation) if free space is short.
5. **Run** — `InstallWorker` in a `QThread`; submits one future per DLC to a `ThreadPoolExecutor` (bounded by `Settings.max_threads`), each with a dedicated `SmartDownloader`, with byte-level resume, retries, proxy/mirror fallback, slow-speed abort, and pause/resume.
6. **Extract** — ZIP via stdlib, multipart via 7-Zip.
7. **Report** — per-DLC results, weighted overall progress on the main bar, then a stats summary; success dialog reminds the user to run a DLC Unlocker.
8. **Reset UI** — buttons/progress restored; DLC status rescanned.

---

## 10. Known Issues & Notes

- **Estimated sizes:** catalog `size` fields (and `SIZE_ESTIMATES` fallbacks) are estimates, not verified byte counts; disk-space and summary calculations can be off from the real archive sizes.
- **Multipart unused:** `MultiPartInstaller` + `SevenZipFinder` remain implemented for `.7z.001/002/...` archives, but no catalog entry currently defines `parts[]`, so the path never runs with the shipped catalog.
- **Hardcoded per-entry URLs:** update-check / region-API / proxy-port / mirror defaults are overridable via the `network` config section, but each DLC download URL is still a hardcoded per-entry value in `DLCDatabase`; operators override the CDN by editing URLs or shipping a new release via `version.json`.
- **Windows-only paths:** registry access, `IsUserAnAdmin`, and `where` rely on win32; the code guards with `sys.platform == "win32"` checks but the app is Windows-targeted.
- **Best-effort endpoints:** proxy/mirror endpoints (including the `gh-proxy.com` prefix mirrors and region API) may become stale or block connections; download fallbacks degrade gracefully.
- **Security posture:** TLS verification is enabled (`verify=True`) on all HTTP calls, and `Extractor.extract_zip` validates every archive member path (rejecting absolute, `..`, and escaping paths) to mitigate zip-slip; the README's security notice correctly warns about fake distribution copies.