# Task 43 — Split `TorrentDownloader` into a service + `TorrentClient` abstraction

## Context

`TorrentDownloader` (`linua_updater/core/torrent_downloader.py`) mixes two concerns: (a) the
engine-specific mechanics of driving `aria2c` as a subprocess (finding the binary, building the
command, `Popen` with `CREATE_NO_WINDOW`, reading/parsing `--summary-interval=1` output, terminate/kill
reaping), and (b) the engine-agnostic orchestration of a download (cancel/pause/resume state machine,
restart-on-resume loop, progress-callback feed with dedupe, artifact cleanup, lifecycle logging).

This task splits them so an alternative torrent engine (e.g. libtorrent) can be added later without
touching the service:

- `TorrentClient` — abstract torrent-engine contract in `core/clients.py` (next to `HTTPClient`).
- `Aria2TorrentClient` — the sole implementation today, owning everything aria2-specific.
- `create_torrent_client(logger, client_name="aria2")` — external factory (registry of client
  type → builder) that "knows enough" to construct the right client; the single extension point.
- `TorrentDownloader` — a service that only orchestrates one injected `TorrentClient`.

## How it works now

- `TorrentDownloader.__init__` (`torrent_downloader.py:42-55`) resolves the aria2 path via
  `Aria2Finder(logger).find()` (`utils/aria2.py`) and stores process/state fields (`_process`,
  `_command`, `_out_dir`, `_aria2_path`) alongside orchestration flags (`_cancelled`, `_paused`,
  `_active`) and the progress callback.
- `download()` (`torrent_downloader.py:147-262`) builds the aria2 command once
  (`_build_command`, `:102-116`), then runs an outer restart loop: `Popen` the command, read stdout
  line-by-line, stop on cancel, restart on pause (`restart`), parse summary lines for progress
  (`_parse_summary`/`_parse_size`, `:118-145`), dedupe progress ticks, and on completion clean up
  `.aria2`/`.torrent` artifacts (`:245-258`) and return the file list.
- `cancel()` (`:60-78`) does terminate→wait→kill→wait reaping; `pause()` (`:80-89`) terminates the
  process (keeps `.aria2` resume state); `resume()` (`:91-95`) clears `_paused` so the loop restarts
  the command with `--continue=true`.
- Callers: `install_worker.py:189` (`TorrentDownloader(self.logger)` per magnet source),
  `installers.py:263` (type hint) and `TorrentInstaller` uses `set_progress_callback`/`download`/
  `cleanup` (`installers.py:250,301,305`).

## How it should work

The torrent-engine abstraction lives in `core/clients.py`:

```python
class TorrentClient(ABC):
    # Implementations must be responsive to stop()/abort() from other threads:
    # a blocked read_progress() must unblock once stop()/abort() is called.
    @property
    @abstractmethod
    def name(self) -> str: ...
    @abstractmethod
    def is_available(self) -> bool: ...                    # engine usable now
    @abstractmethod
    def start(self, magnet: str, out_dir: str) -> None: ...  # raise on failure
    @abstractmethod
    def read_progress(self) -> Optional[Tuple[float, float, float]]: ...  # (pct, dl, total) or None on stream end
    @abstractmethod
    def stop(self) -> None: ...  # keep resumable state (pause)
    @abstractmethod
    def abort(self) -> None: ...  # stop and reap (cancel)
    @abstractmethod
    def wait_exit(self) -> int: ...

def create_torrent_client(logger: ImprovedLogger, client_name: str = "aria2") -> TorrentClient:
    # TORRENT_CLIENTS: Dict[str, Callable[[ImprovedLogger], TorrentClient]] registry;
    # "aria2" -> Aria2TorrentClient. Unknown name raises ValueError.
```

