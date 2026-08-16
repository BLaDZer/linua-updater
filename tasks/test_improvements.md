# Test Improvements Plan

This document catalogs the current automated test coverage in `tests/`, identifies the
untested modules and the untested branches of partially covered modules, and proposes
concrete new tests. It is a plan — each entry lists the module, the exact code paths
involved (with file:line references), and a recommended test name and strategy.

## Current test inventory

| Test file                          | Module(s) covered                                    | Status |
|------------------------------------|------------------------------------------------------|--------|
| `tests/test_admin.py`              | `utils/admin.py` (AdminElevator)                     | Partial |
| `tests/test_config.py`             | `utils/config.py` (ConfigManager)                    | Partial |
| `tests/test_database.py`           | `core/database.py` (DLCDatabase)                     | Partial |
| `tests/test_detection.py`          | `core/detection.py` (GameDetector)                   | Partial |
| `tests/test_disk_space.py`         | `utils/disk_space.py` (DiskSpaceChecker)             | Partial |
| `tests/test_extractor.py`          | `core/extractor.py` (Extractor.extract_zip)          | Partial |
| `tests/test_paths.py`              | `paths.py` (AppPaths)                                | Good |
| `tests/test_persistence.py`        | `persistence/download_queue.py`, `persistence/download_state.py` | Partial |
| `tests/test_sevenzip.py`           | `utils/sevenzip.py` (SevenZipFinder)                 | Good |
| `tests/test_ui_defaults.py`        | `ui/main_window.py` (pure helpers)                   | Good |
| `tests/test_update_checker.py`     | `workers/update_checker.py` (`_compare_versions`)    | Partial |

## Modules with no tests at all

| Module                                            | Why it matters                                          |
|---------------------------------------------------|---------------------------------------------------------|
| `core/downloader.py` (SmartDownloader)            | Core download engine: retries, mirrors, proxies, pause/resume, size/speed checks |
| `core/installers.py` (SingleDLCInstaller, MultiPartInstaller) | Drives the whole install workflow, temp-file cleanup  |
| `core/models.py` (InstallationStats)              | Stats/speed math feeding the summary dialog             |
| `core/parallel.py` (ParallelInstallManager)       | Thread-pool progress aggregation                        |
| `core/diagnostics.py` (NetworkDiagnostics)        | Network decision: direct vs proxy vs vpn_needed         |
| `workers/install_worker.py` (InstallWorker)       | Orchestrates install; pause/resume/state saving         |
| `workers/uninstall_worker.py` (UninstallWorker)   | Deleting DLC folders                                     |
| `utils/single_instance.py` (SingleInstanceLock)   | Single-instance port locking                             |
| `logging_util.py` (ImprovedLogger)                | Log colorizing, file logging, log export                |

---

## Phase 1 — Pure logic, no Qt, highest value (suggested first)

These are pure-Python, deterministic, and don't need a `QApplication`. They cover the
engine that downloads and installs content — currently completely untested.

### 1.1 `tests/test_models.py` — `InstallationStats` (`core/models.py`)

- `test_summary_before_finish_is_none` — `get_summary()` returns `None` before `finish()`
  (`models.py:34-38`).
- `test_record_download_tracks_bytes_and_speed` — `record_download("EP01", 10*1024*1024, 2)`
  yields `size_mb == 10`, `speed_mbps == 5`, `total_bytes` accumulates (`models.py:19-24`).
- `test_record_download_zero_duration_no_division_error` — `duration_sec == 0` → `speed_mbps == 0`
  (`models.py:20`).
- `test_record_error_accumulates` — multiple `record_error` calls append to `errors`
  (`models.py:26-28`).
- `test_summary_aggregates` — after start/record/finish, `total_dlc`, `successful`, `failed`,
  `avg_speed_mbps` are computed (`models.py:39-48`).
- `test_summary_thread_safety` — concurrent `record_download`/`record_error` from threads do
  not lose updates (exercises the `threading.Lock`).

### 1.2 `tests/test_parallel.py` — `ParallelInstallManager` (`core/parallel.py`)

