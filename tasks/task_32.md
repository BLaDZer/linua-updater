# Task 32 — Fix `TypeError: 'bool' object is not callable` when resuming a paused download

## Context

Clicking the **Resume** button while a download is paused crashes the UI:

```
Traceback (most recent call last):
  File "linua_updater\ui\main_window.py", line 702, in on_resume
    self.install_worker.resume()
  File "linua_updater\workers\install_worker.py", line 84, in resume
    downloader.resume()
TypeError: 'bool' object is not callable
```

The root cause is an attribute/method name collision in `SmartDownloader`:

- `linua_updater/core/downloader.py:17` — `self.resume = resume` stores a **boolean** instance attribute named `resume` (the "Resume interrupted downloads" setting).
- `linua_updater/core/downloader.py:47` — `def resume(self):` is the pause/unpause **method**.

The instance attribute shadows the method, so on any real `SmartDownloader`, `downloader.resume` resolves to a `bool` and calling it raises `TypeError`. Note that the boolean attribute is **not** dead code — it carries the setting into `download(..., resume=self.dl.resume)` at `core/installers.py:44` and `:129`. The fix must preserve the flag while removing the collision.

`TorrentDownloader` is unaffected — it has a `resume()` method and no `self.resume` attribute.

## How it works now

- `linua_updater/core/downloader.py:17` — `SmartDownloader.__init__` sets `self.resume = resume` (bool).
- `linua_updater/workers/install_worker.py:79-84` — `InstallWorker.resume()` iterates `_active_downloaders` and calls `downloader.resume()` on each. For a `SmartDownloader` this hits the shadowed boolean attribute and crashes.
- `linua_updater/core/installers.py:44,129` — the *value* of that attribute is read as `self.dl.resume` and passed to `download(..., resume=...)` to enable resuming an interrupted `.part` file via HTTP `Range` headers.
- `tests/test_downloader.py:102` — the existing pause test works around the bug by calling `SmartDownloader.resume(dl)` (class method reference) instead of `dl.resume()`.

## How it should work

- `downloader.resume()` must be a callable method that flips `_paused` back to `False` and notifies the pause condition.
- The "resume interrupted downloads" preference must still reach `download(..., resume=...)` in the installers.
- `InstallWorker.resume()` (`install_worker.py:79-84`) must work for both `SmartDownloader` and `TorrentDownloader` entries in `_active_downloaders`.
- No behavior change for `cancel()`, `pause()`, or the download retry logic.

## What needs fixing

### 1. `SmartDownloader.__init__` — rename the flag attribute

`linua_updater/core/downloader.py:17`:

```python
self.resume = resume
```

→

```python
self.resume_enabled = resume
```

### 2. `installers.py` — update the two consumers

`linua_updater/core/installers.py:44` and `:129`:

```python
ok, reason = self.dl.download(url, temp, dlc_name, resume=self.dl.resume, expected_size=expected_size)
```

→

```python
ok, reason = self.dl.download(url, temp, dlc_name, resume=self.dl.resume_enabled, expected_size=expected_size)
```

(and the same replacement at line 129).

No change is needed in `install_worker.py` or `main_window.py` — the call sites are correct once the method is reachable again.

### 3. `tests/test_downloader.py` — drop the workaround

`tests/test_downloader.py:102` currently calls `SmartDownloader.resume(dl)`. Replace with the normal `dl.resume()`. This turns the test into a regression guard: if the attribute/method collision is ever reintroduced, the test fails loudly instead of silently passing.

## Not in scope

- Changing the download/retry logic or the pause/cancel semantics.
- `TorrentDownloader` — already correct.
- The `download(..., resume=...)` parameter signature — it stays as-is.

## Tests

### `tests/test_downloader.py`

1. Update `test_pause_blocks_until_resume` (line 89) to call `dl.resume()` instead of `SmartDownloader.resume(dl)` (line 102). The test must still pass, proving the method is reachable.
2. Add `test_resume_method_is_callable` — construct a `SmartDownloader`, assert `callable(dl.resume)` and `not dl.resume_enabled`/`dl.resume_enabled` matches the constructor arg.
3. Add `test_resume_flag_survives_rename` — construct with `resume=True`, assert `dl.resume_enabled is True` and that it is a plain bool attribute (i.e. `dl.resume` is the method, `dl.resume_enabled` is the flag).

### `tests/test_installers.py`

4. Existing `FakeDownloader` (lines 16-19) uses `self.resume` as an attribute — the real code no longer reads `self.dl.resume`, so any test that relies on the mock must be updated to `self.resume_enabled` to mirror the real contract. Verify all installer tests still pass.

## Docs

Update `docs/architecture.md` if it mentions `SmartDownloader` internals: note that `SmartDownloader` exposes `resume()` as a method and stores the resume preference in `resume_enabled` (to avoid shadowing).

## Verification

```bash
./scripts/setup.sh   # if needed
./scripts/check.sh   # pytest + ruff
```

All existing tests must pass alongside the new ones.
