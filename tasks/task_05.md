# Task 05 — No blocking network I/O on the UI thread

## How it works now

- `LinuaUI.__init__` schedules two startup operations directly on the UI thread:
  - `QTimer.singleShot(100, self.check_for_updates)` (`:1922`) → `check_for_updates` calls `requests.get(VERSION_CHECK_URL, timeout=10)` synchronously (`:246`), freezing the UI up to 10s.
  - `QTimer.singleShot(300, self.run_diagnostics)` (`:1923`) → `NetworkDiagnostics.diagnose()` runs `detect_region()` (`ipapi.co`, `timeout=5`), two `HEAD` connection tests (`timeout=5` each), and up to 6 proxy probes (`timeout=10` each) — worst case tens of seconds of UI freeze at startup.
- `UpdateChecker.check_for_updates` is invoked via `QTimer.singleShot(0, ...)` (`:1936`) — still on the UI thread.
- This violates the documented design contract (`docs/architecture.md` §2: "The UI thread never performs network or disk-intensive work directly.")

## How it should work

- All network work at startup runs in background threads; the UI stays responsive; results are delivered via Qt queued signals back to the UI thread.
- Pattern: small QObject workers (like `UpdateChecker` already is) moved to a `QThread`, with a `finished` result signal connected to UI slots.

## What needs fixing

1. `LinuaUI.check_for_updates` (`:1928`) — run `UpdateChecker.check_for_updates` in a dedicated `QThread` (or reuse the worker pattern); the existing signals `update_available`/`no_update`/`check_failed` already bridge threads correctly.
2. `LinuaUI.run_diagnostics` (`:2062`) — run `NetworkDiagnostics.diagnose()` off the UI thread; emit a result signal that sets `self.diagnostics` and rebuilds `self.downloader` back on the UI thread (careful: this currently happens inline at `:2090`).
3. Preserve the 3-hour diag cache write (`:2092`) — move it to the worker too, or keep it on the UI thread after a result signal (cheap JSON write is acceptable; the network probes are the problem).
4. Keep the deferred `QTimer.singleShot` scheduling (100/300/500 ms) — that part is fine; only the blocking calls move off-thread.
5. Update `docs/architecture.md` §2 / §3 to describe the threaded startup diagnostics accurately.