`Aria2TorrentClient` owns `_process`, `_command`, `_out_dir`, `_aria2_path` and a lock guarding the
process pointer (moved from the service). `read_progress()` internally skips non-progress lines and
returns `None` on EOF. `start()` also does `os.makedirs(out_dir, exist_ok=True)`. It uses
`_parse_size`/`_parse_summary`, the `ARIA2_FLAG_*`/`TORRENT_STOP_TIMEOUT_SEC`/`PROCESS_KILL_WAIT_SEC`
constants and `_popen_kwargs()` — all moved to `core/clients.py`.

`TorrentDownloader` is the service: `__init__(self, logger, client, cleanup=True)` (client required).
It keeps `set_progress_callback`, `cancel`/`pause`/`resume` (delegating process control to
`client.stop()`/`client.abort()`), the flags, `_wait_for_resume`, the outer restart loop in
`download()` (driving `client.start`/`client.read_progress`/`client.wait_exit`), progress-callback
dedupe, artifact cleanup and all lifecycle logging — behavior identical to today. `is_available()`
false → `(False, "aria2c not found")` WARNING log, same as now.

## What needs fixing

1. **`linua_updater/core/clients.py`** — add, beside `HTTPClient`:
   - `TorrentClient` ABC (above); import `ABC`, `abstractmethod`.
   - `ARIA2_FLAG_*` constants (`--seed-time=0`, `--bt-stop-timeout=`, `--continue=true`,
     `--allow-overwrite=true`, `--file-allocation=none`, `--summary-interval=1`,
     `--check-integrity=true`), `TORRENT_STOP_TIMEOUT_SEC`, `PROCESS_KILL_WAIT_SEC`.
   - `_popen_kwargs()` (verbatim from `torrent_downloader.py:32-38`).
   - `Aria2TorrentClient(TorrentClient)`: `__init__(logger, aria2_path=None)` resolves via
     `Aria2Finder`; static `_parse_size`/`_parse_summary` (verbatim); `_build_command`;
     `start()` = `makedirs` + `Popen(...)` + `_popen_kwargs()` (raises on Popen failure or missing
     stdout with the existing "aria2c did not provide stdout" message); `read_progress()`
     skip-loop over `_parse_summary` returning ticks or `None` on EOF; `stop()` = terminate if
     running; `abort()` = terminate→wait(`PROCESS_KILL_WAIT_SEC`)→kill→wait reaping; `wait_exit()`.
     Guard `_process` access with an internal `threading.Lock` (as `torrent_downloader.py:55,62` did).
   - `create_torrent_client(logger, client_name="aria2")` + `TORRENT_CLIENTS` registry.
2. **`linua_updater/core/torrent_downloader.py`** — strip to the service:
   - `TorrentDownloader.__init__(self, logger, client: TorrentClient, cleanup: bool = True)` (also keep
     it usable as a drop-in with the same `cleanup` attribute that `installers.py:250` reads).
   - Delete aria2 internals (constants, `_popen_kwargs`, `_build_command`, `_parse_size`,
     `_parse_summary`, `_process`/`_command`/`_out_dir`/`_aria2_path`); keep `_cancelled`/`_paused`/
     `_active`/`_display`/`_source`/`_progress_callback`.
   - `download()` refactored unchanged-in-behavior:
     not-available → `(False, "aria2c not found")`; outer loop calling `client.start(...)` then inner
     loop of `client.read_progress()` with cancel/pause checks, `expected_size` fallback, dedupe,
     callback; post-loop `client.wait_exit()`, paused→`_wait_for_resume()`→`continue`, non-zero →
     `(False, f"aria2c exit code {exit_code}")`, else break; artifact cleanup as today.
   - `cancel()` sets `_cancelled` and calls `self._client.abort()`; `pause()` sets `_paused` and calls
     `self._client.stop()`; `resume()` clears the flag.
3. **`linua_updater/workers/install_worker.py`** — import `create_torrent_client` from
   `linua_updater.core.clients`; at `install_worker.py:189` build
   `downloader = TorrentDownloader(self.logger, create_torrent_client(self.logger))`. `_active_downloaders`
   union type and `_build_installer` cast unchanged.

