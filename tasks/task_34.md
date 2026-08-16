# Task 34 — Show download lifecycle and source in the app log (single file, parts, torrent)

## Context

After clicking **Install**, the app-log widget (`QTextEdit` in the main window) shows almost nothing
while downloads run: only `Installation started` appears up front, then per-DLC
`EP01: Installation successful` lines once each DLC finishes. Nothing tells the user *what* is being
downloaded, where it comes from, or where the download stands in its lifecycle.

Two root causes combine:

1. **Worker logs never reach the UI.** `InstallWorker` (`linua_updater/workers/install_worker.py`)
   constructs its own `self.logger = ImprovedLogger()` **without a widget**. Every `logger.log(...)`
   call from the downloaders/installers therefore goes only to `logs/updater.log` — never to the
   app-log widget. The widget only receives messages the main window logs itself via Qt signals.
2. **The downloaders never log the lifecycle.** `SmartDownloader` (`linua_updater/core/downloader.py`)
   only logs `Resuming download: ...` and the slow-speed abort — never *that a download started, was
   paused/resumed, or finished*. `TorrentDownloader` (`linua_updater/core/torrent_downloader.py`) has
   **no `self.logger.log(...)` calls at all** — even "aria2c not found" fails silently. And no
   component records *which source* a DLC is downloaded from (`url`, `magnet`, or the list of parts).

## How it works now

- `linua_updater/core/downloader.py` — `SmartDownloader.download()` computes `display = dlc_name or url`
  but only logs when resuming; `_try_download()` logs nothing except the slow-speed abort.
- `linua_updater/core/installers.py` — `MultiPartInstaller.run()` logs `Downloading part {i+1}/{total_parts}...`
  per part but nothing about the source or per-part completion; no pause/resume/finished traces.
- `linua_updater/core/torrent_downloader.py` — `TorrentDownloader.download()` never calls
  `self.logger.log(...)`; aria2-not-found returns silently, progress is only pushed to `_progress_callback`.
- `linua_updater/workers/install_worker.py` — `self.logger = ImprovedLogger()` with no widget; all
  worker-thread download logs are file-only.
- `linua_updater/ui/main_window.py` — the UI logger (with widget) is connected only to worker signals,
  not to the worker's own logger.

## How it should work

- The app log shows the full download lifecycle for every DLC — **start, pause, resume, finished** —
  and each line identifies the DLC plus its **source**: a single-file **url**, the full **magnet link**,
  or the **links of the parts**.
- **No periodic progress lines.** No per-download byte/percentage milestones (10%, 20%, ...) ever appear
  in the app log; the existing `progress_updated` / `overall_progress_updated` signals keep driving the
  progress widget exactly as today.
- Worker-thread log calls are forwarded to the app-log widget **safely** — via a queued Qt signal
  emitted from the worker thread and consumed on the main thread (never calling `widget.append()`
  from a worker thread).
- Existing behavior is preserved: file logging, retry/mirror/proxy logic, pause/resume/cancel, and all
  current tests.

## What needs fixing

### 1. `SmartDownloader` (single file) — `linua_updater/core/downloader.py`

- In `__init__`, add `self._display = None`, `self._source = None`, `self._active = False`.
- At the top of `download()` set `self._active = True`, `self._display = dlc_name or url`,
  `self._source = url`, and log the **start** line: `Downloading {display} from {source}` (INFO).
- On success (after the final `out_path` exists), log the **finished** line:
  `Downloaded {display} ({size:.1f} MB)` (size from `os.path.getsize(out_path)`).
- When every attempt/proxy/mirror fails, log `All download attempts failed: {display} from {source}`
  (WARNING) before returning `False`.
- `pause()`: when `self._active`, log `Paused {display} from {source}` (WARNING).
- `resume()`: when `self._active`, log `Resumed {display} from {source}` (INFO).
- Reset `self._active = False` (and keep `_display`/`_source` for the finished line) at the end of
  `download()`, so pause/resume only log while a download is genuinely in flight.
- Do **not** add any milestone/percentage logging in the chunk loop.
- Keep the existing `Resuming download: ...` line and slow-speed abort as-is.

### 2. `MultiPartInstaller` (parts) — `linua_updater/core/installers.py`

- At the start of `run()`, log the source list once:
  `Downloading {dlc}: {total_parts} parts from: {url1}, {url2}, ...` joining `info["parts"]`.
- Per part, keep using the downloader for the actual bytes: pass `dlc_name = f"{self.dlc} Part {i+1}"`
  so `SmartDownloader` logs per-part **start** (`Downloading {dlc} Part {i+1} from {part_url}`) and the
  per-part **finished** (`Downloaded {dlc} Part {i+1} ({size:.1f} MB)`) lines. You may drop the existing
  `Downloading part {i+1}/{total_parts}...` installer-level start line to avoid a duplicate start.
- After each part downloads successfully, log `Part {i+1}/{total_parts} downloaded ({part_size/(1024*1024):.1f} MB)`.
- When a part fails, log `Part {i+1}/{total_parts} failed: {reason}` at WARNING before returning.
- Keep the existing overall `Extracting multipart archive...` / `Complete` end lines.

### 3. `TorrentDownloader` — `linua_updater/core/torrent_downloader.py`

