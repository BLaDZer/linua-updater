# Task 09 — Housekeeping & dead-code cleanup

## How it works now

- `build.spec` sets `console=True` (`:32`) for a GUI application — the shipped binary spawns a console window.
- The built binary `LinuaUpdater_v4.3.0.exe` is committed to the repo root (git tracks it).
- Disk-space warnings are duplicated: `on_update` hardcodes a "15 GB" check (`:2200`) in addition to `DiskSpaceChecker.check_space` (`:1319`) run right after DLC selection — two overlapping, inconsistent thresholds (15 GB blanket vs per-selection estimate).
- Dead signal/slot pair: `status_updated` (`:1046`) and `download_detail` (`:1047`) are emitted (`:1125`) and connected (`:2254`–`:2255`) to empty `pass` slots `on_status_updated`/`on_download_detail` (`:2276`–`:2282`). Meanwhile the detail widget is updated directly in `on_progress_updated` (`:2270`) — so the signal path is pure dead weight.
- Misleading/inert infrastructure: `MetadataCache` (`:343`), `DownloadQueue` (`:373`), `DownloadState` (`:421`) — see task_03 (DownloadQueue/DownloadState get wired there) and task_07. If unused after task_03, they must be removed.
- Stale comments/markers: `# Modified InstallWorker to support pause/resume` (`:461`) sits above unrelated classes; `# FIXED:` comments reference removed EP03/EP06 exclusions (`:1670`, `:1711`, `:2051`).

## How it should work

- GUI build uses `console=False`.
- No binaries in the repo; add `*.exe`/`dist/`/`build/` to `.gitignore`, remove the tracked `.exe` (git rm).
- Exactly one space-check path: `DiskSpaceChecker` after selection; the pre-install "needs ~15 GB" heuristic removed or replaced by `DiskSpaceChecker` guidance.
- `status_updated`/`download_detail` signals either get real slots or are deleted; the detail widget is updated through exactly one path.
- Persistence classes are either used (task_03/07) or removed; no `pass`-body slots remain for used signals.
- File is free of stale placeholder comments.

## What needs fixing

1. `build.spec` — `console=False`.
2. Repo hygiene — `.gitignore` for `*.exe`, `dist/`, `build/`, `*.spec` artifacts as appropriate; `git rm LinuaUpdater_v4.3.0.exe`.
3. `on_update` (`:2200`) — remove the hardcoded 15 GB warning and rely on `DiskSpaceChecker` (or fold the threshold into it).
4. Dead signals — either implement `on_status_updated`/`on_download_detail` meaningfully (e.g. per-DLC status log) or remove the signals + slots + `_handle_progress` detail emission (`:1125`); keep a single detail-widget update path in `on_progress_updated`.
5. Assign follow-up ownership in task_03/07 for `DownloadQueue`/`DownloadState`/`MetadataCache`; any class left unused at the end of those tasks gets deleted.
6. Remove stale comments (`:461`, `# FIXED:` block comments) and normalize formatting (the interleaved blank lines at `:1210`, `:1714`).
7. Update `docs/architecture.md` §8 (build: console now windowed) and §3/§10 (dead signals, if removed).