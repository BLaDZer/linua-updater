# Task 27 — Install DLC from a torrent (magnet) when present, falling back to parts/url

## How it works now

- The catalog already carries `magnet` as an example: `EP06` has a `magnet` key next to `url` and `parts` (`database.json:26`). Nothing consumes it — the install path only ever looks at `parts` and `url`.
- `InstallWorker._install_single` (`linua_updater/workers/install_worker.py:88-115`) routes each DLC by a single check: `if info.get("parts")` → `MultiPartInstaller` (`linua_updater/core/installers.py:85`), otherwise → `SingleDLCInstaller` (`linua_updater/core/installers.py:9`). Both wrap `SmartDownloader.download` (plain HTTP, `linua_updater/core/downloader.py:52`), which already degrades through proxies and mirrors (`downloader.py:65-81`).
- Each install builds a dedicated `SmartDownloader` and registers it in `_active_downloaders` (`install_worker.py:92-94`) so `cancel()` / `pause()` / `resume()` (`install_worker.py:51-76`) interrupt the transfer.
- `_save_download_state` (`install_worker.py:78-86`) records in-progress DLC into `DownloadQueue` keyed on `info['url']`; a magnet-only entry has no `url`, so the queue path cannot represent it today.
- No torrent engine exists. `pyproject.toml` depends only on `requests` + `PyQt6` (`pyproject.toml:8-11`). The `torrentp`/`libtorrent` wheels are unavailable for the project's `requires-python >= 3.8` (`pyproject.toml:7`) and the Python 3.10 CI builds, so an in-process libtorrent binding is ruled out.
- Release binaries are single-file PyInstaller artifacts (`build.spec`, with an empty `binaries=[]` at `build.spec:9`), built on `windows-latest` and `ubuntu-latest` runners (`.github/workflows/windows_build.yml`, `.github/workflows/linux_build.yml`). The precedent for shipping an external CLI tool is 7-Zip: `SevenZipFinder` (`linua_updater/utils/sevenzip.py:6-46`) resolves the binary at runtime (exe dir → common paths → PATH) and the missing-tool case degrades gracefully to a `WARNING`.

## How it should work

- **Two new pieces** ship the torrent path:
  1. `Aria2Finder` (`linua_updater/utils/aria2.py`) — locates the `aria2c` executable at runtime, mirroring `SevenZipFinder` exactly, but checking the PyInstaller `sys._MEIPASS` directory first so the bundled binary is found in a one-file build.
  2. `TorrentDownloader` (`linua_updater/core/torrent_downloader.py`) — a **separate downloader** that drives `aria2c` as a subprocess, e.g.:
     ```
     aria2c <magnet> --dir=<download_dir> --seed-time=0 --bt-stop-timeout=600 \
       --continue=true --allow-overwrite=true --file-allocation=none \
       --summary-interval=1
     ```
     It exposes the same surface as `SmartDownloader` (`set_progress_callback` / `cancel` / `pause` / `resume` / `download`) so installers treat both uniformly.
- **Priority** in `_install_single` becomes `magnet` (highest) → `parts` → `url`, decided by a pure helper `installer_kind(info)`:
  | `info` content | kind | installer |
  | --- | --- | --- |
  | `magnet` present | `magnet` | new `TorrentInstaller` |
  | no `magnet`, `parts` present | `parts` | `MultiPartInstaller` (existing) |
  | neither | `single` | `SingleDLCInstaller` (existing) |
- `TorrentInstaller` (`linua_updater/core/installers.py`) downloads the magnet into a temp dir, verifies the completed archive with `verify_file_checksums` (`linua_updater/core/checksum.py:9`) against `info['checksum']`, then extracts through the existing `Extractor` — `.zip` → `extract_zip` (`extractor.py:15`), `.7z` / `.001…` → `SevenZipFinder` + `extract_7z` (`extractor.py:47`) — exactly like the single/multipart installers.
- **Fallback:** if the magnet path fails at any point (aria2c missing, no seeders, timeout, empty/corrupt download, checksum mismatch), installation **falls back to the current implementation** — `parts`, then `url`. This mirrors `SmartDownloader`'s proxy/mirror fallback philosophy (`downloader.py:65-81`) and is the key guarantee: `magnet` is a preferred source, never a hard requirement. The failure is logged at `WARNING` so operators can see torrents are not working.
- **Pause/resume/cancel** keep working: `TorrentDownloader` is registered in `_active_downloaders` (`install_worker.py:93-94`) like `SmartDownloader`. Pause/cancel terminate the `aria2c` process, leaving the `.aria2` control file; resume re-runs the same command (`--continue=true` resumes from the control file).
- `aria2c` is a **bundled binary** in release builds (packaged by `build.spec`, downloaded by each CI workflow) and found at runtime by `Aria2Finder`; when it is absent (dev machine), the finder logs a `WARNING` and the install degrades to `parts`/`url` — never a hard error.
- No seeding: `--seed-time=0` stops `aria2c` once the transfer completes. Security posture unchanged: archives still pass the same path-safety checks in `Extractor` before anything is written into the game folder.

