# Task 39 — `DLCInfo` domain model for the DLC catalog + source-based install routing

## Context

`DLCDatabase.all()` / `DLCDatabase.get()` (`linua_updater/core/database.py:110-114`) still leak raw dictionaries from `database.json`. Every consumer reaches into them with string keys (`info['name']`, `info['url']`, `info['parts']`, `info['magnet']`, `info['checksum']`, `info['size']`), and the install routing in `InstallWorker._install_single` (`linua_updater/workers/install_worker.py:97-160`) decides the download strategy by sniffing keys (`installer_kind`, `linua_updater/workers/install_worker.py:20-25`) with a `magnet → parts → url` priority.

Desired end state: the catalog is exposed as a typed `DLCInfo` value object (with `DownloadSource` and `CheckSums` collaborators), and installation picks the download source explicitly: the **main** source (always the `url` direct download when present) first, then a prioritized list of **mirrors**.

## How it works now

- `DLCDatabase` keeps the whole remote payload under `self.data` and exposes the `dlc` mapping verbatim: `all()` returns `self.dlc` (dict id → raw dict), `get(dlc_id)` returns a single raw dict or `None` (`database.py:110-114`). `_apply_sizes` injects `size` from `SIZE_ESTIMATES` into each raw dict (`database.py:48-51`).
- Consumers read raw keys: `install_worker.py:90-92` (`info['url']`), `disk_space.py:14-16` (`info.get('size')`), `dialogs.py:459-460` (`info.get('name')`), `main_window.py:440` (`.items()` → `(id, info)`), `installers.py` (`self.info.get('url'|'parts'|'magnet'|'size'|'name'|'checksum')`).
- `installer_kind(info)` (`install_worker.py:20-25`) routes `magnet` → `TorrentInstaller`, `parts` → `MultiPartInstaller`, else `SingleDLCInstaller`. Priority is **magnet first**, then parts, then url (`install_worker.py:107-148`); a failed magnet falls back to parts/url by mutating a dict copy (`install_worker.py:113-133`).
- The catalog format is dual:
  - legacy (current `database.json`): top-level `url`, optional `magnet` / `parts[]` (string arrays), optional `checksum`;
  - new (see `database_draft.json:35-84`): top-level `url` and a structured `mirrors` array of `{type: 'parts'|'magnet'|'url', ..., checksum, priority}`, where a `parts` source nests `parts: [{type: 'url', url, checksum}]`.
- Every source today shares the entry-level `checksum`, and the `magnet` source in the draft can carry its own `priority` (e.g. 20, `database_draft.json:82`).

## How it should work

- `DLCDatabase.all()` returns `dict[str, DLCInfo]`; `.get(dlc_id)` returns a single `DLCInfo` or `None`. Call-site shapes that only use keys/len/items keep working.
- Three new value classes in `linua_updater/core/models.py`:
  - `CheckSums` — `getSha256()`, `getSha1()`, `getMd5()`; a `get(alg)` helper so `verify_file_checksums` (`linua_updater/core/checksum.py:9`) keeps working unchanged on either a dict or a `CheckSums`.
  - `DownloadSource` — `getType()` (`'url' | 'parts' | 'magnet'`), `getSource()` (str or `None`), `getParts()` (list of `DownloadSource`; only for a `parts` container), `getCheckSums()` (`CheckSums` or `None`), `getPriority()` (int, from the `priority` key, default `0`).
  - `DLCInfo` — `getId()`, `getName()`, `getSize()` (bytes or `None`), `getMainDownloadSource()` (`DownloadSource` or `None`), `getMirrors()` (list of `DownloadSource`).