## Tests

- New **`tests/test_torrent_clients.py`**:
  - `Aria2TorrentClient`: `is_available` with/without a real path; `start()` builds the command with
    the existing `ARIA2_FLAG_*` set and passes `CREATE_NO_WINDOW` (patch `linua_updater.core.clients`
    module's `subprocess`/`_popen_kwargs`); `read_progress` returns parsed ticks and skips
    non-progress lines; missing stdout raises the "aria2c did not provide stdout" message; `stop`/
    `abort` reap with the `StubbornProcess` pattern from `test_torrent_downloader.py:354-375`;
    `_parse_size`/`_parse_summary` still parse `12.3MiB/123.4MiB(10%)` and the `100%` case.
  - `create_torrent_client(FakeLogger())` returns an `Aria2TorrentClient`; unknown name raises
    `ValueError`.
- **`tests/test_torrent_downloader.py`** (service) — update construction to
  `TorrentDownloader(logger, Aria2TorrentClient(logger, aria2_path=str(aria2c)), cleanup=True)`
  (add a small `make_dl(logger, aria2_path)` helper; `patch_finder` fixture now patches
  `Aria2Finder` in `linua_updater.core.clients`). `_popen_kwargs`/`_parse_summary` assertions move to
  the client tests. Migrate `test_cancel_kills_when_terminate_ignored` to the client (`client._process
  = StubbornProcess(); client.abort()`). Keep all subprocess-driven scenarios (monkeypatched
  `subprocess.Popen` still intercepts the client's spawn): success+cleanup, logs, missing aria2,
  non-zero exit, cancel before/after start, progress callback, pause/resume restarts (calls start
  twice). Add a `StubTorrentClient(TorrentClient)` service test verifying the restart loop and
  progress-dedupe without any subprocess.
- **`tests/test_install_worker.py`** — `FakeTorrentDownloader` monkeypatch of
  `install_worker.TorrentDownloader` is unaffected; verify the magnet branch still constructs via
  `create_torrent_client` (assert import/Callable used) or leave as-is (duck-typed stub). If the
  worker patch is kept entire, no edits are strictly required.
- **`tests/test_installers.py`** — `StubTorrentDownloader` (duck-typed) unaffected.
- Run `./scripts/check.sh` (`line-length = 160`, typed generics e.g. `Optional[Tuple[float, float,
  float]]`, `Dict[str, Callable[..., TorrentClient]]`).

## Docs

- **`docs/architecture.md`** — components table (`:106-119`): rewrite the `TorrentDownloader` row to
  describe the service (orchestrates one injected `TorrentClient`; keeps the pause/resume restart
  loop, progress dedupe, cleanup, lifecycle logging); add `TorrentClient`/`Aria2TorrentClient`/
  `create_torrent_client` rows; note `Aria2Finder` is now consumed by `Aria2TorrentClient`.
- **`tasks/refactoring-plan.md`** — class→module map: note `TorrentClient`/`Aria2TorrentClient` live
  in `core/clients.py` alongside `HTTPClient`.
- **`tasks/task_43.md`** — this file.

## Notes / out of scope

- No feature or behavior changes; the service keeps its `download`/`set_progress_callback`/`cancel`/
  `pause`/`resume` surface so `TorrentInstaller` and `SmartDownloader`-union typing are untouched.
- The factory defaults to `aria2`; a config-driven client selector is a follow-up, not part of this
  task. Adding libtorrent = implement `TorrentClient` + one registry entry.
- `utils/aria2.py` (`Aria2Finder`) unchanged.
- The one message change: a `Popen` startup failure now surfaces as the raised error string from
  `Aria2TorrentClient.start()` (currently the raw `str(e)`), keeping the same "aria2c did not provide
  stdout" and exit-code paths.