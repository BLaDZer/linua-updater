# Task 02 — Overall progress bar reflects real overall progress

## How it works now

- `InstallWorker.overall_progress_updated` is emitted from `ParallelInstallManager._calculate_overall_progress` (`:880`), which averages per-DLC progress.
- However the UI slot that receives it, `LinuaUI.on_overall_progress_updated` (`:2272`), is an empty `pass`.
- `on_progress_updated` (`:2264`) sets `self.download_progress.setValue(int(progress))` directly from the **current single DLC's** progress signal.
- Net effect: the main progress bar shows whatever DLC is downloading right now. With multiple selected DLC it jumps to 0% when each DLC starts, never showing cumulative completion. `on_install_finished` forces 100% only at the very end.

## How it should work

- The main progress bar should represent the **overall** install progress across all selected DLC: e.g. weighted average of per-DLC progress (sum of per-DLC progress ÷ number of selected DLC).
- `on_overall_progress_updated(progress)` should drive `download_progress.setValue(...)`.
- Per-DLC detail (`Downloading EP04: 45% …`) continues to be shown in the detail widget (`SimpleDetailWidget.update_progress`).
- When all DLC complete, bar reaches 100% naturally (already handled by `finished` → `on_install_finished`).

## What needs fixing

1. Implement `LinuaUI.on_overall_progress_updated` to set the main progress bar value.
2. Decouple the main bar from per-DLC progress in `on_progress_updated` — it should only feed the detail widget (the `download_detail` signal/slot is the redundant path; task_09 covers cleanup, but the per-DLC bar update must be removed here).
3. Verify `ParallelInstallManager.update_download_progress` → `_calculate_overall_progress` fires often enough (every download chunk) to look smooth — currently it is called per progress callback, which is fine once wired.
4. Fix `_calculate_overall_progress` for the count being 0 / partial sets (guard already exists, confirm when only one of several DLC has reported).
5. Update `docs/architecture.md` §3 / §4 signal-flow description.