- **`getMainDownloadSource()` is the `url` direct download** whenever the entry has a `url`; otherwise `None`. It carries the entry-level `checksum` when present.
- **`getMirrors()`** collects, in this order, then sorts stable by `getPriority()` descending (higher priority on top):
  1. legacy top-level `magnet` (kept for old databases) → a `'magnet'` `DownloadSource` with priority 0;
  2. legacy top-level `parts[]` (kept for old databases) → a `'parts'` container whose `getParts()` are `'url'` sources, priority 0;
  3. the new `mirrors[]` array, each parsed via `DownloadSource.from_dict` (own `type`/`source`/`parts`/`checksum`/`priority`).
  - Ties keep collection order, so for legacy entries `magnet` still precedes `parts` (preserves today's precedence); on a new-format entry like `database_draft.json` EP06 the `magnet` (priority 20) sorts above the `parts` mirror (priority 0).
- **Install routing** becomes explicit source iteration in `_install_single`: try `getMainDownloadSource()` first, then `getMirrors()` in returned order. Each `DownloadSource` maps to an installer by `getType()`: `'url'` → `SingleDLCInstaller`, `'parts'` → `MultiPartInstaller` (parts resolved from `getParts()`), `'magnet'` → `TorrentInstaller`. A failed source logs a `WARNING` and moves to the next mirror; a `Cancelled` result (or `self._cancelled`) ends the attempt immediately with no fallthrough (matches task_36).
- Installers no longer sniff a dict: they receive the `DLCInfo` (for `getName`/`getSize`) plus the chosen `DownloadSource` (for `getSource()`/`getParts()`/`getCheckSums()`).
- `_save_download_state` records the main source URL in the download queue (`install_worker.py:87-95`).
- The new model is compatible with both catalog formats; `database.json` is **not** migrated in this task (legacy keys are still parsed).

## What needs fixing

1. **`linua_updater/core/models.py` — three new classes**
   - `CheckSums.__init__(self, sha256=None, sha1=None, md5=None)` + getters + `get(alg)`; `@classmethod from_dict(raw)` accepting `{'sha256'|'sha1'|'md5': ...}` (skip absent/empty values).
   - `DownloadSource.__init__(self, source_type, source=None, parts=None, checksums=None, priority=0)`; getters; `@classmethod from_dict(raw)` for structured mirror dicts (`type` required; `url`/`magnet` → `getSource()`, `parts[]` → nested `DownloadSource` list, `checksum` → `CheckSums`, `priority` → int, non-int/absent → 0); conveniences `url(...)` / `magnet(...)` / `parts(...)` used by the legacy parsers.
   - `DLCInfo.from_entry(dlc_id, raw)`:
     - `main` = a `'url'` source from `raw['url']` (checksums from `raw['checksum']`) when present, else `None`;
     - mirrors = legacy `magnet`, legacy `parts` (as string→url sources), then each `mirrors[]` entry;
     - each mirror without an explicit `checksum` inherits the entry-level `raw['checksum']` (keeps today's single-archive guarantee);
     - sort stable by `priority` desc;
     - `getSize()` returns `raw['size']` (already injected by `_apply_sizes`, `database.py:48-51`) or `None`.
2. **`linua_updater/core/database.py`**
   - Keep `self.dlc` (raw) and `self.data`; add `self._infos` built by `_build_infos()` after `_apply_sizes()` in both `__init__` (`database.py:31-33`) and `refresh()` (`database.py:43-45`).
   - `all()` → `dict[str, DLCInfo]`; `get(dlc_id)` → `DLCInfo | None` via `self._infos`.
3. **`linua_updater/core/installers.py`** — port the three installers
   - New ctor shape: `(dlc_id, info, source, game_path, downloader, extractor, [seven_path,] logger, stats=None)` where `info` is a `DLCInfo` and `source` the chosen `DownloadSource`.
   - `SingleDLCInstaller.run` (`installers.py:29-83`): `url = source.getSource()`, `expected_size = info.getSize()`, `dlc_name = f"{dlc} - {info.getName()}"`, `verify_file_checksums(temp, source.getCheckSums())`.
   - `MultiPartInstaller.run` (`installers.py:106-169`): `parts = source.getParts()`; `for i, part in enumerate(parts): url = part.getSource()`. (Per-part `getCheckSums()` is available now but not yet verified — leave current behavior.)
   - `TorrentInstaller.run` (`installers.py:191-264`): `magnet = source.getSource()`, `expected_size = info.getSize()`, `dlc_name` from `info.getName()`, `verify_file_checksums(primary, source.getCheckSums())`.
4. **`linua_updater/workers/install_worker.py`**
   - Replace `installer_kind(info)` with a `DownloadSource`-based helper (or inline `source.getType()`); keep a small pure helper `installer_kind(source)` returning `'magnet' | 'parts' | 'single'` for testability.
   - Rewrite `_install_single` (`install_worker.py:97-160`) as the source-loop described above; register each source's downloader in `_active_downloaders` (smart downloader for url/parts, `TorrentDownloader` for magnet) exactly as today so `cancel/pause/resume` (`install_worker.py:61-85`) still cover it; deregister in `finally`.
   - `_save_download_state` (`install_worker.py:87-95`): `main = info.getMainDownloadSource()`; enqueue only when `main and main.getSource()`.
5. **`linua_updater/utils/disk_space.py`** — `get_dlc_size` (`disk_space.py:11-17`): `info = db.get(dlc_id)`, `size = info.getSize() if info else None`, keep `SIZE_ESTIMATES` fallback.
6. **`linua_updater/ui/dialogs.py`**
   - `DLCSelector.populate` (`dialogs.py:343-344`): `info['name']` → `info.getName()`.
   - `UninstallDialog.populate_dlc` (`dialogs.py:459-460`): `info = db.get(dlc_id)`, `name = info.getName() if info else 'Unknown'`.
7. **`linua_updater/ui/main_window.py`** — verify the `.all()` call sites (`main_window.py:309-310`, `440`, `475`) keep working with `dict[str, DLCInfo]`; `.keys()`, `.items()` truthiness and `len()` are unaffected.
8. **Tests**
   - `tests/test_models.py` — add coverage: legacy url-only entry (main url, empty mirrors); legacy `magnet`/`parts` mirrors (priority 0, order); new `mirrors[]` parsing incl. `parts` container with nested url sources and `priority` sorting (`database_draft.json` EP06 shape); `CheckSums` getters + `get(alg)`; `getSize` default/None; `getMainDownloadSource` `None` when no url.
   - `tests/test_database.py` — convert dict assertions to accessors (`db.all()["EP01"].getSize()`/`.getName()`, `db.get("EP01").getName()`, `db.all()["EP01"].getMainDownloadSource().getSource()`); assert EP01 main is `'url'`, fallback EP06 yields 1 parts mirror with 7 url children, priority 0.
   - `tests/test_installers.py` — update `_single`/`_multipart`/`_torrent` helpers to build a `DLCInfo` + `DownloadSource` from the existing dict fixtures (e.g. `DLCInfo.from_entry(...)` plus main/mirror selection); test scenarios unchanged.
   - `tests/test_install_worker.py` — `FakeDb` returns `DLCInfo` values; rewrite routing tests for the new **url-first** order (old magnet-first expectations inverted); keep pure `installer_kind` tests (now on `DownloadSource`); keep the "cancelled → no fallthrough" guarantee.
   - Run `./scripts/check.sh` (tests + ruff) before marking done.
9. **Docs**
   - `tasks/task_39.md` — this file.
   - `docs/architecture.md` — module layout + `DLCDatabase` row (returns `DLCInfo`); install-flow section: routing is now `url` (main) → `mirrors` by priority; add `DLCInfo`/`DownloadSource`/`CheckSums`.
   - `README.md` — note the fallback order (direct url, then prioritized mirrors incl. magnet).
   - `database.json` left unchanged (legacy format still parsed); `database_draft.json` cited as the new-format reference.

## Notes / out of scope

- `database.json` is not rewritten to the new `mirrors` format; the parser accepts both old and new key layouts for backward compatibility.
- `SmartDownloader.mirrors` (`downloader.py:15`) is the host-domain proxy-mirror map for single downloads — unrelated to DLC source mirrors; no change.
- Per-part checksums are exposed via `getParts()[i].getCheckSums()` but the multipart installer still does not verify them (existing behavior).
- Disk-space math unchanged (`getSize()` returns the same injected `size`).
- Behavioral change to document in the release notes: DLC source order flips from `magnet → parts → url` to `url (main) → mirrors by priority`; for legacy entries without a `url` the main source is `None` and only mirrors are tried.