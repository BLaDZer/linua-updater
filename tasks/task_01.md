# Task 01 — Make parallel install actually parallel

## How it works now

`InstallWorker.run()` (`LinuaUpdater_v4.3.0.py:1074`) creates a `ParallelInstallManager` with a real `ThreadPoolExecutor`:

- `ParallelInstallManager.__init__` spins up `ThreadPoolExecutor(max_workers=self.max_workers)` (`:866`) but **never submits any futures**.
- `run()` iterates `for dlc_id in self.dlc_ids` sequentially (`:1083`–`:1107`), calling each installer's `run()` inline on the worker thread.
- Result: downloads are 100% serial. The `max_workers` setting (Settings dialog, default 3) only controls an unused pool size.
- The manager's `cancel_all()` shuts the executor down, but because nothing was submitted, cancel relies solely on the shared `SmartDownloader._cancelled` flag.

Additional trap for real parallelism: `run()` creates a **single shared** `SmartDownloader` (`:1062`) used by every installer. Its mutable state — `session`, `_cancelled`, `_progress_callback` — is shared across threads, so naively submitting installs in parallel would introduce data races (mixed progress callbacks, session reuse, cancel flag races).

## How it should work

- The worker submits each DLC install as a unit of work to the `ThreadPoolExecutor`, with up to `max_workers` downloading concurrently.
- Each concurrent install uses its **own** `SmartDownloader` instance (fresh `requests.Session`, own cancel flag), avoiding shared mutable state.
- Per-DLC progress is routed through `ParallelInstallManager.update_download_progress(...)`, which aggregates into overall progress.
- `cancel()` still works: sets the shared cancel flag so in-flight futures stop, and shuts down the pool (`cancel_futures=True`).
- `status_updated`/`download_detail`-style signals map correctly per DLC.
- The UI reports "Installing N DLC (M threads)" truthfully, and the Settings `max_threads` value takes real effect.

## What needs fixing

1. `InstallWorker.run()` — replace the sequential loop with `parallel_manager.executor.submit(...)` per DLC + `as_completed`, honoring `max_workers`.
2. Installers must receive per-install downloader instances instead of one shared one (`SingleDLCInstaller`/`MultiPartInstaller` take `downloader` as a constructor arg — pass a fresh `SmartDownloader` per future).
3. Fix the ordering/serialization of results: `result_ready` currently depends on install order; with futures the order is unordered — UI counters (successful/failed) still work since they only count.
4. Make `ParallelInstallManager._download_progress` update thread-safe (it is written from multiple futures now) — a lock or per-future isolation.
5. Recheck `SingleDLCInstaller` temp-file naming (`{dlc}_{int(time.time())}.zip`, `:920`) — parallel runs of the same DLC id could collide; make it unique per worker.
6. `cancel()` — verify it interrupts in-flight downloads immediately and doesn't leave `.part` files for DLC that never started cleanly.
7. Update `docs/architecture.md` §4 (currently documents the parallel class as downloading serially in the worker loop).