## What needs fixing

1. **New `linua_updater/utils/aria2.py` — `Aria2Finder`** (modeled on `sevenzip.py:6-46`):
   - `_executable_names()` → `["aria2c.exe"]` on Windows, `["aria2c"]` elsewhere.
   - `find()` order: PyInstaller `getattr(sys, "_MEIPASS", None)` → exe dir (`os.path.dirname(os.path.abspath(sys.argv[0]))`) → `POSSIBLE_LOCATIONS` (common install paths) → `shutil.which`.
   - Returns `None` (not raise) with `self.logger.log("aria2c not found ... torrent downloads will fall back to direct download", "WARNING")` when missing.
2. **New `linua_updater/core/torrent_downloader.py` — `TorrentDownloader`**:
   - ctor `(logger, aria2_path=None, cleanup=True)`; `aria2_path` defaulting to `Aria2Finder(logger).find()`.
   - Public API mirroring `SmartDownloader` (`downloader.py:28-83`): `set_progress_callback(cb)`, `cancel()`, `pause()`, `resume()`, and
     ```python
     def download(self, magnet, out_dir, dlc_name=None, expected_size=None):
         """Fetch a magnet link. Returns (True, [completed_files]) or (False, reason)."""
     ```
   - `_build_command(magnet, out_dir)` producing the flags above plus `--check-integrity=false` (checksum is verified by the installer afterwards against `info['checksum']`).
   - `_parse_summary(line)` → `(progress_pct, downloaded_bytes, total_bytes)` from the periodic `--summary-interval=1` output line `[#hash 12.3MiB/123.4MiB(10%) CN:... DL:...]`, converting the `KiB/MiB/GiB` units; a `total` of 0 falls back to `expected_size`.
   - `cancel()` / `pause()`: set `self._cancelled`, terminate the child process (leaving `.aria2`/`.torrent` control files for resume). `resume()`: clear `self._cancelled` and re-run the same command.
   - On exit code 0: remove `*.aria2` and `*.torrent` artifacts in `out_dir`, return a sorted list of the remaining completed files; on non-zero exit return `(False, "aria2c exit code N")`.
   - Track `self._cancelled` so a mid-transfer terminate returns `(False, "Cancelled")` rather than an exit-code error.
3. **`linua_updater/core/installers.py` — add `TorrentInstaller`** (after `MultiPartInstaller`, `installers.py:85-167`):
   - ctor `(dlc_id, info, game_path, downloader, extractor, logger, stats=None)` plus `set_progress_callback` and `log` mirroring `installers.py:98-103`; requires `info.get("magnet")`.
   - `run()`:
     - `tempfile.mkdtemp()` download dir;
     - `ok, result = self.dl.download(info["magnet"], temp_dir, dlc_name=..., expected_size=info.get("size"))`; wrap progress via the same `part_progress`-style callback pattern used for multipart (`installers.py:123-127`);
     - on failure → `stats.record_error` + `return False, reason`;
     - pick the primary file: the one matching `info.get("size")`, else the largest; missing/empty → failure;
     - `errors = verify_file_checksums(primary, info.get("checksum"))`; non-empty → log each at `WARNING` and `return False, "; ".join(errors)`;
     - extract: `.zip`/`.ZIP` → `self.ex.extract_zip(...)`; `.7z` or a multi-part `.001` → `SevenZipFinder` + `self.ex.extract_7z(...)`; else → `return False, f"Unsupported torrent archive: {name}"` (fallback handles it);
     - `stats.record_download` + `self.log("Complete")` → `return True, "OK"`;
     - `finally` removes the temp dir.
4. **`linua_updater/workers/install_worker.py`:**
   - Module-level helper (pure, unit-testable):
     ```python
     def installer_kind(info):
         if info and info.get("magnet"):
             return "magnet"
         if info and info.get("parts"):
             return "parts"
         return "single"
     ```
   - `_install_single` (`install_worker.py:96-103`) switches on it: `magnet` → `TorrentInstaller(dlc_id, info, self.game_path, downloader, self.extractor, self.logger, self.stats)`; `parts` → the existing 7-Zip lookup + `MultiPartInstaller`; `single` → `SingleDLCInstaller`.
   - **Fallback wrapper** around the magnet attempt: keep a copy of `info`; when a magnet install returns `success == False`, log `WARNING: <dlc>: Torrent download failed (<reason>), falling back to direct download`, strip the key (`info.pop("magnet", None)`), and re-enter the selector so it tries `parts` then `url`. The final returned value for the DLC comes only from a parts/url install (or the last failure). A magnet failure must never surface before parts/url are attempted.
   - `_save_download_state` (`install_worker.py:78-86`): skip `self._download_queue.add(...)` when `info.get('url')` is absent (magnet-only entries); `DownloadState.save_state` is unchanged.
   - Register the `TorrentDownloader` in `_active_downloaders` exactly like `SmartDownloader` (`install_worker.py:92-94`); `cancel/pause/resume` (`install_worker.py:51-76`) then cover it without changes.
