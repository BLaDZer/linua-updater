# Task 33 — Fix `QThread: Destroyed while thread '' is still running` after cancelling a torrent download and starting a new one

## Context

Reproduction: start a torrent (magnet) download, press **Cancel**, wait for the "Installation Cancelled" message, then try to download DLC again. Qt prints:

```
QThread: Destroyed while thread '' is still running
```

The message means an install `QThread` was destroyed (garbage collected) while its underlying thread was still executing `InstallWorker.run()`. Two defects combine:

1. **`TorrentDownloader` silently loses a cancel that arrives before `download()` starts.** `download()` (`torrent_downloader.py:121`) unconditionally resets `self._cancelled = False` at entry. `InstallWorker.cancel()` runs on the UI/main thread and calls `cancel()` on every downloader in `_active_downloaders`, while `_install_single` creates the `TorrentDownloader` and runs `download()` inside a `ThreadPoolExecutor` thread. If the cancel lands between object creation and the reset (a real window right when the torrent starts), the reset wipes it: the flag is cleared, `aria2c` launches, and the whole torrent keeps downloading despite the cancel. `SmartDownloader` has no such reset (`downloader.py` only ever sets `_cancelled = True`), which is why this only manifests on torrents.

2. **The UI lets a new install start while the old thread is still running.** `on_cancel()` (`main_window.py:610`) schedules `QTimer.singleShot(1000, show_cancelled_message)`, which unconditionally calls `reset_ui_after_install()` and re-enables the **Install** button ~1 s later — regardless of whether `InstallWorker.run()` has returned. Because the runaway torrent future keeps `run()` blocked in `as_completed()`, `finished` → `on_install_finished` (the only place that `quit()/wait()`s the thread and nulls the references) never runs in time. Clicking **Install** again makes `start_parallel_install()` (`main_window.py:487`) build a fresh `QThread()` and overwrite `self.install_thread`. The old, still-running `QThread` loses its Python reference and is GC-destroyed → the error. There is no guard against a concurrent install, and a late `on_install_finished` would even `quit()/wait()` the *new* thread.

## How it works now

- `linua_updater/core/torrent_downloader.py:121` — `download()` resets `self._cancelled = False` and never re-checks it before `Popen`; a pre-start cancel is lost.
- `linua_updater/workers/install_worker.py:96-154` — `_install_single` starts new `SmartDownloader`/`TorrentDownloader` objects and runs the installer even if the worker was already cancelled.
- `linua_updater/ui/main_window.py:610-622` — `on_cancel()` is fire-and-forget: `QTimer.singleShot(1000, show_cancelled_message)` → `reset_ui_after_install()` re-enables Install while the thread is still alive.
- `linua_updater/ui/main_window.py:487-516` — `start_parallel_install()` unconditionally creates a new `install_thread`, overwriting any still-running one.
- `linua_updater/ui/main_window.py:567-586` — `on_install_finished()` is the only thread teardown point and only runs after `run()` truly returns.

## How it should work

- A cancel must be sticky for torrent downloads: once `_cancelled` is set, `download()` must return `(False, "Cancelled")` even if the cancel arrived before the download started, and must never re-launch `aria2c`.
- `_install_single` must not kick off fresh downloads for a DLC once the worker is cancelled.
- The **Install** button must only be re-enabled / a new install only startable after the previous install `QThread` has actually finished and been torn down.
- No duplicate or premature dialogs on cancel; a successful install keeps its current UX.

## What needs fixing

### 1. `TorrentDownloader` — honor a pre-start cancel

`linua_updater/core/torrent_downloader.py:~117-128`:

```python
self._cancelled = False
self._out_dir = out_dir
os.makedirs(out_dir, exist_ok=True)
cmd = self._build_command(magnet, out_dir)
...
while True:  # outer restart loop — pause terminates, resume restarts
    try:
        self._process = subprocess.Popen(...)
```

Add an immediate check after the flag reset and a second check at the top of the outer restart loop (before `Popen`):

```python
self._cancelled = False
if self._cancelled:            # cancel() beat download() to the start → no download
    return False, "Cancelled"
self._out_dir = out_dir
os.makedirs(out_dir, exist_ok=True)
cmd = self._build_command(magnet, out_dir)
...
while True:  # outer restart loop — pause terminates, resume restarts
    if self._cancelled:        # never re-launch aria2c after a cancel (also after resume/pause)
        return False, "Cancelled"
    try:
        self._process = subprocess.Popen(...)
```

The two checks close the whole race window (cancel before reset, cancel between reset and `Popen`, cancel during a pause/restart) while preserving existing pause/resume/cancel behavior.

### 2. `InstallWorker._install_single` — stop starting work after a cancel

`linua_updater/workers/install_worker.py:96-99`:

```python
def _install_single(self, dlc_id):
    info = self.db.all().get(dlc_id)
    if not info:
        return dlc_id, False, "DLC not found in database"
```

