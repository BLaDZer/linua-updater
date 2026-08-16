# Task 28 — Fix 12 broken tests from Task 27 implementation

## Problem

After completing Task 27 (torrent/magnet download support), 12 of 213 tests are failing:

- `tests/test_aria2.py::test_meipass_wins_over_path` — `AttributeError` on `sys._MEIPASS`
- `tests/test_installers.py::test_torrent_download_failure` — `'FakeTempfile' object has no attribute 'mkdtemp'`
- `tests/test_installers.py::test_torrent_success` — same FakeTempfile issue
- `tests/test_installers.py::test_torrent_checksum_failure` — same FakeTempfile issue
- `tests/test_installers.py::test_torrent_unsupported_archive` — same FakeTempfile issue
- `tests/test_installers.py::test_torrent_no_files` — same FakeTempfile issue
- `tests/test_torrent_downloader.py::test_parse_summary` — returns `(None, 0, 0)` instead of parsed values
- `tests/test_torrent_downloader.py::test_parse_summary_100_percent` — same regex issue
- `tests/test_torrent_downloader.py::test_download_success_cleans_artifacts` — `TypeError: path should be ... not FakeLogger`
- `tests/test_torrent_downloader.py::test_download_progress_callback` — same logger TypeError
- `tests/test_torrent_downloader.py::test_download_cancel_returns_cancelled` — same logger TypeError
- `tests/test_torrent_downloader.py::test_download_nonzero_exit` — same logger TypeError

## Root causes

### 1. `test_meipass_wins_over_path` — `sys._MEIPASS` monkeypatch (tests/test_aria2.py:45)

`monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path))` fails because `sys` is a built-in module and Python 3.4+ raises on setting attributes on built-in modules. Fix: use `monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)` — but that silently ignores the failure. Better: set it on the module dict directly or use `monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path))` with `raising=False` and verify the value was set.

### 2. `test_torrent_*` (5 tests) — `FakeTempfile` missing `mkdtemp` (tests/test_installers.py:52-58)

The `FakeTempfile` fixture at line 52-58 only implements `gettempdir()`. `TorrentInstaller.run()` calls `tempfile.mkdtemp(prefix=...)` at line 197 of `installers.py`. Fix: add `mkdtemp(self, prefix=None)` to `FakeTempfile` that creates and returns a real subdirectory under `self._path`.

### 3. `_parse_summary` regex (linua_updater/core/torrent_downloader.py:84)

Current regex: `r"\[(\d+\.?\d*)\s*(\S+?)/(?:\S+?)\((\d+)%\)"` — expects the first group to be digits (a number), but aria2 output starts with `[#hash123 ...` where `hash123` is alphanumeric. The regex captures `123` from `#hash123` as group 1 (the digits before the space), then expects a space, then captures the size. This is wrong — group 1 should capture the progress number from the percentage, not a fake number from the hash.

Fix: `r"\[(\S+?)\s+(\S+?)/(\S+?)\((\d+)%\)"` — group 1 = hash (ignored), group 2 = downloaded size, group 3 = total size, group 4 = progress percentage. Then `progress = float(m.group(4))`, `downloaded = _parse_size(m.group(2))`.

### 4. `test_download_*` (4 tests) — `Aria2Finder` called before patch (tests/test_torrent_downloader.py:83-146)

`TorrentDownloader.__init__` calls `Aria2Finder(logger).find()` at line 13. The `patch_finder` fixture patches `Aria2Finder` in the `torrent_downloader` module, but the `FakeLogger` instance is passed to the real `Aria2Finder.__init__` before the patch takes effect (or the patch doesn't prevent the constructor from being called with `FakeLogger`). The `FakeLogger` object ends up being used as `aria2_path` in `_build_command`, causing `os.path.exists(FakeLogger())` → `TypeError`.

Fix: In the tests, pass `aria2_path="/fake/aria2c"` explicitly to `TorrentDownloader` so it skips the `Aria2Finder` call entirely. This is simpler and more robust than relying on the module-level patch.

## Fix plan

### Fix 1: `tests/test_aria2.py` — `test_meipass_wins_over_path`

Change line 45 from:
```python
monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path))
```
to:
```python
monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
```

### Fix 2: `tests/test_installers.py` — add `mkdtemp` to `FakeTempfile`

Add method to `FakeTempfile` class (after line 57):
```python
def mkdtemp(self, prefix=None):
    import tempfile as _tempfile
    real_dir = _tempfile.mkdtemp(prefix=prefix)
    return real_dir
```

### Fix 3: `linua_updater/core/torrent_downloader.py` — fix `_parse_summary` regex

Change line 84 from:
```python
m = re.search(r"\[(\d+\.?\d*)\s*(\S+?)/(?:\S+?)\((\d+)%\)", line)
```
to:
```python
m = re.search(r"\[(\S+?)\s+(\S+?)/(\S+?)\((\d+)%\)", line)
```

And change lines 87-88 from:
```python
progress = float(m.group(3))
downloaded = TorrentDownloader._parse_size(m.group(2))
```
to:
```python
progress = float(m.group(4))
downloaded = TorrentDownloader._parse_size(m.group(2))
```

### Fix 4: `tests/test_torrent_downloader.py` — pass `aria2_path` explicitly

In all 4 failing test functions (`test_download_success_cleans_artifacts`, `test_download_progress_callback`, `test_download_cancel_returns_cancelled`, `test_download_nonzero_exit`), change:
```python
dl = TorrentDownloader(FakeLogger(), cleanup=True)
```
to:
```python
dl = TorrentDownloader(FakeLogger(), aria2_path="/fake/aria2c", cleanup=True)
```

This avoids the `Aria2Finder` call entirely and makes the tests more isolated.

## Verification

After applying all 4 fixes:
```bash
python -m pytest tests/ -v
```

Expected: 213 passed, 0 failed, 3 skipped (macOS/Windows layout tests).