- `test_initialize_sets_progress_map` — `initialize(["EP01","GP01"])` seeds each DLC at
  0.0 progress (`parallel.py:15-18`).
- `test_overall_progress_average` — update EP01 to 100, GP01 to 50 → overall 75
  (`parallel.py:23-35`).
- `test_overall_progress_empty_is_zero` — no `initialize` → `_calculate_overall_progress() == 0`
  (`parallel.py:30-35`).
- `test_cancel_all_shuts_down_executor` — `cancel_all()` sets `_cancelled` and shuts the pool
  down without raising (`parallel.py:37-39`).

### 1.3 `tests/test_diagnostics.py` — `NetworkDiagnostics` (`core/diagnostics.py`)

Use `monkeypatch` on the module's `requests` to avoid real network calls.

- `test_detect_region_ru_marks_is_russia` — mocked GET returns `{"country_code": "RU"}` →
  `detect_region()` is `True` and `is_russia` set (`diagnostics.py:23-33`).
- `test_detect_region_network_error_false` — `requests.get` raises → `False`, no crash.
- `test_test_connection_ok` / `test_test_connection_failure` — status `< 400` → `True`;
  exception → `False` (`diagnostics.py:35-40`).
- `test_test_proxy_returns_speed` — mocked GET returns `<400` → `(True, elapsed_ms)`; error →
  `(False, 0)` (`diagnostics.py:42-49`).
- `test_diagnose_direct` — both github and raw reachable → `recommended_solution == "direct"`,
  `proxy_needed is False` (`diagnostics.py:51-60`).
- `test_diagnose_proxy_found` — direct blocked, one `test_proxy` succeeds →
  `recommended_solution == "proxy"`, `working_proxies` populated (`diagnostics.py:62-80`).
- `test_diagnose_vpn_needed` — direct blocked, no proxies work → `"vpn_needed"`
  (`diagnostics.py:79-80`).
- `test_get_recommendation_messages` — each solution maps to its string (`diagnostics.py:82-88`).

### 1.4 `tests/test_downloader.py` — `SmartDownloader` (`core/downloader.py`)

This is the largest gap. Mock `requests.Session` (or the module-level `requests` used by the
session) so no real network is touched. A small fake `session` object returning a fake stream
response works well.

- `test_cancel_prevents_write` — fake streaming response with `_cancelled` set before/inside
  the chunk loop → returns `(False, "Cancelled")` (`downloader.py:126-134`).
- `test_pause_blocks_until_resume` — set `_paused`, start chunk loop in a thread, `resume()`
  after a delay → loop completes (`downloader.py:129-135`).
- `test_resume_uses_range_header_and_appends` — `start_byte > 0` sends `Range` header and opens
  in `ab` mode (`downloader.py:105-119`).
- `test_retry_after_connection_error` — first `_try_download` raises `ConnectionError`, second
  succeeds → overall success (exercises `_try_download_with_retry` retry loop, `downloader.py:83-99`).
- `test_size_mismatch_detected` — `content-length` present but downloaded size differs → returns
  `(False, "Size mismatch...")` (`downloader.py:161-165`).
- `test_file_too_large_rejected` — `total_size > 10GB` → `(False, "File too large (>10GB)")`
  (`downloader.py:116-117`).
- `test_speed_threshold_aborts` — simulate elapsed `> speed_check_duration` with low speed →
  `(False, "Speed too slow, trying alternative")` (`downloader.py:148-152`).
- `test_mirror_fallback` — primary URL fails, mirror domain mapping present → downloads via
  replaced URL (`downloader.py:72-79`).
- `test_proxy_fallback_uses_working_proxies` — `diagnostics.working_proxies` non-empty →
  retries via proxy (`downloader.py:65-70`).
- `test_set_proxy_clears_proxies` — `set_proxy(None)` empties `session.proxies`
  (`downloader.py:31-35`).

### 1.5 `tests/test_installers.py` — `SingleDLCInstaller` / `MultiPartInstaller` (`core/installers.py`)

