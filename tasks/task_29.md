# Task 29 — Complete Task 27: CI aria2 bundling and fix resume/cancel bugs in TorrentDownloader

## Context

Task 27 implemented torrent/magnet download support with fallback to parts/url. The core implementation is correct, but three issues remain:

1. **CI workflows do not download aria2c** — release binaries will never bundle the binary, so `Aria2Finder` always falls back to direct download in production.
2. **`TorrentDownloader` pause/resume is non-functional** — `pause()` terminates the process, but `resume()` only clears the `_paused` flag; the `download()` loop has already exited on EOF (the process is dead), so nothing ever restarts `aria2c --continue=true` from the `.aria2` control files. Pause/resume for torrents must block in `download()` and restart the process.
3. **Minor bugs** in `cancel()`/`resume()` logic and a busy-wait loop in the download loop.

---

## 1. CI workflows — bundle aria2c in `tools/`

### `linux_build.yml`

Add aria2 installation and `tools/` copy after the "Install system dependencies for PyQt6" step and before "Install dependencies":

```yaml
      - name: Install aria2 for bundling
        run: |
          sudo apt-get install -y aria2
          mkdir -p tools
          cp "$(command -v aria2c)" tools/
```

### `windows_build.yml`

Add a step before "Build EXE" that downloads the official aria2 Windows build and extracts `aria2c.exe` into `tools/`:

```yaml
      - name: Download aria2 for bundling
        run: |
          $aria2Url = "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip"
          $zipPath = "$env:RUNNER_TEMP\aria2.zip"
          Invoke-WebRequest -Uri $aria2Url -OutFile $zipPath -UseBasicParsing
          Expand-Archive -Path $zipPath -DestinationPath "$env:RUNNER_TEMP\aria2" -Force
          New-Item -ItemType Directory -Force -Path tools | Out-Null
          Copy-Item "$env:RUNNER_TEMP\aria2\aria2-1.37.0-win-64bit-build1\aria2c.exe" -Destination "tools\aria2c.exe" -Force
```

Note: in the 1.37.0 Windows zip the `aria2c.exe` sits at the **zip root** (`aria2-1.37.0-win-64bit-build1\aria2c.exe`) — there is no `bin\` subfolder. If you pin a different release, verify its layout before copying.

Use a recent stable aria2 release (1.37.0 or latest). The exact URL can be verified at https://github.com/aria2/aria2/releases.

### Verification

After merging, a CI run should produce a binary that contains `aria2c` in the one-file PyInstaller bundle. `Aria2Finder` will find it via `_MEIPASS` on Linux or exe dir on Windows.

The bundling side is already wired up and needs **no** changes: `build.spec` adds `tools/aria2c` (or `aria2c.exe`) to `a.binaries` when present (`build.spec:20-23`), and `.gitignore` already excludes the `tools/` build artifact. Only the two workflow steps above are new.

---

## 2. Fix `TorrentDownloader` — pause must block and restart internally

### Problem

`pause()` terminates the `aria2c` process. The download loop is blocked in `self._process.stdout.readline()`; termination closes stdout, `readline()` returns `""`, and the loop `break`s at `torrent_downloader.py:117` — **before** the `if self._paused:` check (~line 125) is ever reached. So the pause-detection code that only lives inside the loop never runs, and `resume()` (which just clears `_paused = False`) leaves the transfer dead with no mechanism to restart `aria2c --continue=true` from the `.aria2` control files.

Two facts make any correct fix **blocking, not "return control to the caller"**:
- `pause()` can be observed from either path — the in-loop summary-line path *or* the EOF path — so both must be handled.
- The installer runs `dl.download(...)` synchronously inside `TorrentInstaller.run()`. If `download()` ever returns while the user is pausing, the installer immediately logs "falling back to direct download" and starts direct HTTP; the caller (`InstallWorker.resume()` via the UI thread) then has nothing left to resume. A `resume()` that re-invokes `download()` would run the whole transfer on the UI thread with a discarded result.

### Solution

`download()` must **block while paused** and, when resumed, **restart `aria2c` internally** — the installer thread never leaves the torrent path and nothing runs on the UI thread. `resume()` only clears the flag.

```python
def resume(self):
    with self._lock:
        self._paused = False