- In `__init__`, add `self._display = None`, `self._source = None`, `self._active = False`.
- aria2 not found: log `Torrent download: aria2c not found` at WARNING instead of returning silently.
- At the top of `download()`, set `self._active = True`, `self._display = dlc_name or magnet`,
  `self._source = magnet`, and log `Starting torrent download: {display} ({source})` (full magnet link).
- `pause()`: when `self._active`, log `Paused torrent download: {display}` (WARNING).
- `resume()`: when `self._active`, log `Resumed torrent download: {display}` (INFO).
- Nonzero aria2 exit: log `aria2c exit code {exit_code}` at ERROR.
- Cancel: log `Torrent download cancelled: {display}` at WARNING at each `return False, "Cancelled"` site.
- Completion: log `Torrent download complete: {display}` when returning the file list.
- Reset `self._active = False` at the end of `download()`.
- `TorrentInstaller` may drop its own `Starting torrent download...` line to avoid two start lines.

### 4. Forward worker-thread logs to the app log

- `linua_updater/logging_util.py`: add a thin subclass `class SignalLogger(ImprovedLogger)` taking a
  callable `emitter`; `log(text, level="INFO")` calls `super().log(text, level)` (file as today) then
  `self._emitter(text, level)`. Do not change `ImprovedLogger` behavior.
- `linua_updater/workers/install_worker.py`: add `log_updated = pyqtSignal(str, str)`; replace
  `self.logger = ImprovedLogger()` with `self.logger = SignalLogger(self.log_updated.emit)`. Emitting a
  signal from the worker thread is safe — Qt queues the delivery.
- `linua_updater/ui/main_window.py` in `start_parallel_install`: connect
  `self.install_worker.log_updated.connect(self._on_worker_log)` and add a slot
  `def _on_worker_log(self, text, level="INFO"): self.logger.log(text, level)`. The queued
  cross-thread connection runs the slot on the main thread, so appending to the widget is safe.

## Not in scope

- **No periodic progress logging** — no download percentage/byte milestones are added anywhere, for
  single-file, multipart, or torrent downloads. (The progress *widget* keeps updating via the existing
  `progress_updated`/`overall_progress_updated` signals.)
- Changing download/retry/pause/resume/cancel/mirror/proxy logic.
- Changing the existing progress-signal plumbing.
- Changing aria2 summary parsing or the `--summary-interval`/pause-restart mechanics.
- New UI components; the `QTextEdit` app log stays as-is.

## Tests

Use a `RecordingLogger` (collects `(text, level)` tuples) in the new assertions:

- `tests/test_downloader.py` — assert `download()` logs a start line containing the display name and
  the url; on success a finished line containing the display and "MB"; on total failure a WARNING
  containing `All download attempts failed` and the display. Assert `pause()` logs
  `Paused {display}` and `resume()` logs `Resumed {display}` while a download is active.
  (The old milestone assertions are removed.)
- `tests/test_torrent_downloader.py` — assert the start line contains the display and the full magnet;
  the complete line is emitted on success; a missing-aria2 path logs a WARNING containing
  `aria2c not found`; nonzero exit logs an ERROR containing `aria2c exit code`; cancel logs a WARNING
  containing `Torrent download cancelled`.
- `tests/test_installers.py` — assert `MultiPartInstaller` logs a parts-source line containing every
  part url, per-part finished lines (`Part {i+1}/{N} downloaded`), and the failure reason for a failing
  part (`Part {N}/{N} failed`).
- `tests/test_logging_util.py` — assert `SignalLogger.log(...)` both writes to the file logger and
  invokes the emitter with `(text, level)`.
- `tests/test_install_worker.py` — headless (PyQt6 available): assert the worker's logger is a
  `SignalLogger` (or that it forwards to `log_updated`), following the file's existing
  `InstallWorker.__new__` fixture style.

## Docs

- `docs/architecture.md` — in §4 (download engine) and §7 (worker threads / `ImprovedLogger` row):
  note that worker-thread download logs now reach the app log via `SignalLogger` →
  `InstallWorker.log_updated` → main-window slot, and that `SmartDownloader`/`TorrentDownloader`/
  `MultiPartInstaller` log the lifecycle (start, pause, resume, finished) together with the DLC's
  source (url / magnet link / parts links), with **no** periodic progress lines.

## Verification

```bash
python -m pytest tests/ -v
./scripts/check.sh   # pytest + ruff
```

Manual smoke:

1. Install a single-file DLC (e.g. `EP01`) — app log shows `Downloading EP01 from <url>`,
   `Paused EP01 from <url>` / `Resumed EP01 from <url>` if paused, and `Downloaded EP01 (N MB)`.
2. Install a multipart DLC (`EP06`) — log shows `Downloading EP06: 7 parts from: <all part urls>`,
   `Downloading EP06 Part 1 from <url>`, `Downloaded EP06 Part 1 (N MB)`, `Part 1/7 downloaded (N MB)`,
   ..., and the final `Complete`.
3. Install a magnet DLC — log shows the full magnet link with `Starting torrent download: ...`,
   and `Torrent download complete: ...`; cancel mid-download logs `Torrent download cancelled: ...`.
4. Place a `Pause`/`Resume` mid-download for a single + multipart DLC — every active download logs its
   own per-DLC `Paused ... from <source>` / `Resumed ...` line.
5. Start an install with no `aria2c` present — log shows the `aria2c not found` WARNING.