# Task 40 — Fix installation statistics: per-DLC counting (models.py, install_worker.py)

## Context

The end-of-install "STATISTICS" block is computed by `InstallationStats.get_summary()` (`linua_updater/core/models.py:187-201`) from two sources: the `downloads` dict (populated only on the success path via `record_download`) and the flat `errors` list (one entry per failed downloader/source/part). This produces wrong numbers, e.g. after cancelling a run of a single DLC:

```text
[12:46:11] Progress: 1/1 (Success: 0, Failed: 1)
[12:46:11] Total: 0 DLC
[12:46:11] Success: 0
[12:46:11] Failed: 3
[12:46:11] === ERROR DETAILS ===
[12:46:11] EP07: All download attempts failed
[12:46:11] EP07: aria2c not found
[12:46:11] EP07: Part 5 failed: Cancelled
```

`Total` is 0 because nothing was downloaded. `Failed` is 3 because the three sources for `EP07` each recorded a separate error (`installers.py:50,64,70,145,159,216,258...`), but it is really 1 DLC.

## How it works now

- `get_summary()` (`linua_updater/core/models.py:187-201`) computes `total_dlc = len(self.downloads)`, `successful = len(self.downloads)` and `failed = len(self.errors)`.
- `self.downloads` (`models.py:171`) is keyed by `dlc_id` and only `record_download()` (called on the success path, e.g. `installers.py:74,163,262`) adds entries — one per successfully installed DLC. A DLC that is cancelled, fails all sources, or is never even submitted to the pool leaves no entry.
- `self.errors` (`models.py:161`) accumulates one dict per `record_error()` call. Installers call it for every failed source attempt, per failed part, per checksum failure, per extraction failure, and for exceptions (`installers.py:50,64,70,79,145,159,168,216,242,258,267`). So a single DLC can contribute several entries.
- The summary dict drives `MainWindow.on_stats_ready` (`linua_updater/ui/main_window.py:620-638`): `stats['total_dlc']` → "Total", `stats['successful']` → "Success", `stats['failed']` → "Failed", and `stats['errors']` → the ERROR DETAILS block.

## How it should work

- **Total** = the number of DLCs the user selected, not the number successfully downloaded.
- **Success** = number of distinct DLCs that were successfully installed. Because `record_download()` runs only on the success path and only once per DLC, `len(self.downloads)` already equals this. A DLC that succeeds from any source (i.e. at least one mirror) counts as one success — failed earlier mirror attempts must not reduce it.
- **Failed** = `Total - Success`, i.e. the DLCs that could not be installed. This also covers cancellation: DLCs that were never started, or whose result never arrived, are counted as failed.
- Counts are per DLC; the accumulation of per-attempt/per-source error entries no longer inflates `Failed`.
- The ERROR DETAILS block keeps listing every per-attempt error line (still useful for debugging) — only the counters change.

## What needs fixing

1. `linua_updater/core/models.py` — `InstallationStats`
   - Add `self.total_dlc = None` in `__init__` (`models.py:156-163`), alongside `downloads`/`errors`.
   - In `get_summary()` (`models.py:187-201`):
     - `total_dlc = self.total_dlc if self.total_dlc is not None else len(self.downloads)` (backward-compatible fallback for standalone/legacy use);
     - `successful = len(self.downloads)` (unchanged);
     - `failed = total_dlc - successful` (replaces `len(self.errors)`);
     - keep returning the raw `errors` list unchanged.
2. `linua_updater/workers/install_worker.py`
   - After `self.stats = InstallationStats()` (`install_worker.py:53`), set `self.stats.total_dlc = len(self.dlc_ids)` so the summary knows the selected DLC count even when nothing downloads.
3. `tests/test_models.py` — update existing expectations and add coverage
   - `test_summary_aggregates` (`tests/test_models.py:38-53`): set `stats.total_dlc = 3`; expect `total_dlc == 3`, `successful == 2`, `failed == 1`, size/speed assertions unchanged.
   - `test_summary_thread_safety` (`tests/test_models.py:56-74`): set `stats.total_dlc = 100`; expect `successful == 50`, `failed == 50`.
   - New: cancelled run — total set, errors recorded, no downloads → `successful == 0`, `failed == total_dlc`.
   - New: one DLC with three failed source attempts (3 error entries, no download) counts as `failed == 1` (not 3); two DLCs with interleaved failures/successes → `successful + failed == total_dlc`.
   - `test_record_download_tracks_bytes_and_speed` and `test_record_error_accumulates` remain valid (they assert on `downloads`/`errors` directly).
4. Run `./scripts/check.sh` (tests + ruff) before marking done.

## Docs

- `tasks/task_40.md` — this file.
- `docs/architecture.md` — update the `InstallationStats` row (`docs/architecture.md:118`) to state that it records per-DLC size/duration/errors and that the summary counts are per DLC: `Total` = selected count, `Failed` = `Total - Success`.

## Notes / out of scope

- `Success` semantics are unchanged (`len(self.downloads)`) and already per-DLC; only `Total`/`Failed` are fixed.
- Working-tree counters (`MainWindow.successful_count`/`failed_count`, driven per `result_ready`) are left as-is — they count submitted results and are already per-DLC.
- Error detail lines are kept per-attempt by design (see decision in task issue); only the numeric summary changes.