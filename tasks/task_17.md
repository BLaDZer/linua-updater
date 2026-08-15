# Task 17 — Persist manually typed game folder path (main_window.py)

## How it works now

- Manually typing the game folder into `self.path_input` fires only `on_path_changed()` (`main_window.py:206-207`), which schedules `update_dlc_status` after 500 ms and writes nothing to config.
- Only `browse_folder()` (`main_window.py:295-300`) and `auto_detect()` (`main_window.py:302-313`) persist via `self.config.set("game_path", folder)`.
- `__init__` (`main_window.py:77-79`) prefills the field from `config.get("game_path", "")` on startup, so a manually typed (even valid) path is silently discarded on the next launch.
- `ConfigManager.set` (`config.py:27-29`) writes the whole JSON file on every call, so naive per-keystroke saving would write to disk on each character.

## How it should work

- A manually typed path is persisted to `game_path` **only when it passes the valid game folder check** — i.e. `Game/Bin/TS4_x64.exe` exists, using the same `GameDetector._has_valid_exe()` (`core/detection.py:11-14`) rule that `on_update` relies on (`main_window.py:366-367`). A merely existing directory or partial input is never saved.
- When the folder is valid, the save happens automatically once the user pauses (keep the existing 500 ms debounce pattern from `on_path_changed`), giving parity with Browse/Auto Detect persistence.
- Invalid or incomplete input leaves `game_path` untouched; the user keeps the current status feedback (`update_dlc_status`).

## What needs fixing

1. `on_path_changed` (`main_window.py:206-207`) — extend the 500 ms `QTimer.singleShot` callback to also persist: compute `path = self.path_input.text().strip()`; if `GameDetector._has_valid_exe(path)` then `self.config.set("game_path", path)`. Keep the existing `update_dlc_status` call. (Import `GameDetector` if not already imported, or reuse the window's existing reference.)
2. Factor a module-level helper in `main_window.py` (e.g. `_persistable_game_path(text)`) that returns the stripped path when it passes `GameDetector._has_valid_exe`, else `None` — so the decision is unit-testable without constructing a `QApplication` (mirrors the helper style at `main_window.py:30-43`).
3. Optionally route `browse_folder`/`auto_detect` through the same helper so there's a single persistence path; log on manual save for parity with Browse (`main_window.py:300`).
4. Tests in `tests/test_ui_defaults.py` (headless `pytest`/`tmp_path`, no `QApplication`):
   - `_persistable_game_path("")` → `None`;
   - a `tmp_path` with no `Game/Bin/TS4_x64.exe` (even though the dir exists) → `None`;
   - a `tmp_path` with the created `Game/Bin/TS4_x64.exe` file → returns the stripped path;
   - surrounding whitespace is stripped before the check.