5. **`build.spec` (`build.spec:9`)** — bundle the executable:
   ```python
   aria2_name = "aria2c.exe" if os.name == "nt" else "aria2c"
   aria2_bin = os.path.join(os.path.dirname(os.path.abspath(SPEC)), "tools", aria2_name)
   if os.path.exists(aria2_bin):
       a.binaries += [(aria2_bin, ".")]
   ```
   The binary lands next to the app and is found via `Aria2Finder` (or the exe dir / `_MEIPASS`).
6. **CI workflows:**
   - `.github/workflows/windows_build.yml` (before "Build EXE"): step that downloads the official `aria2-*-win-64bit-build*.zip` release asset and extracts `aria2c.exe` into `tools/`.
   - `.github/workflows/linux_build.yml` (in the system-deps step): `sudo apt-get install -y aria2`, then `mkdir -p tools && cp "$(command -v aria2c)" tools/`.
   - `tools/` is a build artifact only — add it to `.gitignore`.
7. **Tests** (offline, following `tests/conftest.py:15-28` so no test hits the real network or the real app-data dir):
   - `tests/test_aria2.py` — `Aria2Finder` precedence: `_MEIPASS` beats exe dir beats PATH (temporary fake binaries via `tmp_path` + `monkeypatch`); missing binary → `None` and a WARNING (no exception).
   - `tests/test_torrent_downloader.py` — fake `aria2c` (a stub `subprocess.Popen` with scripted stdout): summary-line parsing (`…(10%)…` → 10.0, then `…(100%)…` → 100.0) drives the progress callback; successful run returns the completed files and cleans `.aria2`/`.torrent`; `cancel()` mid-run returns `(False, "Cancelled")`; non-zero exit → `(False, "aria2c exit code ...")`. All unit-testable with a `FakeProcess` object; no real binary required.
   - `tests/test_installers.py` — `TorrentInstaller` happy path: a monkeypatched `downloader` returning a handcrafted ZIP (with matching `checksum`) in a temp dir → extracts into the game dir and verifies; corrupt/checksum-mismatch ZIP → `(False, ...)`.
   - `tests/test_install_worker.py` — `installer_kind`: `{"magnet": ...}` → `"magnet"`, `{"parts": [...]}` → `"parts"`, `{"url": ...}` → `"single"`. Pure functions only; no Qt/thread tests (the repo has no `pytest-qt`, matching the existing convention from task 26).
8. **`docs/architecture.md`** — update the download-engine components table (`docs/architecture.md:105-114`), the per-DLC step list with the new routing + fallback (`docs/architecture.md:116-123`), the module layout (`docs/architecture.md:34-35`), and the install flow (`docs/architecture.md:225-234`): add `Aria2Finder`, `TorrentDownloader`, `TorrentInstaller`; note the `magnet` → `parts` → `url` priority and the automatic fallback.
9. **`README.md`** — Features (`README.md:20-29`): add "Automatic torrent (magnet) downloads with automatic fallback to direct download". Troubleshooting: note that when `aria2c` is unavailable/unreachable the app silently falls back to parts/url, so torrent issues never block installation.

## Notes / out of scope

- No schema/DB change: `magnet` already exists on `EP06` (`database.json:26`); entries without it route exactly as before (`parts` → multipart, otherwise single `url`).
- No leaks/resharing: `--seed-time=0` stops seeding once the download completes; the temp dir is removed after extraction.
- Disk-space math is unchanged — `TorrentInstaller` uses the same `info['size']`/`SIZE_ESTIMATES` estimates (`linua_updater/utils/disk_space.py:11-17`).
- Pause/resume for torrents persists via the `.aria2` control file, not `DownloadQueue`; the `download_queue.json` schema is not extended, and magnet-only entries are skipped there.
- Multiple-file torrents: the primary archive is the file matching `info['size']`, else the largest; per-file `--select-file` selection is explicitly deferred (a future refinement if a catalog entry ever needs it).
- A magnet that announces a non-archive (e.g. EP06's example announces `Alawar_NoKey.exe`, an in-place installer) is not extracted by this path — `TorrentInstaller` returns `Unsupported torrent archive` and the catalog falls back to the trusted `parts`/`url`. Checksums remain the arbiter for everything actually installed.
- `aria2c` itself is a build-time artifact in `tools/` (gitignored); a developer without it still gets a fully working app (WARNING + parts/url fallback). No new Python dependency is introduced (`pyproject.toml` unchanged).