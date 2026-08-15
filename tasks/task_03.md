# Task 03 — Implement Pause / Resume

## How it works now

- A `Pause` button exists (`:1990`) and is shown/enabled during install (`:2243`), but it is a **no-op**:
  - `LinuaUI.on_pause` (`:2440`) checks `hasattr(self.install_worker, 'pause')`; `InstallWorker` defines no `pause` method, so the branch never runs and the button does nothing visibly.
  - `on_resume` (`:2449`) similarly guards on a nonexistent `resume`.
- `DownloadQueue` (`:373`) and `DownloadState` (`:421`) are fully implemented persistence classes but **never instantiated** anywhere — dead code.
- `MetadataCache` (`:343`) is likewise never used.
- `DownloadState`/`DownloadQueue` JSON files are documented in `docs/architecture.md` §7 but never written.
- Resume at the byte level already exists inside `SmartDownloader.download(..., resume=True)` via `Range` header + `.part` temp files (`:660`, `:709`), and is hardcoded on (`:925`, `:1002`) regardless of the `resume_downloads` setting.

## How it should work

- **Pause**: user clicks Pause → in-flight downloads stop cleanly; per-DLC `.part` files remain on disk; `DownloadQueue`/`DownloadState` records which DLC are complete / failed / remaining; the button label switches to "Resume". Pausing must work across concurrent downloads in-task (see task_01) and must not leave the session in a broken state.
- **Resume**: user clicks Resume → remaining DLC continue; incomplete downloads resume from their `.part` byte offset via the existing `Range` logic; queue is updated; button label switches back to "Pause".
- The `resume_downloads` settings toggle (task_04) controls whether resume is attempted at all.
- Pause/Resume is also interruptible by `Cancel` at any point.
- The pause state machine must be thread-safe when (task_01) parallel installs are active.

## What needs fixing

1. Add a thread-safe pause flag to `SmartDownloader` (`_paused`), checked in the `iter_content` loop alongside `_cancelled` (`:729`); keep the connection open or close cleanly — decide: simplest correct approach is to abort the current stream like cancel but keep `.part` and queue state so resume reconnects via `Range`.
2. Add `pause()` / `resume()` methods to `InstallWorker` that set the flag and emit/update UI state through signals.
3. Wire `DownloadQueue` (track per-DLC progress) and `DownloadState` (24h-TTL snapshot of completed/failed/remaining) into `InstallWorker.run()` — persist on pause, load on resume/startup.
4. Replace the `hasattr`-guarded `on_pause`/`on_resume` with real calls when the worker is active (store bool `self.installing` to gate the button).
5. Ensure Pause/Resume labels + button enable/disable states are reset in `reset_ui_after_install` (`:2345`).
6. Handle the edge case: user closes the app while paused — state must still be recoverable via `DownloadState` (24h TTL) and `.part` files.
7. Update `docs/architecture.md` §10 Known Issues — remove the "partial" pause/resume note; document the implemented flow.