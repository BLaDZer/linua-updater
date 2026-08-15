# Task 19 — Auto Detect checks the saved folder first and skips the search when it's valid (main_window.py, detection.py)

## How it works now

- On startup and on every "Auto Detect" click, `auto_detect()` (`main_window.py:332-343`) unconditionally logs `Searching for game...` (`main_window.py:335`) and runs the full `GameDetector.find_game()` scan (`main_window.py:336`), which probes the Windows registry, fixed Windows search paths, Steam library VDFs and Proton compatdata (`detection.py:121-151`).
- The saved/current folder is never consulted: a valid `game_path` already present in the field (`__init__` pre-fill at `main_window.py:90-92`, or a previously typed/browsed path) is re-scanned from scratch every time.
- On machines where the game lives outside the scanned locations (e.g. a mounted NTFS Windows drive at an arbitrary path), the scan returns `None` even though the shown folder is a valid game folder.

## How it should work

- Before searching, `auto_detect` evaluates the current field text (which already carries the saved path after `__init__` pre-fill) with the same validity rule the rest of the app relies on (`GameDetector._has_valid_exe`, `detection.py:11-14`).
- When the current/saved folder is a valid game folder:
  - the field is set to it and it is persisted via the existing `_persist_valid_path` (`main_window.py:222-231`);
  - a neutral line is logged — `Using saved game folder: <path>` — making clear it came from saved state, not a change (parity with the "Game path saved" wording from Task 17);
  - the function returns immediately, **skipping** `GameDetector.find_game()` and the `Searching for game...` log.
- The full scan runs only when there is no valid saved/current folder.

## What needs fixing

1. Factor a module-level pure helper in `main_window.py`, e.g. `_resolve_detected_path(text)`:
   - if `_persistable_game_path(text)` is truthy → return it;
   - otherwise return `GameDetector.find_game()`.
   This keeps the "check saved first, then search" decision unit-testable without a `QApplication`.
2. Rewrite `auto_detect()` (`main_window.py:332-343`) to resolve once via the helper:
   - if a path is resolved: `self.path_input.setText(path)`, `self._persist_valid_path(path)`, log `Using saved game folder: {path}` when it came from the saved value (and `Game found: {path}` — the existing message at `main_window.py:341` — when it came from the scan), then `self.update_dlc_status()`;
   - only when the helper returns `None` fall through to the not-found branch (Task 20).
3. Tests (new or extended in `tests/test_ui_defaults.py`, plain `pytest`/`monkeypatch`, no `QApplication`):
   - a `tmp_path` with `Game/Bin/TS4_x64.exe` → `_resolve_detected_path(str(tmp_path))` returns it and does **not** call `GameDetector.find_game()` (assert via monkeypatched `find_game`);
   - `_resolve_detected_path("")` delegates to `GameDetector.find_game()` (monkeypatch it to return `None` / a fake path and assert the delegation);
   - an existing dir **without** the exe delegates to `find_game()` (does not short-circuit on mere existence).