# Task 31 — Hide aria2c/7z console windows on Windows and terminate subprocess on window close

## Context

Users running the windowed GUI build (PyInstaller `console=False`, `build.spec:49`) on **Windows** see a **separate console window flash/open** whenever `aria2c.exe` or `7z.exe` is spawned, and the subprocess is not reliably cleaned up when the main window closes.

The root cause was diagnosed in `tasks/chatgpt_conversation_02.md`:

- `subprocess.Popen(cmd, stdout=…, stderr=…)` starts a console-subsystem binary (`aria2c.exe` / `7z.exe`) without `CREATE_NO_WINDOW`, so Windows opens a new console window for it (conversation lines 13-32).
- The recommended fix is `creationflags=subprocess.CREATE_NO_WINDOW`, which still allows capturing `stdout`/`stderr` via pipes (lines 17-49).
- The conversation also recommends a robust shutdown pattern on window close: `terminate()` → `wait(timeout)` → `kill()` → `wait()` (lines 55-145).

## How it works now

- `linua_updater/core/torrent_downloader.py:110-116` — `subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)` with **no** `creationflags`. A running torrent install on Windows pops a console window.
- `linua_updater/core/extractor.py:55` — `subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)` for the 7-Zip binary, **no** `creationflags`. Multipart installs (`MultiPartInstaller`) also spawn the 7z console window.
- `linua_updater/ui/main_window.py:741-756` — `closeEvent` calls `install_worker.cancel()`, which iterates `_active_downloaders` and calls `TorrentDownloader.cancel()`. That `cancel()` (`torrent_downloader.py:26-33`) only calls `terminate()` and never waits for (or force-kills) the child. If `aria2c` ignores SIGTERM, the process is not reaped and may keep running.

## How it should work

- Spawning `aria2c` (torrent path) and the 7-Zip binary (`extract_7z`) must not open a console window on Windows; behavior on Linux/macOS is unchanged.
- Closing the main window must terminate the `aria2c` child gracefully: `terminate()` → wait up to 2s → `kill()` → wait, mirroring the pattern in the conversation.

## What needs fixing

### 1. `TorrentDownloader` — pass `CREATE_NO_WINDOW` to `Popen`

In `linua_updater/core/torrent_downloader.py` add a module-private helper and use it in `download()`:

```python
def _popen_kwargs():
    """Popen kwargs hiding the console window on Windows. No-op elsewhere."""
    kwargs = {}
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if flag:
        kwargs["creationflags"] = flag
    return kwargs
```

Use it at line 110:

```python
self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, **_popen_kwargs())
```

`subprocess.CREATE_NO_WINDOW` only exists on Windows; `getattr(..., 0)` keeps cross-platform import safety. `creationflags` is a documented parameter on all platforms, so passing it is safe everywhere.

### 2. `Extractor.extract_7z` — pass `CREATE_NO_WINDOW` to `subprocess.run`

In `linua_updater/core/extractor.py:55`:

```python
result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
```

Note: passing `creationflags=0` explicitly is valid on every platform — Python accepts `creationflags` and ignores it when the platform has no such flag.

### 3. `TorrentDownloader.cancel()` — terminate, then wait/kill

Currently `cancel()` (torrent_downloader.py:26-33) only `terminate()`s. Extend it so the child is actually reaped:

```python
def cancel(self):
    self._cancelled = True
    with self._lock:
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                    try:
                        self._process.wait()
                    except Exception:
                        pass
            except Exception:
                pass
```

Constraints:
- Keep all access inside `self._lock` (already the pattern in `pause()`/`cancel()`).
- Do **not** change `pause()` — pause must terminate and let the restart loop pick back up quickly; `resume()` must not be blocked by a wait/kill sequence.
- `cancel()` is called from the installer thread's restart/cancel paths and from `InstallWorker.cancel()`; a 2s wait is acceptable there.
- `.wait(timeout=)`/`.kill()` are racy by nature; wrap defensively in the same try/except style already used for `terminate()`.

### 4. Main window `closeEvent`

`linua_updater/ui/main_window.py:741-756` already cancels the install worker, which routes to `TorrentDownloader.cancel()`. The terminate→wait→kill fix in item 3 makes the existing `closeEvent` sufficient — **no UI change required**. Verify during review that `install_thread.wait()` (line 749) returns promptly after cancel because the child is now force-reaped.

## Not in scope

- Migrating from `subprocess.Popen` to `QProcess` (conversation lines 185-186). `CREATE_NO_WINDOW` resolves the reported console-window problem with a far smaller change, and stdout is already read on worker threads, not the GUI thread.
- Linux/macOS builds do not need any flag; the `getattr` default ensures full cross-platform support.

## Tests

### `tests/test_torrent_downloader.py`

1. `test_popen_kwargs_linux_no_creationflags` — patch `torrent_downloader.subprocess` so `CREATE_NO_WINDOW` is absent (`delattr`/fake module), assert `_popen_kwargs()` returns `{}`.
2. `test_popen_kwargs_windows_sets_creationflags` — patch a fake `subprocess` module exposing `CREATE_NO_WINDOW = 0x08000000` (e.g. `types.SimpleNamespace`), assert `_popen_kwargs() == {"creationflags": 0x08000000}`.
3. `test_download_passes_no_window_flag` — monkeypatch `subprocess.Popen` with a capture-stub recording `**kwargs` (existing style, `tests/test_torrent_downloader.py:98-109`), assert the recorded kwargs contain `creationflags` equal to `getattr(subprocess, "CREATE_NO_WINDOW", 0)`.
4. `test_cancel_kills_when_terminate_ignored` — FakeProcess that never exits after `terminate()`; monkeypatch its `wait` to raise `TimeoutExpired` first, then succeed; assert `cancel()` returns and `kill()` was called. Extend the existing `FakeProcess` fixture (lines 11-46) with `kill()` if needed.
5. Existing cancel/pause/resume tests (`test_download_cancel_returns_cancelled`, `test_download_pause_resume_restarts`) must still pass unchanged — the 2s wait in `cancel()` must not break the threaded test timing.

### `tests/test_extractor.py`

6. `test_extract_7z_passes_no_window_flag` — capture the `creationflags` kwarg in `fake_run` (existing pattern at `tests/test_extractor.py:102-111`), assert it equals `getattr(subprocess, "CREATE_NO_WINDOW", 0)`.

## Docs

Update `docs/architecture.md`:
- `TorrentDownloader` row (`docs/architecture.md:109`): add "spawns `aria2c` with `CREATE_NO_WINDOW` on Windows and reaps the child on cancel/close".
- `Extractor` row if it lists `extract_7z`: note the same hidden-console behavior.

## Verification

```bash
./scripts/setup.sh   # if needed
./scripts/check.sh   # pytest + ruff
```

All existing tests must pass alongside the new ones.