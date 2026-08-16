# Task 36 — Cancellation must be terminal for torrent installs (no fallback to direct download)

## Context

When a torrent (magnet) download is cancelled mid-install, `InstallWorker._install_single`
treats the `"Cancelled"` result like any ordinary torrent failure and starts the
direct-download fallback. The log shows:

```
[20:43:47] Cancelling installation...
[20:43:47] Torrent download cancelled: EP01 - Get to Work
[20:43:48] EP01: Torrent download failed (Cancelled), falling back to direct download
[20:43:48] EP01: Starting download...
```

On a cancel the fallback must not run at all: only the "Cancelled" message and the
statistics should follow, and no further network attempts may be made.

## How it works now

- `linua_updater/workers/install_worker.py:117-132` — after the torrent installer
  returns a non-success, the `if not success:` block unconditionally logs
  `"{dlc_id}: Torrent download failed ({message}), falling back to direct download"`
  and starts a `SingleDLCInstaller`/`MultiPartInstaller`, even when the failure is a
  user cancellation (`message == "Cancelled"` or `self._cancelled` is set).
- `linua_updater/core/downloader.py:66-106` — `SmartDownloader.download()` has no
  `_cancelled` guard at entry or between the primary/proxy/mirror attempt stages, so a
  cancelled downloader keeps opening new connections ("trying other download options").
- `linua_updater/core/downloader.py:108-124` — `_try_download_with_retry` runs all
  `max_retries` even when cancelled and masks the real reason with
  `"Max retries exceeded"`.

## How it should work

- After a cancel, the torrent branch of `_install_single` returns
  `(dlc_id, False, "Cancelled")` immediately — no fallback log, no direct download.
- A `SmartDownloader` whose `_cancelled` is set returns `(False, "Cancelled")`
  without performing further HTTP requests (primary, proxy, or mirror).

## What needs fixing

### 1. `InstallWorker._install_single` — no fallback after a cancel

`linua_updater/workers/install_worker.py:118-132`. Before the fallback, bail out:

```python
success, message = installer.run()
if not success:
    if self._cancelled or message == "Cancelled":
        return dlc_id, False, "Cancelled"
    self.logger.log(f"{dlc_id}: Torrent download failed ({message}), falling back to direct download", "WARNING")
    ...
```

Checking both `self._cancelled` (worker-wide flag) and `message == "Cancelled"`
(single-installer cancel) makes the cancel terminal regardless of which one fired.

### 2. `SmartDownloader.download` — abort when already cancelled

`linua_updater/core/downloader.py:66-106`. Add guards so a cancelled downloader never
starts a new attempt:

```python
def download(self, url, out_path, dlc_name=None, resume=False, expected_size=None):
    self._active = True
    ...
    if self._cancelled:
        self._active = False
        return False, "Cancelled"
```

and between each stage (after primary `_try_download_with_retry`, before and inside the
proxy loop, and before the mirror loop) return `False, "Cancelled"` when `_cancelled`.

### 3. `_try_download_with_retry` — don't retry after a cancel

`linua_updater/core/downloader.py:108`. Add at the top of the attempt loop:

```python
if self._cancelled:
    return False, "Cancelled"
```

so "Cancelled" is surfaced instead of "Max retries exceeded" for every retry.

## Not in scope

- `TorrentDownloader` changes (already fixed in Task 33 / commit `b12f456`).
- Pause/resume mechanics, parallel manager, or UI thread lifecycle.
- Whether a cancelled DLC is counted as a failed installation in statistics.

## Tests

### `tests/test_install_worker.py`

Add `test_install_single_torrent_cancelled_no_fallback`:
- Build a `worker` via `__new__` (as the existing fixture), set `db` with a magnet DLC,
  `settings`, `mirrors`, `logger`.
- Monkeypatch `linua_updater.workers.install_worker.TorrentDownloader` with a stub whose
  `download()` returns `(False, "Cancelled")`.
- Monkeypatch the `SmartDownloader` (created inside `_install_single`) with a stub that
  records `download` calls.
- Assert the direct downloader's `download` is never called and the result message is
  `"Cancelled"`.

### `tests/test_downloader.py`

Add `test_download_returns_cancelled_when_already_cancelled`:
- Create a `SmartDownloader`, call `dl.cancel()` first.
- Monkeypatch `requests.Session.get` to raise if called.
- Call `dl.download(url, path)`; assert `(False, "Cancelled")` and that `Session.get`
  was never invoked.

## Docs

No `docs/architecture.md` change needed — cancellation semantics are preserved.

## Verification

```bash
python -m pytest tests/test_install_worker.py tests/test_downloader.py -v
./scripts/check.sh   # pytest + ruff
```

Manual smoke: start a torrent download, press **Cancel**, confirm the log shows only
"Cancelling installation...", "Torrent download cancelled: <name>", and the statistics —
no "falling back to direct download" and no "Starting download...".