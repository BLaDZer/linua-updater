# Task 18 — Don't re-save / re-log an unchanged game path at startup (main_window.py)

## How it works now

- On launch, `__init__` pre-fills the game folder field from the saved config: `saved = self.config.get("game_path", ""); if saved: self.path_input.setText(saved)` (`main_window.py:90-92`).
- `path_input` is wired to `on_path_changed` in `setup_ui` (`main_window.py:141-143`), so that `setText` fires `textChanged` even though the user typed nothing.
- `on_path_changed` (`main_window.py:219-220`) schedules `_on_path_idle` after 500 ms.
- `_on_path_idle` (`main_window.py:233-237`) calls `_persist_valid_path` (`main_window.py:222-231`), which — when the value is a valid game folder — runs `config.set("game_path", path)` (rewriting the whole JSON file) and logs `Game path saved: <path>` (`main_window.py:236`) on **every** launch, even when the stored value did not change. The user sees this as if their path changed, when it was only loaded from saved state.

## How it should work

- A persisted value that is already equal to what's stored is not written again and not announced. The idle handler only fires the `Game path saved` message (and the redundant `config.set`) when a *different* valid path was actually entered.
- Startup with a valid saved path should be silent with respect to "saving": the `game_path` value is untouched and no "Game path saved" log line appears.
- `update_dlc_status` still runs as before (`main_window.py:237`), so the UI status reflects the current field regardless of whether anything was persisted.

## What needs fixing

1. Factor a module-level pure helper next to `_persistable_game_path` (`main_window.py:46-56`), e.g. `_changed_valid_path(text, stored)`: returns `_persistable_game_path(text)` only when it is truthy **and** differs from `stored`, else `None`. Both sides are compared stripped, and a stored `""`/empty value never matches a real path.
2. Route `_on_path_idle` (`main_window.py:233-237`) through the new helper against `self.config.get("game_path", "")`; only then call `self.config.set(...)` and log `Game path saved: {path}`.
3. Keep `_persist_valid_path` (`main_window.py:222-231`) for the Browse/Auto Detect call sites, or fold it into the helper — but keep the "skip when unchanged" behavior shared so all persistence paths behave identically.
4. Tests in `tests/test_ui_defaults.py` (headless `pytest`, no `QApplication`):
   - `_changed_valid_path("", "")` → `None`;
   - a `tmp_path` with `Game/Bin/TS4_x64.exe` stored as the identical string → `None` (unchanged, must not re-save);
   - a `tmp_path` with `Game/Bin/TS4_x64.exe` differing from an unrelated stored value → returns the stripped path;
   - a valid `tmp_path` while `stored` is `""` → returns the path (a genuinely new save);
   - surrounding whitespace is stripped before comparison.