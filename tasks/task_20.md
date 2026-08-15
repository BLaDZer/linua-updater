# Task 20 — "Game not found" must never fire when a valid saved folder exists (main_window.py)

## How it works now

- `auto_detect()` logs `Game not found. Please select manually` (`main_window.py:343`) whenever `GameDetector.find_game()` (`main_window.py:336`) returns `None`.
- Because the search never consults the saved `game_path`, a user whose game lives outside the scanned locations (e.g. a mounted NTFS Windows drive) sees the warning at startup **even though the UI already shows a valid saved game folder** — a contradictory message. See the launch log in Task 18/19:
  ```
  Game path saved: /run/media/blad/WINDOWS/Games/The Sims 4
  Searching for game...
  Game not found. Please select manually
  ```

## How it should work

- The `Game not found. Please select manually` warning fires **only** when there is genuinely no playable folder: no valid saved/current value **and** no auto-detected location. With a valid saved folder present, auto-detect resolves it first (Task 19) and the warning branch is unreachable.
- When nothing is found, the message keeps the current field text untouched (no clearing of the saved value) and continues to rely on the normal `update_dlc_status` feedback for guidance.

## What needs fixing

1. Gate the not-found branch of `auto_detect` (`main_window.py:342-343`) on the resolution helper from Task 19 (`_resolve_detected_path`) returning `None` — i.e. warn only when no saved-valid path **and** no scan hit exists. This is the messaging half of the same fix as Task 19's early return; the two compose through the shared helper.
2. In the not-found branch, do not mutate the field: leave `self.path_input` as-is so a previously entered path is never wiped by a failed scan.
3. Add a test in `tests/test_ui_defaults.py` (headless, no `QApplication`) proving the invariant via the shared helper:
   - with a valid `tmp_path` game folder present, `_resolve_detected_path(str(tmp_path))` returns a truthy path, so `auto_detect`'s not-found branch is unreachable (no delegation to `find_game`);
   - with no valid saved folder and `GameDetector.find_game()` monkeypatched to `None`, resolution is `None` — the only case where the warning may appear.