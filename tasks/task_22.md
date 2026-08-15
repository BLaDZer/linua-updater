# Task 22 — Folder selection must validate the same game-folder rule for every path (main_window.py)

## How it works now

- `update_dlc_status()` (`main_window.py:279-297`) gates the status label and the Update button by **existence only**: `if not path or not os.path.exists(path)` (`main_window.py:283`).
- So the two failure cases are treated asymmetrically when the user picks a folder:
  - a **non-existent** path (e.g. typed, or a saved value pointing nowhere) hits the guard and flips to `Select valid game folder` + disables the Update button (`main_window.py:284-285`);
  - an **existing** directory that is not a game folder (no `Game/Bin/TS4_x64.exe`) passes the guard, then `detect_installed()` (`main_window.py:287`) finds no DLC and the UI shows `Installed: 0/N | Available: N` with the Update button **enabled** (`main_window.py:295-297`).
- Meanwhile every other path through the app already applies the real rule: `_persistable_game_path()` (`main_window.py:46-56`) only accepts a folder when `GameDetector._has_valid_exe(path)` — i.e. `Game/Bin/TS4_x64.exe` exists — so `_on_path_idle()` (`main_window.py:272-277`), `_persist_valid_path()` (`main_window.py:261-270`) and `browse_folder()` (`main_window.py:365-370`) silently skip persistence for a folder that merely exists, and `on_update()` explicitly warns "TS4_x64.exe not found" (`main_window.py:444-451`). Only the status label in `update_dlc_status` uses a weaker, existence-only check.

## How it should work

- The status label / Update button enforce the **exact same** game-folder rule as persistence: a folder is usable only when it exists **and** contains `Game/Bin/TS4_x64.exe` (the `_persistable_game_path` / `GameDetector._has_valid_exe` rule).
- Any path that is not a valid game folder — whether it does not exist **or** it exists without the executable — maps to the invalid state (`Select valid game folder`, Update disabled). An empty/partial input, a missing path, and a real-but-exe-less directory are all treated identically.
- Picking an existing folder without game files therefore no longer looks like a working installation (no more `Installed: 0/N` + enabled Update button); the app flags it the same way it flags a non-existent path.

## What needs fixing

1. `update_dlc_status()` (`main_window.py:282-286`) — replace the existence-only guard with the shared validity rule:
   - `path = _persistable_game_path(self.path_input.text())` (covers empty input, non-existent paths, and existing directories without the exe in one rule);
   - if `path` is `None` → `self.dlc_status.setText("Select valid game folder")` and `self.update_btn.setEnabled(False)`; `return`.
   - When valid, keep the rest of the method unchanged (`detect_installed`, installed/available counts, button labels — `main_window.py:287-297`).
2. Leave `_on_path_idle` (`main_window.py:272-277`), `_persist_valid_path` (`main_window.py:261-270`), `browse_folder` (`main_window.py:365-370`) and `_startup_detect_message` (`main_window.py:59-70`) untouched — they already route through `_persistable_game_path`, so `update_dlc_status` now agrees with what gets persisted and with the startup message.
3. Optionally factor the decision into a module-level pure helper next to `_persistable_game_path` (mirrors the helper style used for Task 21, `main_window.py:59-70`), e.g.:
   - `_game_folder_state(text)` → `_persistable_game_path(text) is not None`, so the UI branch reads `if not _game_folder_state(self.path_input.text()): ...` and the rule is covered by a headless test without hardening the method.
4. Tests in `tests/test_ui_defaults.py` (headless, no `QApplication`):
   - `_game_folder_state("")` and `_game_folder_state("   ")` → `False`;
   - `_game_folder_state(str(tmp_path))` for a real directory with **no** `Game/Bin/TS4_x64.exe` → `False` (this is the case that currently slips through);
   - `_game_folder_state("/no/such/game/folder")` → `False`;
   - `tmp_path` with `Game/Bin/TS4_x64.exe` → `True`;
   - existing `_persistable_game_path` tests (`tests/test_ui_defaults.py:47-62`) must remain valid and unchanged — the new helper composes them rather than duplicating the rule.