def _wait_for_resume(self):
    """Block until resume() or cancel(). Yields the GIL via sleep."""
    while self._paused and not self._cancelled:
        time.sleep(0.1)

def download(self, magnet, out_dir, dlc_name=None, expected_size=None):
    if not self._aria2_path or not os.path.exists(self._aria2_path):
        return False, "aria2c not found"

    self._cancelled = False
    self._out_dir = out_dir
    os.makedirs(out_dir, exist_ok=True)
    cmd = self._build_command(magnet, out_dir)
    total_bytes = 0
    last_progress = 0

    while True:  # outer restart loop — pause terminates, resume restarts
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            return False, str(e)

        restart = False
        try:
            while True:
                line = self._process.stdout.readline()
                if not line:
                    break
                if self._cancelled:
                    return False, "Cancelled"
                if self._paused:
                    restart = True  # halt; restart below once resumed
                    break
                parsed = self._parse_summary(line)
                if parsed and parsed[0] is not None:
                    progress, downloaded, total = parsed
                    if total == 0 and expected_size:
                        total = expected_size
                    total_bytes = max(total_bytes, downloaded)
                    if progress != last_progress and self._progress_callback:
                        self._progress_callback(progress, downloaded, total)
                        last_progress = progress
        except Exception:
            pass

        if restart:
            # loop hit a summary line while paused → wait, then restart
            self._wait_for_resume()
            if self._cancelled:
                return False, "Cancelled"
            self._process.wait()  # reap the terminated child
            self._process = None
            continue  # re-run the command; --continue=true resumes from .aria2

        exit_code = self._process.wait()
        self._process = None
        if self._cancelled:
            return False, "Cancelled"
        if self._paused:
            # readline hit EOF because pause() terminated the process → wait, then restart
            self._wait_for_resume()
            if self._cancelled:
                return False, "Cancelled"
            continue
        if exit_code != 0:
            return False, f"aria2c exit code {exit_code}"
        break  # completed normally

    completed_files = []
    try:
        for f in os.listdir(out_dir):
            if f.endswith((".aria2", ".torrent")):
                try:
                    os.remove(os.path.join(out_dir, f))
                except Exception:
                    pass
            else:
                fp = os.path.join(out_dir, f)
                if os.path.isfile(fp):
                    completed_files.append(fp)
    except Exception:
        pass

    completed_files.sort()
    return True, completed_files
```

The key invariant: whenever `_paused` is observed — in the loop or on EOF — the thread parks itself in `_wait_for_resume()` (sleeping, not spinning) and, once `resume()` clears the flag, re-runs the same command so `--continue=true` picks up from the `.aria2` control files. A `cancel()` arriving during the pause returns `(False, "Cancelled")` immediately. No `_last_magnet`/`_last_out_dir`/`_last_expected_size`/`_paused_was_set` bookkeeping is needed: the original parameters stay in scope for the whole `download()` call.

---

## 3. Fix `InstallWorker.cancel()` — remove `resume()` call

### Problem

`InstallWorker.cancel()` calls `downloader.resume()` after `downloader.cancel()`:

```python
def cancel(self):
    ...
    for downloader in active:
        downloader.cancel()
        downloader.resume()  # ← clears paused state of a cancelled downloader
```

This is a logic error: cancelling a downloader should not also resume it.

### Fix

Remove the `resume()` call from `cancel()`:

```python
def cancel(self):
    self._cancelled = True
    if self.parallel_manager:
        self.parallel_manager.cancel_all()
    if self.downloader:
        self.downloader.cancel()
    with self._active_downloaders_lock:
        active = list(self._active_downloaders)
    for downloader in active:
        downloader.cancel()
```

---

## 4. Fix busy-wait with `_wait_for_resume()`

### Problem

The current pause branch spins the CPU:

```python
if self._paused:
    with self._lock:
        while self._paused and not self._cancelled:
            pass  # ← spins CPU, no sleep, no timeout
```

This busy-waits, consuming 100% CPU while paused. It is also the *only* pause-detection point in the loop, so a pause observed on the EOF path (the common case after `pause()` terminates the process) is never handled.

### Fix

There is no pause branch to bolt on top of the loop anymore — Section 2's `_wait_for_resume()` replaces it. The replacement must be used in **both** places a pause can be observed (in-loop and EOF), not just one:

```python
def _wait_for_resume(self):
    """Block until resume() or cancel(). Yields the GIL via sleep."""
    while self._paused and not self._cancelled:
        time.sleep(0.1)
