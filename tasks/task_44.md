# Task 44 — Fix tests and mypy after priority-based main source selection

## Context

Commit `685cb48` ("added default priorities to pick main download source") changed how a DLC's
main download source is chosen. Instead of always using the entry's direct `url` as the main
source, the highest-priority source is now picked (magnet=100, parts=50, url=30), with the
remaining sources kept as mirrors sorted by priority descending.

This broke the test suite and the mypy type check.

## How it works now

- `DLCInfo.from_entry` (`core/models.py:168-199`) builds a list of `DownloadSource` objects
  (top-level `magnet`/`url`/`parts` plus parsed `mirrors[]` entries), sorts them by
  `getPriority()` descending, then pops the first element as the main source.
- Default priorities were added in `constants.py:84-86`:
  `DOWNLOAD_SOURCE_DEFAULT_PRIORITY_FOR_MAGNET = 100`,
  `DOWNLOAD_SOURCE_DEFAULT_PRIORITY_FOR_PARTS = 50`,
  `DOWNLOAD_SOURCE_DEFAULT_PRIORITY_FOR_URL = 30`.
- `DownloadSource.__init__` now requires `source_type: str` (was `Optional[str]`), and
  `DownloadSource.parts()` dropped its `checksums` parameter.

## What needs fixing

1. **`linua_updater/core/models.py`** — three mypy errors and one runtime bug:
   - `from_dict` passes `Optional` values into params that now require `str`:
     `models.py:117` (`raw.get(DATABASE_DLC_KEY_URL)`), `models.py:119`
     (`raw.get(DATABASE_DLC_KEY_MAGNET)`), `models.py:121` (`source_type` may be `None`).
     Fix with `cast(str, ...)` (add `cast` to the `typing` import).
   - `from_entry` crashes with `IndexError: pop from empty list` for entries with no sources
     (e.g. `{}`): `main = mirrors.pop(0)` at `models.py:197` must become
     `main = mirrors.pop(0) if mirrors else None`.

2. **`tests/test_models.py`** — update for the new priority semantics:
   - `test_dlc_info_legacy_magnet_and_parts_mirrors` (`:146`): entry with `url` + `magnet` +
     `parts` now yields main = magnet (priority 100, inherits the entry checksum) and
     mirrors = `[parts(50), url(30)]`, not main = url.
   - `test_dlc_info_no_main_source_without_url` (`:232`): a magnet-only entry now has
     main = magnet (not `None`). Rewrite accordingly and add a new test for a completely empty
     entry asserting `getMainDownloadSource() is None` and `getMirrors() == []`.

3. **`tests/test_install_worker.py`** — update for magnet-first routing:
   - `test_install_single_cancelled_no_fallback` (`:73`): magnet is now the first source tried.
     Make `FakeTorrentDownloader.download` return `(False, "Cancelled")`; assert
     `magnet_calls == ["magnet:?xt=foo"]`, `direct_downloads == []`, msg `"Cancelled"`.
   - `test_install_single_url_first_then_magnet_mirror` (`:138`): rename to reflect magnet-first
     order; the final message becomes `"All download attempts failed"` (url mirror is last);
     calls stay `magnet_calls == ["magnet:?xt=foo"]` and
     `direct_downloads == ["http://example.com/EP01.zip"]`.

4. **`tests/test_installers.py`** — no edits needed; `test_single_missing_url`,
   `test_multipart_no_parts`, `test_torrent_missing_magnet` pass once the `IndexError` in
   `from_entry` is fixed.

## Tests

- `./scripts/check.sh` must pass: `ruff check`, `mypy`, and the full pytest suite
  (expect 294 passing).

## Docs

- `docs/architecture.md` (`:125`, `:141`, `:242`) still states the main source is the entry's
  direct `url`. Update to describe priority-based selection (highest priority becomes main,
  magnet > parts > url by default).

## Notes / out of scope

- The magnet-becomes-main behavior change is intentional per the commit message; tests are
  updated to match it, not to preserve url-first selection.
