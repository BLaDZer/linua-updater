# Task 11 — Export Logs fails when the Desktop directory doesn't exist

## How it works now

- `ImprovedLogger.export_logs()` (`LinuaUpdater_v4.3.0.py:105`) hardcodes the destination as `Path.home() / "Desktop"`:
  ```python
  desktop = Path.home() / "Desktop"
  export_path = desktop / export_name
  shutil.copy(log_file, export_path)
  ```
- The target directory is never created before the copy. On systems where `~/Desktop` does not exist (Linux boxes, localized Windows setups, headless profiles), `shutil.copy` raises `FileNotFoundError` (`[Errno 2] No such file or directory`), which is caught and surfaced to the user as "Failed to export logs:".
- `LinuaUI.export_logs()` (`:2126`) calls the logger method with no arguments and then shows a "Logs exported" confirmation message box.

## How it should work

- "Export Logs" exports automatically to a sensible default location with **no save dialog and no confirmation dialog**.
- The destination is resolved robustly and its parent directory is created before copying, so the export never fails on a missing Desktop:
  1. Real Desktop via `QStandardPaths.writableLocation(DesktopLocation)`.
  2. Fallback if that's empty → `Path.home()`.
  3. Final fallback → the application log directory itself.
- After a successful export the app **opens the file explorer revealing the created file** (on Windows `explorer /select`, on macOS `open -R`, on Linux `xdg-open` the containing folder).
- On failure a warning message is still shown (silent failure would hide problems).

## What needs fixing

1. `ImprovedLogger.export_logs(self, target_path=None)`:
   - If `target_path` is provided, copy to that exact path.
   - Otherwise resolve the default directory per the fallback chain above (Desktop via `QStandardPaths` → `Path.home()` → log dir).
   - `export_path.parent.mkdir(parents=True, exist_ok=True)` before `shutil.copy`.
   - Keep the `(bool, path-or-error)` return contract.
2. `LinuaUI.export_logs()`:
   - No `QFileDialog`, no save prompt, and no success `QMessageBox`.
   - On success, reveal the exported file in the file explorer (platform-specific: `explorer /select,` / `open -R` / `xdg-open <dir>`) and log the location.
   - On failure only, show the existing warning message box.
3. Add a small cross-platform `_reveal_in_explorer(path)` helper (module-level).
4. Import `QStandardPaths` from `PyQt6.QtCore` (the existing import on `:36`).