```

- `time.sleep(0.1)` yields the GIL and the OS scheduler instead of spinning at 100% CPU.
- `self._cancelled` is checked on every iteration **inside** the loop, so a cancellation during a pause is always observed — no separate check outside the lock that could be missed.
- It parks the *download* thread, not the UI thread; `resume()`/`cancel()` come in from the UI/worker threads and only flip a flag, so no cross-thread blocking or re-download is involved.

In `download()` both call sites are followed by `if self._cancelled: return False, "Cancelled"` and, when not cancelled, a `continue` of the outer restart loop to re-run the command.

---

## 5. Tests

### `tests/test_torrent_downloader.py` — add pause/resume restart test

The test must be deterministic. Add a `BlockingFakeProcess` (its `readline()` parks on a `threading.Event` and its `poll()` reports "still running" until the gate is set) next to `FakeProcess`, then drive the first `Popen` call with it and the resumed call with a normal finishing `FakeProcess`:

```python
class BlockingFakeProcess(FakeProcess):
    def __init__(self, gate, lines=None, exit_code=0):
        super().__init__(lines, exit_code)
        self._gate = gate

    def poll(self):
        if not self._gate.is_set():
            return None  # still "running" until released
        return super().poll()

    def readline(self):
        self._gate.wait(timeout=5)
        return super().readline()


def test_download_pause_resume_restarts(tmp_path, patch_finder, monkeypatch):
    """Pause terminates the process; resume restarts aria2c and completes."""
    gate = threading.Event()
    started = threading.Event()
    call_count = [0]

    def counting_popen(*a, **kw):
        call_count[0] += 1
        if call_count[0] == 1:
            started.set()
            return BlockingFakeProcess(gate,
                lines=["[#hash 10MiB/100MiB(10%) CN:1 DL:1.0MiB]"], exit_code=0)
        return FakeProcess(lines=["[#hash 100MiB/100MiB(100%) CN:1 DL:1.0MiB]"], exit_code=0)

    monkeypatch.setattr(subprocess, "Popen", counting_popen)
    out_dir = str(tmp_path / "out")
    dl = TorrentDownloader(FakeLogger(), aria2_path="/fake/aria2c", cleanup=True)

    result = [None]
    def run_download():
        result[0] = dl.download("magnet:?xt=foo", out_dir, expected_size=100 * 1024 * 1024)

    t = threading.Thread(target=run_download)
    t.start()
    assert started.wait(timeout=2)  # first Popen is running, blocked on readline

    dl.pause()   # sets _paused and terminates the process
    gate.set()   # unblock the fake process (EOF / next summary line after terminate)
    time.sleep(0.1)
    dl.resume()  # clears _paused → download() restarts aria2c internally
    t.join(timeout=5)

    assert result[0][0] is True
    assert call_count[0] == 2  # aria2c was re-invoked (restarted) after resume
```

How it exercises the fix: once `gate` is released the loop observes `_paused` and parks in `_wait_for_resume()`; `resume()` unparks it and the outer loop re-runs `Popen` (call 2), which finishes at 100% and returns `(True, files)`. The old broken behavior — `resume()` doing nothing and the process never restarting — leaves `call_count[0] == 1` and fails the last assertion.

### `tests/test_install_worker.py` — verify cancel does not call resume

```python
def test_cancel_does_not_resume(worker):
    """cancel() should only call cancel() on downloaders, not resume()."""
    resume_called = []
    cancel_called = []

    class FakeDownloader:
        def cancel(self):
            cancel_called.append(True)
        def resume(self):
            resume_called.append(True)
        def pause(self):
            pass

    worker._active_downloaders = [FakeDownloader()]
    worker.parallel_manager = None
    worker.downloader = None
    worker.cancel()
    assert len(cancel_called) == 1
    assert len(resume_called) == 0
```

---

## Verification

After all fixes:

```bash
python -m pytest tests/test_torrent_downloader.py tests/test_install_worker.py -v
```

All torrent-related tests should pass, including the new pause/resume-restart and cancel tests.