Use stub `downloader`/`extractor` objects (records calls, returns canned results) and
`tmp_path` for the game dir. Set `cleanup=True/False` on the fake downloader to assert the
`finally` cleanup paths.

- `test_single_missing_url` — `info` without `url` → `(False, "URL missing")`
  (`installers.py:31-32`).
- `test_single_empty_download` — downloader writes 0-byte file → `"Downloaded file is empty"`
  (`installers.py:49-50`).
- `test_single_too_small_download` — file `< 1024` bytes → `"Downloaded file too small (corrupted?)"`
  (`installers.py:51-52`).
- `test_single_extract_failure_records_error` — extractor returns `(False, "boom")` →
  `stats.record_error` called, result `(False, "boom")` (`installers.py:54-58`).
- `test_single_success_records_download` — success path calls `stats.record_download` with the
  file size (`installers.py:59-63`).
- `test_single_cleanup_removes_temp` — with `cleanup=True`, temp file removed after run
  (`installers.py:68-73`).
- `test_single_cleanup_false_keeps_temp` — with `cleanup=False`, temp file remains.
- `test_multipart_missing_7z` — `seven` path invalid → `(False, "7-Zip not found")`
  (`installers.py:101-102`).
- `test_multipart_no_parts` — `info["parts"]` empty → `(False, "No parts defined")`
  (`installers.py:103-105`).
- `test_multipart_part_failure_cleans_up` — second part download fails → prior parts removed,
  error recorded (`installers.py:119-128`).

---

## Phase 2 — Error branches in partially covered modules

### 2.1 `tests/test_update_checker.py` (extend)

Currently only `_compare_versions` is tested (`test_update_checker.py:4-10`). Add network
checks with `monkeypatch` on `requests.get` and the `version_url`/cache file.

- `test_compare_versions_invalid_tokens` — `"4.3.a"` vs `"4.3.0"` → `False` (non-int parse,
  `update_checker.py:101-115`).
- `test_compare_versions_shorter_major_wins_rule` — e.g. `"10.0"` vs `"9.9.9"` → `True`.
- `test_check_update_available_emits_signal` — mocked 200 response with higher version → capture
  `update_available` signal with `(version, url)` (`update_checker.py:77-90`).
- `test_check_no_update_emits` — same version → `no_update` signal.
- `test_check_http_error_emits_failed` — status 500 → `check_failed("HTTP 500")` (`update_checker.py:91-92`).
- `test_check_timeout_emits_failed` — `requests.exceptions.Timeout` → `check_failed("Timeout")`
  (`update_checker.py:94-95`).
- `test_check_connection_error_emits_failed` — `ConnectionError` → `check_failed("Connection error")`.
- `test_check_uses_fresh_cache` — cached `latest_version` higher → `update_available` without a
  network call (`update_checker.py:60-71`).
- `test_check_expired_cache_ignored` — cached timestamp older than `cache_duration` → performs
  the real (mocked) check (`update_checker.py:37`).
- `test_save_cache_writes_file` — `_save_cache` writes JSON with timestamp/version/url
  (`update_checker.py:43-55`).

### 2.2 `tests/test_config.py` (extend)

- `test_corrupted_config_recovered_with_defaults` — write invalid JSON to `CONFIG_FILE` → new
  `ConfigManager` falls back to defaults and saves (`config.py:20-22`).
- `test_get_network_merges_only_falsy` — config with `network: {"version_check_url": ""}` keeps
  the default URL (`config.py:41-46`).
- `test_get_network_keeps_custom_values` — non-empty custom values override defaults.
- `test_set_overwrites_and_persists` — `set` persists immediately; a second instance sees it
  (extend existing roundtrip, `config.py:27-29`).

### 2.3 `tests/test_persistence.py` (extend)

- `test_download_queue_corrupted_file_returns_empty` — invalid JSON in queue file → `_load()`
  returns `{}` (`download_queue.py:13-20`).
- `test_download_queue_add_overwrites` — re-`add` same id updates url/progress
  (`download_queue.py:22-24`).
- `test_download_queue_update_progress_unknown_is_noop` — updating a missing id doesn't raise
  (`download_queue.py:26-29`).