Add after the `info` retrieval:

```python
if self._cancelled:
    return dlc_id, False, "Cancelled"
```

This makes queued/just-starting futures unwind immediately instead of creating downloaders and downloading after the user cancelled.

### 3. `MainWindow` — deterministic cancel lifecycle

`linua_updater/ui/main_window.py`:

1. In `__init__` add `self._cancel_requested = False` next to `self.install_thread = None` / `self.install_worker = None` (near line 128-129).
2. Guard `start_parallel_install` (line 487): right after the `logger.log` line, add `if self.install_worker is not None or self.install_thread is not None:` → log `"Install already in progress"` (WARNING) and return. Prevent the thread-overwrite/GC race outright.
3. Rework `on_cancel` (line 610) to be event-driven — remove the `QTimer.singleShot(1000, self.show_cancelled_message)` and delete `show_cancelled_message` (line 618):

```python
def on_cancel(self):
    if self.install_worker:
        self.logger.log("Cancelling installation...", "WARNING")
        self.install_worker.cancel()
        self._cancel_requested = True
        self.cancel_btn.setText("Cancelling...")
        self.cancel_btn.setEnabled(False)
```

4. Rework `on_install_finished` (line 567) so the thread is torn down first, then the cancel/success message is resolved, then the UI is reset — the Install button is re-enabled only after the thread is verified dead:

```python
@pyqtSlot()
def on_install_finished(self):
    if self.install_thread:
        self.install_thread.quit()
        self.install_thread.wait()
        self.install_thread = None
        self.install_worker = None
    try:
        self.update_dlc_status()
        if self._cancel_requested:
            self._cancel_requested = False
            self.logger.log("Installation cancelled", "WARNING")
            if not self.is_closing:
                QMessageBox.information(self, "Installation Cancelled", "Installation has been cancelled.")
            self.reset_ui_after_install()
        else:
            self.logger.log("Installation complete!")
            self.download_progress.setValue(100)
            self.download_detail.setText("Installation complete!")
            if self.is_closing:
                return
            if self.failed_count == 0:
                completion_dlg = CompletionDialog(self)
                completion_dlg.exec()
            else:
                msg = f"Installation finished:\n\nSuccessful: {self.successful_count}\nFailed: {self.failed_count}\n\nCheck log for details."
                QMessageBox.warning(self, "Installation Complete", msg)
            QTimer.singleShot(1000, self.reset_ui_after_install)
    except Exception as e:
        self.logger.log(f"Error finishing install: {e!s}", "ERROR")
```

5. In `reset_ui_after_install` (line 588), reset the cancel button label back to `"Cancel"` (and re-disable it as it already does at line 605-606).

## Not in scope

- Changing `SmartDownloader` download/retry/pause logic (it has no cancel-loss bug).
- Changing the `TorrentDownloader` pause/resume restart mechanics (only the pre-start cancel checks are added).
- Altering the parallel manager or `closeEvent` except where already safe once the guard in step 3.2 is in place.

## Tests

### `tests/test_torrent_downloader.py`

1. Add `test_download_cancelled_before_start_returns_cancelled` — create a `TorrentDownloader`, call `dl.cancel()` **before** `dl.download(...)`, monkeypatch `subprocess.Popen` to record/raise if called, assert `ok is False` and `result == "Cancelled"` and `Popen` was never invoked.

### `tests/test_install_worker.py`

2. Add `test_install_single_cancelled_returns_cancelled` — `worker._cancelled = True`, `db` with a magnet DLC, assert `_install_single(dlc_id)` returns `(dlc_id, False, "Cancelled")` and no downloader is created (`_active_downloaders` stays empty).

### `tests/test_ui_defaults.py`

3. Headless tests for the new lifecycle logic, following that file's pure-helper style:
   - Extract the install-in-progress guard into a tiny module-level helper (e.g. `_install_in_progress(install_worker, install_thread)`) and add a test that it returns `True` when either reference is set and `False` when both are `None`.
   - Capture the cancel-request state by asserting the reworked `on_cancel`/`on_install_finished` flow sets/clears `_cancel_requested` (via a lightweight object, not a live widget tree).

## Docs

No `docs/architecture.md` change needed — the fix preserves existing behavior. Optionally note in the cancel/threading section that a new install cannot start while one is in progress.

## Verification

```bash
python -m pytest tests/test_torrent_downloader.py tests/test_install_worker.py tests/test_ui_defaults.py tests/test_parallel.py -v
./scripts/check.sh   # pytest + ruff
```

Manual smoke:

1. Start a torrent (magnet) download.
2. Press **Cancel** immediately (before/around the time the download begins).
3. Confirm the accurate cancellation message appears once and `aria2c` is not left downloading.
4. Click **Install** again — no `QThread: Destroyed while thread is still running` warning, download proceeds normally.