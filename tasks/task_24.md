# Task 24 — Load the DLC catalog from a remote `database.json` with a cached fallback (database.py)

## How it works now

- `DLCDatabase` (`linua_updater/core/database.py`) hardcodes the entire 109-entry catalog as a dict literal inside `__init__` (`self.dlc`), then enriches every entry with an estimated `size` from the module-level `SIZE_ESTIMATES` table in `linua_updater/constants.py:19-40` (`database.py:158-160`).
- The class is constructed fresh in several places: `linua_updater/__main__.py:44` (startup, passed into `LinuaUI`), `linua_updater/ui/dialogs.py:407`, `linua_updater/utils/disk_space.py:13` (per `get_dlc_size` call), and `linua_updater/workers/install_worker.py:37`. All consumers only use `all()` / `get()`.
- The repo already ships the intended remote payload as `database.json` at the repo root: a top-level object whose `dlc` key holds the catalog. The same data is not yet loaded from anywhere — it is just duplicated by hand in `database.py`.

## How it should work

- `DLCDatabase` loads the remote file `database.json` (URL from constants) and caches **the whole payload** (all top-level keys, e.g. `version`, `updatedAt`, `dlc`, future keys) in the app state folder, mirroring how `ConfigManager` stores `config.json` (`linua_updater/utils/config.py`) and how `UpdateChecker` caches update checks (`linua_updater/workers/update_checker.py`).
- Cache file: `AppPaths.DATABASE_CACHE_FILE` = `BASE_DIR / "database_cache.json"`; TTL is `AppPaths.DATABASE_CACHE_DURATION` (24 h).
- Resolution order (TTL refresh like `UpdateChecker`):
  1. **Fresh cache** — if the cache file exists, parses, and is younger than the duration, its payload is used as-is (no network).
  2. **Remote download** — otherwise fetch `DEFAULT_DATABASE_URL`; a valid payload (HTTP 200 + `response.json()` that passes validation) replaces the cache and is returned.
  3. **Stale cache** — if the download failed or returned an invalid payload, a still-parseable (even expired) cache is reused.
  4. **Hardcoded fallback** — only when neither a usable cache nor a successful download exists, the former hardcoded catalog (now `DEFAULT_DATABASE_FALLBACK` in `linua_updater/constants.py`) is used.
- A payload is "valid" when it is a JSON object whose `dlc` key is a non-empty dict. Invalid JSON, a non-object body, or a missing/empty/`None` `dlc` all count as broken and cause fall-through to the next source.
- Cache file format: `{"timestamp": <epoch seconds>, "database": <entire server payload>}`.
- `SIZE_ESTIMATES` enrichment keeps running on every load, so cached and fallback entries get a `size` exactly as before.

## What needs fixing

1. `linua_updater/constants.py`:
   - Add `DEFAULT_DATABASE_URL = "https://raw.githubusercontent.com/BLaDZer/linua-updater/main/database.json"` (same `https://raw.githubusercontent.com/BLaDZer/linua-updater/main/...` form as `DEFAULT_VERSION_CHECK_URL`, `constants.py:8`).
   - Move the catalog dict literal out of `database.py` into `DEFAULT_DATABASE_FALLBACK` here, wrapped in the remote-file shape `{"dlc": {...}}` so loader code treats all sources uniformly. Move it **verbatim** (including `EP06`'s `mirrors` schema). `SIZE_ESTIMATES` stays as-is.
2. `linua_updater/paths.py`:
   - Add `DATABASE_CACHE_FILE = BASE_DIR / "database_cache.json"` (next to `CONFIG_FILE` / `UPDATE_CACHE_FILE`, `paths.py:52-54`).
   - Add `DATABASE_CACHE_DURATION = 86400` (next to the other cache durations, `paths.py:61-64`).
3. `linua_updater/core/database.py` — rework `DLCDatabase`:
   - Constructor params: `db_url=None`, `cache_file=None`, `cache_duration=None`, defaulting to `DEFAULT_DATABASE_URL`, `AppPaths.DATABASE_CACHE_FILE`, `AppPaths.DATABASE_CACHE_DURATION` so tests can isolate.
   - Helpers: `_load()` (orchestrates the 4-step order), `_load_cache(fresh_only=True)`, `_download()` (single `requests.get(..., timeout=10)` like `update_checker.py:75`), `_save_cache(payload)`, and a static `_is_valid(payload)`.
   - Store the whole payload as `self.data` and the DLC map as `self.dlc = self.data.get("dlc", {})`. Keep `all()`, `get()` and the existing size-enrichment loop unchanged. Add a forward-looking `get_key(key, default=None)` accessor for future top-level keys (not yet used by any caller).
   - The fallback path must `copy.deepcopy` `DEFAULT_DATABASE_FALLBACK` so size enrichment never mutates the module-level constant across instances.
   - No call sites change: `__main__.py`, `main_window.py`, `dialogs.py`, `disk_space.py`, `install_worker.py` keep working through `all()` / `get()`.
4. Tests (`tests/test_database.py` and a new `tests/conftest.py`):
   - `tests/conftest.py`: `autouse` fixture that points `AppPaths.DATABASE_CACHE_FILE` at a `tmp_path` file and stubs `linua_updater.core.database.requests.get` to fail (HTTP 404), so no test ever hits the real network or the real app-state directory. Tests needing download behavior override the stub per-test.
   - `tests/test_database.py`: keep `test_catalog_has_109_entries`, `test_size_enrichment_from_estimates`, `test_get` (now deterministic via the offline fixture) and add coverage for:
     - fresh cache is used and never triggers a download; non-`dlc` keys (e.g. `version`, `updatedAt`) are preserved and reachable via `data` / `get_key`;
     - expired cache triggers a download, and a successful download rewrites the cache;
     - missing cache + failed download + stale cache present → stale cache used;
     - missing cache + failed download + no cache → hardcoded fallback with the full 109-entry catalog, and no cache file is written;
     - broken remote (invalid JSON, or a body without a usable `dlc`) → falls back to the catalog;
     - corrupt / missing-`dlc` cache file is ignored;
     - size enrichment still applied to cached data.
   - `tests/test_disk_space.py` keeps passing unchanged (the conftest keeps its `DLCDatabase()` constructions offline).
5. `docs/architecture.md` — update the `DLCDatabase` row (`docs/architecture.md:130`) and the hardcoded-URL note (`docs/architecture.md:241`): the catalog is now fetched from `DEFAULT_DATABASE_URL`, cached under the app state folder, and falls back to `DEFAULT_DATABASE_FALLBACK`.

## Notes / out of scope

- `EP06` keeps its current `mirrors` schema in the fallback; the remote file's own per-entry schema (e.g. a plain `parts` list) passes through untouched — nothing here parses those fields.
- The remote payload is treated as a generic database. Today only `dlc` is consumed; future keys are read from `self.data` / `get_key()` with no restructuring.