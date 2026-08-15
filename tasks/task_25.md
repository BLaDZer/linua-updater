# Task 25 — Log which database source is in use (remote / cache / fallback)

## How it works now

- `DLCDatabase._load()` (`linua_updater/core/database.py:37-48`) resolves the catalog through four branches — fresh cache, remote download, stale cache, hardcoded fallback — but nothing records **which** branch produced the payload. Callers only ever see the resulting catalog via `all()` / `get()`.
- The app log is `AppPaths.LOG_FILE` (`updater.log`), written by `ImprovedLogger` (`linua_updater/logging_util.py`), which routes through the module-level `logging.getLogger("LinuaUpdater")` handler (`logging_util.py:38-45`). A message is only visible in the UI panel when the line goes through an `ImprovedLogger` that was constructed with a widget.
- `DLCDatabase()` is constructed fresh in several places: `linua_updater/__main__.py:44` (startup, before any logger exists), `linua_updater/ui/main_window.py` via `self.db`, `linua_updater/ui/dialogs.py:407`, `linua_updater/utils/disk_space.py:13` (once per `get_dlc_size` call), and `linua_updater/workers/install_worker.py:37`. None of them report the source.
- So today the log cannot answer any of: was the database refreshed from remote, reused from cache, or the built-in hardcoded data.

## How it should work

- `DLCDatabase` records which source produced its payload as `self.source`, and exposes a ready-to-log sentence via `source_description()`. `DLCDatabase` itself does **not** log — callers route the sentence through `ImprovedLogger` so the line lands in both the file log and, when a widget is attached, the UI panel.
- The line is written once at startup by `LinuaUI` (covering the app's persistent `self.db`) and once per `InstallWorker` (which builds its own instance). The ephemeral instances built by the uninstall dialog and `DiskSpaceChecker.get_dlc_size` do not re-log, so the log stays one line per meaningful instance instead of one per `DLCDatabase()` construction.
- The message always identifies the source explicitly, distinguishing a fresh cache from a reused (expired-but-parseable) one:

  | source | message |
  | --- | --- |
  | remote download succeeded | `DLC database: refreshed from remote (<url>)` |
  | fresh cache | `DLC database: loaded from cache (<cache file>)` |
  | stale cache reused after failed/empty download | `DLC database: loaded from stale cache (<cache file>, ~N h old)` |
  | hardcoded fallback | `DLC database: using built-in fallback data` |

  These map to the three user-facing cases — "refreshed from remote", "used from cache", "used internal hardcoded data" — with the stale-cache variant kept explicit (it still counts as "used from cache", just older than the TTL).

## What needs fixing

1. `linua_updater/core/database.py`:
   - `_load()` (`database.py:37-48`) sets `self.source` on `self` in every return path:
     - fresh cache → `"cache"`;
     - successful `_download()` → `"remote"`;
     - stale cache reuse → `"stale_cache"`;
     - fallback → `"fallback"`.
   - `_load_cache()` (`database.py:50-60`) records the cache file's age so the stale branch can report it — e.g. store `self._cache_age_h = int((time.time() - data.get("timestamp", 0)) / 3600)` only when it actually reads a parseable cache (so the "cache" and "stale_cache" branches can reuse it; the remote/fallback branches never use it).
   - Add a small method, e.g.:
     ```python
     def source_description(self):
         if self.source == "remote":
             return f"DLC database: refreshed from remote ({self.db_url})"
         if self.source == "stale_cache":
             return f"DLC database: loaded from stale cache ({self.cache_file}, ~{self._cache_age_h} h old)"
         if self.source == "fallback":
             return "DLC database: using built-in fallback data"
         return f"DLC database: loaded from cache ({self.cache_file})"
     ```
     (any top-level *non-`dlc`* keys, size enrichment and the resolution order are untouched).
2. `linua_updater/ui/main_window.py`:
   - In `LinuaUI.__init__`, directly after `self.logger = ImprovedLogger(self.log_text)` (`main_window.py:123`), add:
     ```python
     self.logger.log(self.db.source_description(), "INFO")
     ```
     This is the startup instance built in `__main__.py:44`, so the user immediately sees the answer in both `updater.log` and the in-app log panel. No `__main__.py` change is needed — the message is emitted once the widget logger exists.
3. `linua_updater/workers/install_worker.py`:
   - After `self.db = DLCDatabase()` (`install_worker.py:37`), add:
     ```python
     self.logger.log(self.db.source_description(), "INFO")
     ```
     The worker's `ImprovedLogger` is created without a widget (`install_worker.py:36`), so this lands in the file log only.
4. Leave `dialogs.py:407`, `disk_space.py:13` and `__main__.py` untouched — those construct transient throwaway instances whose catalog matches the already-logged shared database, and `DiskSpaceChecker` builds one per DLC id, so logging there would spam the log.
5. Tests (`tests/test_database.py`, which already runs offline via `tests/conftest.py`):
   - Assert `db.source` for every branch, reusing the existing fixtures:
     - fresh cache → `"cache"` (no download);
     - expired cache + successful download → `"remote"` and the cache file rewritten;
     - expired cache + failed download → `"stale_cache"`;
     - missing cache + failed download → `"fallback"`.
   - Assert `source_description()` substrings: the URL on `"remote"`, the cache file path on `"cache"` / `"stale_cache"`, the `~N h old` fragment on `"stale_cache"`, and `built-in fallback data` on `"fallback"`.

## Notes / out of scope

- `DLCDatabase` stays logger-agnostic; `ImprovedLogger` remains the single path into both the file handler and the UI widget, so no call site changes signature.
- Repeated constructions of the shared catalog (dialog, disk-space checks) intentionally do not log; if per-instance diagnostics are ever wanted, a DEBUG-level line could be added later without affecting the INFO messages above.