- `test_download_state_expired_returns_none` — write a state with a `timestamp` older than
  `DOWNLOAD_STATE_DURATION` → `load_state()` returns `None` (`download_state.py:36-37`).
- `test_download_state_corrupted_returns_none` — invalid JSON → `None` (`download_state.py:39-40`).
- `test_download_state_missing_file_returns_none` — `load_state()` before any save → `None`
  (`download_state.py:30-31`).

### 2.4 `tests/test_extractor.py` (extend)

`extract_zip` is well covered; `extract_7z` is not.

- `test_extract_7z_missing_binary` — `extract_7z("/no/7z", ...)` → `(False, "7-Zip not found")`
  (`extractor.py:49-50`).
- `test_extract_7z_missing_archive` — `extract_7z("7z", "/no/archive", ...)` →
  `(False, "Archive not found")` (`extractor.py:51-52`).
- `test_extract_7z_subprocess_error` — monkeypatch `subprocess.run` to raise
  `CalledProcessError` → `(False, "7z error: ...")` (`extractor.py:57-58`).
- `test_extract_7z_timeout` — monkeypatch `subprocess.run` to raise `TimeoutExpired` →
  `(False, "7z timeout (5 minutes)")` (`extractor.py:59-60`).
- `test_extract_7z_success` — fake `subprocess.run` returning success → `(True, "OK")`.
- `test_rejects_windows_drive_absolute_path` — zip member `C:/evil.txt` → `(False, ...)`
  (the drive-letter branch `extractor.py:27` is currently only covered by the POSIX-absolute
  test, not the `name[:2].isalpha()` case).

### 2.5 `tests/test_detection.py` (extend)

- `test_has_valid_exe_missing_path` — `_has_valid_exe("/no/such")` → `False` (`detection.py:12-14`).
- `test_parse_steam_library_paths_missing_vdf` — non-existent vdf → `[]`
  (`detection.py:62-74`).
- `test_parse_steam_library_paths_malformed` — garbage bytes → `[]` (decode/binary path).
- `test_steam_vdf_candidates_darwin` — monkeypatch `sys.platform` to `darwin` → the mac path is
  returned (`detection.py:44-50`).
- `test_find_game_returns_none_when_nothing_found` — registry and steam both empty, off-win32 →
  `None` (`detection.py:121-151`).

### 2.6 `tests/test_admin.py` (extend)

- `test_matches_win32_protected_boundaries` — exact prefix, trailing backslash, different
  casing (`admin.py` win32 helper, mirrors existing `test_matches_win32_protected`).
