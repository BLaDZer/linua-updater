# Task 37 — Torrent branch falls through: installer runs twice (double download)

## Context

After a magnet (torrent) install fails and falls back to the direct download, the direct
download runs **twice**. The user log shows two full download cycles:

```
[20:43:48] EP01: Starting download...
[20:43:48] Downloading EP01 - Get to Work from https://.../EP01.zip
[20:44:09] All download attempts failed: EP01 - Get to Work from ...
[20:44:09] EP01: Starting download...
[20:44:09] Downloading EP01 - Get to Work from https://.../EP01.zip
[20:44:28] All download attempts failed: EP01 - Get to Work from ...
[20:44:29] EP01: FAILED - All download attempts failed
```

The `if kind == "magnet":` branch of `_install_single` has no `return`, so after running
the fallback installer, control falls through to the shared `installer.run()` calls below
the branch and runs the same installer a second time. This is independent of the cancel
behavior in Task 36 — a genuinely failed torrent also double-downloads (and a successful
torrent would re-run twice too).

## How it works now

`linua_updater/workers/install_worker.py:114-148`:

```python
if kind == "magnet":
    ...
    success, message = installer.run()
    if not success:
        ...
        success, message = installer.run()   # fallback run (1)
    finally:
        ...
        self._active_downloaders.remove(torrent_dl)
elif kind == "parts":
    ...
else:
    installer = SingleDLCInstaller(...)
installer.set_progress_callback(...)   # <-- shared block
success, message = installer.run()     # <-- runs the SAME installer again (2)
return dlc_id, success, message
```

There is no `return` at the end of the magnet branch, so execution reaches the shared
`installer.run()` at the bottom and the installer object (now the direct-download one after
the fallback) is executed a second time.

## How it should work

- Each DLC's installer runs exactly once. The magnet branch returns its result instead of
  falling through to the shared `installer.run()`.

## What needs fixing

`linua_updater/workers/install_worker.py` — add an explicit return at the end of the magnet
branch (after the try/finally that removes `torrent_dl` from `_active_downloaders`):

```python
if kind == "magnet":
    ...
    finally:
        with self._active_downloaders_lock:
            try:
                self._active_downloaders.remove(torrent_dl)
            except ValueError:
                pass
    return dlc_id, success, message   # <-- add
elif kind == "parts":
    ...
```

(Alternative structural refactor is acceptable, but the minimal change is the `return`.)

## Not in scope

- Cancellation handling (Task 36).
- `SmartDownloader`/`TorrentDownloader` internals.

## Tests

### `tests/test_install_worker.py`

Add `test_install_single_magnet_fallback_runs_once`:
- Build a `worker` via `__new__` (existing fixture style), set `db` with a magnet DLC that
  has both `magnet` and `url` (so the fallback targets `SingleDLCInstaller`),
  `settings`, `mirrors`, `logger`.
- Monkeypatch `TorrentDownloader` with a stub whose `download()` returns
  `(False, "bad torrent")`.
- Monkeypatch the `SmartDownloader` (created in `_install_single`) with a stub that records
  `download` calls and returns `(False, "All download attempts failed")` — it must expose
  the attributes/API used by `SingleDLCInstaller.run` (`set_progress_callback`, `download`,
  `resume_enabled`, `cleanup`).
- Assert the direct downloader's `download` was called exactly once (this is the regression
  for the double run), and `_active_downloaders` is empty afterwards.

## Docs

No `docs/architecture.md` change needed — behavior is limited to a single run per DLC.

## Verification

```bash
python -m pytest tests/test_install_worker.py -v
./scripts/check.sh   # pytest + ruff
```

Manual smoke: run a torrent install so the torrent genuinely fails (no fallback cancel).
Confirm "Starting download..." appears exactly once after the fallback log line.