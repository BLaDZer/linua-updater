# Task 26 — Reset the database cache from the Settings window

## How it works now

- `SettingsDialog` (`linua_updater/ui/dialogs.py:75-122`) shows two groups — "Parallel Download Settings" and "Network Settings" — inside a fixed 400×300 modal window, followed by Save/Cancel buttons. It has no knowledge of the DLC database or any logger.
- `LinuaUI.db` is a single `DLCDatabase` instance built once at startup (`linua_updater/__main__.py:44`, passed into `LinuaUI`) and consumed throughout the main window — `update_dlc_status` (`main_window.py:290-308`), `DLCSelector` in `on_update` (`main_window.py:464-465`) and the resume-download check (`main_window.py:708-739`). It is loaded once in `__init__` (`database.py:31`) and there is **no runtime path to invalidate the cache or force a re-fetch**.
- The remote fetch performs `requests.get(self.db_url, timeout=10)` (`database.py:69`), so a forced refresh can block the calling thread for up to 10 seconds. The resolution order is fresh cache → remote → stale cache → fallback (`database.py:37-48`), with the cache file `AppPaths.DATABASE_CACHE_FILE` (`database_cache.json`, 24 h TTL, `paths.py:54/65`).
- `LinuaUI.show_settings` (`main_window.py:364-374`) opens `SettingsDialog(self)` and passes nothing but the parent.

## How it should work

- The Settings window gains a third group **"Database"** containing a **"Reset database cache"** button.
- Clicking it **invalidates** the cache (deletes `AppPaths.DATABASE_CACHE_FILE`) and **refreshes from the remote source** — the previously downloaded `database.json`, falling back through the normal resolution order.
- Because it mutates the shared `LinuaUI.db` instance in place, a successful reset is visible immediately everywhere the app reads the catalog (the 3-second `dlc_check_timer` in `main_window.py:138-146` re-runs `update_dlc_status`; the next `DLCSelector` uses the new entries).
- **Every outcome is logged** through `ImprovedLogger` (`LinuaUI.logger`, which writes to both `updater.log` and the in-app panel):

  | step | message |
  | --- | --- |
  | button clicked | `Database cache reset requested...` (`INFO`) |
  | refresh succeeded | `DLC database: refreshed from remote (<url>)` via `source_description()` (`INFO`) |
  | refresh failed | `Database cache reset failed: <source_description()>` (`WARNING`) |
  | unexpected exception | `Database cache reset failed: <error>` (`ERROR`) |

- The refresh runs on a **background `QThread`** so the modal dialog stays responsive during the up-to-10 s network call: while running, the button is disabled and its text becomes `Refreshing...`, then re-enabled once the result is handled.
- Since the cache file is deleted up front, the refresh resolves to exactly two outcomes — `remote` (success, cache rewritten by `_save_cache`) or `fallback` (failure) — which map cleanly to the success/WARNING log lines above.

## What needs fixing

1. `linua_updater/core/database.py`:
   - Extract the size-enrichment loop (`database.py:33-35`) into a private `_apply_sizes()` helper and call it from both `__init__` and `refresh()` so the reload path re-enriches exactly as construction does.
   - Add:
     ```python
     def refresh(self):
         """Invalidate the cache file and reload, re-running the resolution order.
         Returns True when the payload came from the remote server."""
         try:
             if self.cache_file.exists():
                 self.cache_file.unlink()
         except OSError:
             pass
         self.data = self._load()
         self.dlc = self.data.get("dlc", {})
         self._apply_sizes()
         return self.source == "remote"
     ```
   - With the cache gone, `_load()` either downloads a valid payload (rewrites the cache via `_save_cache`, `source == "remote"`) or falls through to the hardcoded `DEFAULT_DATABASE_FALLBACK` (`source == "fallback"`); the stale-cache branch can no longer match, so the two-outcome guarantee holds. `source_description()` (`database.py:104-112`) stays the single source of the logged sentence.
2. New `linua_updater/workers/database_refresh_worker.py` — a tiny `QObject` modeled on `DiagnosticsWorker` (`linua_updater/workers/diagnostics_worker.py:6-16`):
   ```python
   class DatabaseRefreshWorker(QObject):
       result_ready = pyqtSignal(bool)

       def __init__(self, db):
           super().__init__()
           self.db = db

       def run(self):
           self.result_ready.emit(self.db.refresh())
   ```
3. `linua_updater/ui/dialogs.py` — `SettingsDialog`:
   - Constructor becomes `def __init__(self, parent=None, db=None, logger=None):` storing `self.db` / `self.logger`.
   - Grow the fixed size (`dialogs.py:79`, currently 400×300) enough for a third group, e.g. `setFixedSize(420, 440)`.
   - Add a `QGroupBox("Database")` between the Network group (`dialogs.py:95-107`) and the buttons: a hint label ("Delete the cached DLC database and download the latest from the remote source.") and `self.reset_db_btn = QPushButton("Reset database cache")` wired to `reset_database_cache`.
   - `reset_database_cache()`:
     - guard against re-entry while running; `self.logger.log("Database cache reset requested...", "INFO")` when a logger is present;
     - disable the button and set `Refreshing...`;
     - build the `DatabaseRefreshWorker` on a fresh `QThread` (pattern in `main_window.py:334-340`), connect `result_ready` to a `_on_db_reset_done(bool)` slot, start it;
     - `_on_db_reset_done(ok)` re-enables the button (`Reset database cache`) and logs: `ok` → `self.logger.log(self.db.source_description(), "INFO")`; otherwise → `self.logger.log("Database cache reset failed: " + self.db.source_description(), "WARNING")`.
   - Keep the worker thread referenced on the dialog (`self._db_reset_thread` / `self._db_reset_worker`) and clean it up (quit/wait/deleteLater) on completion so the dialog can be closed safely.
4. `linua_updater/ui/main_window.py` — `show_settings` (`main_window.py:365`): `dlg = SettingsDialog(self, db=self.db, logger=self.logger)`. The existing settings-loading lines (`main_window.py:366-368`) are unchanged.
5. Tests (`tests/test_database.py`, offline via `tests/conftest.py`; reuse the `isolated_db_env` / `cache_file` fixtures):
   - `test_refresh_with_fresh_cache_replaces_it_from_remote` — seed a fresh cache, stub `requests.get` to return a different valid payload → `refresh()` returns `True`, `db.source == "remote"`, the cache file is rewritten with the new `database` payload, and `db.data` / `get_key` reflect the new download.
   - `test_refresh_failure_removes_cache_and_falls_back` — seed a fresh cache with the default failing stub (404) → `refresh()` returns `False`, `db.source == "fallback"`, the cache file no longer exists, `len(db.all()) == 109`.
   - `test_refresh_reapplies_size_enrichment` — after a successful refresh, `db.all()["EP01"]["size"] == 1900000000` again.
   - No dialog/thread tests: the worker and dialog are Qt UI; the repository has no `pytest-qt`, so only the pure `DLCDatabase.refresh()` logic is unit-tested (matching the existing convention).

## Notes / out of scope

- The dialog remains modal while the refresh thread runs; the button's disabled state gives feedback and prevents re-entry (the 10 s `timeout` bounds the wait, and `result_ready` re-enables it).
- `DLCDatabase` is otherwise used single-threaded in the main window, so this one-off background refresh needs no locking.
- Transient `DLCDatabase()` constructions — `install_worker.py:37`, `disk_space.py:13`, uninstall dialog `dialogs.py:407` — are untouched; they build their own copies from the (now refreshed) cache, so they pick up new data on the next install/check automatically.
- Cleaning the cache file is the whole invalidation; no new file format or constant is introduced.