- `test_requires_admin_posix_fast_path_for_other_roots` — e.g. `/`, `/tmp`-style writable roots
  behave consistently (document behavior, don't assert the OS default).

### 2.7 `tests/test_ui_defaults.py` (extend)

- `test_persist_valid_path_returns_none_for_invalid` — invalid input leaves config untouched
  and returns `None` (`main_window.py:271-280`); needs a fake config object.
- `test_persist_valid_path_persists_and_returns` — valid path is written to the fake config.
- `test_startup_detect_message_whitespace_only` — `"  \t  "` → no-saved message
  (currently only `""` and `"   "` are tested).
- `test_game_folder_state_dir_with_trailing_slash` — `str(tmp_path) + os.sep` with a valid exe
  still resolves valid (exercises the `strip()` in `_persistable_game_path`, `main_window.py:53`).

---

## Phase 3 — Worker/UI modules requiring Qt (run headless, no event loop)

These import `PyQt6.QtCore` but their logic can be exercised without a `QApplication`. They can
live in the same `tests/` tree; signals are just callable objects.

### 3.1 `tests/test_uninstall_worker.py` — `UninstallWorker` (`workers/uninstall_worker.py`)

- `test_uninstall_missing_folder` — `uninstall_dlc("NOPE")` → `(False, "DLC folder not found...")`
  (`uninstall_worker.py:34-35`).
- `test_uninstall_file_not_directory` — create a file named `EP01` → `(False, "Not a directory...")`
  (`uninstall_worker.py:36-37`).
- `test_uninstall_success_deletes_folder` — real folder with a child file → `(True, "OK")` and
  the dir is gone (`uninstall_worker.py:38-42`).
- `test_uninstall_permission_error` — monkeypatch `shutil.rmtree` to raise `PermissionError` →
  `(False, "Permission denied...")` (`uninstall_worker.py:43-44`).
- `test_run_cancelled_skips_remaining` — set `_cancelled` after first item → remaining ids not
  processed (`uninstall_worker.py:23-25`).

### 3.2 `tests/test_logging_util.py` — `ImprovedLogger` (`logging_util.py`)

Use a fake widget exposing `append(text)` and `ensureCursorVisible()` to avoid Qt widgets.

- `test_log_writes_to_file_logger` — after `log("x")` a log file exists under
  `AppPaths.LOG_FILE` (`logging_util.py:47-57`); needs the `isolated_app_paths` fixture pattern
  from `test_config.py`.
- `test_log_colorized_by_level` — `"ERROR"` text produces a `<font color="#ff6b6b">` wrapped
  line; `"OK"` produces green (`logging_util.py:62-67`).
- `test_log_no_widget_still_logs_to_file` — `widget=None` doesn't crash.
- `test_export_logs_missing_file` — `export_logs()` with no log file → `(False, "No log file found")`
  (`logging_util.py:84-85`).
- `test_export_logs_copies_file` — with a log file and an explicit `target_path` → `(True, path)`
  and contents copied (`logging_util.py:101-107`). Mock `_reveal_in_explorer` to keep it quiet.

### 3.3 `tests/test_single_instance.py` — `SingleInstanceLock` (`utils/single_instance.py`)

- `test_acquire_release_roundtrip` — `acquire()` → `is_locked`; `release()` → socket closed.
- `test_acquire_after_release_reuses` — release then re-acquire works (port range, `SO_REUSEADDR`).
- `test_is_already_running_true_while_held` — acquire in one lock, `is_already_running` → `True`.
- `test_is_already_running_false_when_free` — no lock held → `False`.
- `test_acquire_falls_through_port_range` — monkeypatch `socket.socket` to fail for the first few
  ports then succeed (or use a range where the port is occupied).

### 3.4 `tests/test_install_worker.py` — `InstallWorker` (`workers/install_worker.py`)

Heavier — target the deterministic pieces first.

- `test_install_single_unknown_dlc` — `_install_single("NOPE")` → `(False, "DLC not found in database")`
  (`install_worker.py:88-90`).
- `test_save_download_state_writes_queue_and_state` — stub `_download_queue`/`_download_state`
  and a fake `db`; assert `add`/`save_state` called with expected args (`install_worker.py:77-85`).
- `test_pause_saves_state` — `pause()` calls `_save_download_state()` (`install_worker.py:62-68`).

---

## Test double / fixture conventions to reuse

- **Isolated paths**: `monkeypatch.setattr(AppPaths, "CONFIG_FILE", tmp_path / "config.json")`
  (and the other file attrs) — already the pattern in `tests/test_config.py:8-12` and
  `tests/test_persistence.py:9-14`. Add a shared `conftest.py` fixture (e.g. `isolated_app_paths`)
  so new suites reuse it instead of duplicating it.
- **Network stubbing**: `monkeypatch.setattr(module, "requests", fake_module)` or
  `monkeypatch.setattr(requests.Session, "get", fake)`. Prefer patching the module attribute so
  `Session()` construction stays real.
- **Fake widgets**: any object with the methods the code calls (e.g. `append`,
  `ensureCursorVisible`, `setValue`). Define a tiny `FakeWidget`/`FakeLogger` in each test file
  (pattern already used in `tests/test_extractor.py:7-9` and `tests/test_sevenzip.py:9-14`).

## Verification

```bash
python -m pytest            # or: .venv/bin/python -m pytest
ruff check tests linua_updater
```

New tests must remain headless (no `QApplication`), deterministic, and must not perform real
network or filesystem writes outside `tmp_path`. Run the suite after each phase; keep existing
tests green.
