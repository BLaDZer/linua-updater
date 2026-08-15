# Task 21 — Auto Detect runs only on button click; startup prints one of three saved-path states (main_window.py)

## How it works now

- `__init__` schedules `QTimer.singleShot(500, self.auto_detect)` (`main_window.py:120`), so every app launch runs the detection flow automatically.
- The same `auto_detect()` (`main_window.py:358-372`) also backs the "Auto Detect" button (`main_window.py:171-172`). It picks its log line by where the resolved folder came from: `Using saved game folder: {saved}` (`main_window.py:364-365`) when the current/saved field value is a valid game folder, else `Game found: {path}` (`main_window.py:367`).
- Net effect: clicking the button prints `Using saved game folder: ...`, which reads like a startup notice on a manual action; conversely, launch triggers the full detection flow ("Searching for game...", scans, warnings) even though the user did nothing.

## How it should work

- **Startup:** `auto_detect()` is never called. A separate startup-only `_startup_detect()` validates the *persisted* `game_path` and prints exactly one of three states — never an OS scan, the field keeps its value, and `update_dlc_status()` runs so the UI label reflects the folder:
  1. **No saved path** (stored value empty/whitespace) → tell the user no folder is saved and ask them to use the "Auto Detect" button or choose the folder manually.
  2. **Stored path is not a valid game folder** → warn that the stored path is not a valid game folder and ask for "Auto Detect" or manual selection.
  3. **Stored path is a valid game folder** → one neutral line `Using saved game folder: <path>`.
- **"Auto Detect" button:** `auto_detect()` is a pure button action and always reports the result as a detection:
  - valid saved/current folder → resolved and logged as `Game found: <path>` (no scan needed);
  - otherwise → `Searching for game...`, run `GameDetector.find_game()` (via `_resolve_detected_path`, `main_window.py:59-69`), then `Game found: <path>` or `Game not found. Please select manually`.
  - `Using saved game folder` is never printed on a button click.

## What needs fixing

1. `auto_detect()` (`main_window.py:358-372`) — remove the `saved = _persistable_game_path(...)` / `Using saved game folder` branch. Always log `Game found: {path}` when a path is resolved. Log `Searching for game...` first only when `_persistable_game_path(self.path_input.text())` is falsy (i.e. a real scan runs); when the saved value is already valid, skip the scan and the "Searching" line. Keep `self.path_input.setText(path)`, `self._persist_valid_path(path)`, `self.update_dlc_status()` and the existing not-found warning (`main_window.py:371-372`).
2. Add `_startup_detect()` method — read `self.config.get("game_path", "")`, log exactly one line returned by the `_startup_detect_message(saved)` helper (below) and call `self.update_dlc_status()`; do nothing else (no search, no persistence).
3. `__init__` (`main_window.py:120`) — schedule the startup check only: `QTimer.singleShot(500, self._startup_detect)`.
4. Factor a module-level pure helper next to `_persistable_game_path` (`main_window.py:46-56`), e.g. `_startup_detect_message(saved)` — it decides the startup state and always returns a message string (mirrors the helper style of `_persistable_game_path` / `_changed_valid_path` `main_window.py:72-81`):
   - `saved` is empty/whitespace → the **no saved path** state, e.g. `"No game folder saved. Click 'Auto Detect' or choose the folder manually."`;
   - `saved` is non-empty but `_persistable_game_path(saved)` is `None` → the **not a valid game folder** state, e.g. `"Saved game folder is not a valid game path: {stripped}. Click 'Auto Detect' or choose the folder manually."`;
   - otherwise → the **valid** state: `f"Using saved game folder: {path}"`.
5. Tests in `tests/test_ui_defaults.py` (headless `pytest`/`tmp_path`, no `QApplication`) for `_startup_detect_message`:
   - a `tmp_path` with `Game/Bin/TS4_x64.exe` → returns exactly `"Using saved game folder: <tmp_path>"`;
   - `_startup_detect_message("")` and `_startup_detect_message("   ")` → non-empty message that mentions `"Auto Detect"` and manual selection (state 1);
   - `_startup_detect_message("/no/such/game/folder")` → non-empty message stating the path is not a valid game folder and mentioning `"Auto Detect"` / manual selection (state 2);
   - existing `_resolve_detected_path` tests (valid saved path returns it and skips `find_game`; empty/invalid delegates) remain valid and unchanged.

Note: do not add a `from_startup` flag parameter to `auto_detect()` — PyQt6's `QPushButton.clicked` emits a `checked` bool that would land on such a parameter and silently corrupt the behavior. The separate `_startup_detect()` method avoids that coupling.