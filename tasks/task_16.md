# Task 16 — UI portability polish (main_window.py, __main__.py, theme.py)

## How it works now

- `LinuaUI.browse_folder()` (`main_window.py:267`) opens `QFileDialog.getExistingDirectory(self, "Select The Sims 4 Folder", self.path_input.text() or "C:\\")` (`main_window.py:268`). The default directory `C:\` is meaningful only on Windows; on Linux/macOS the dialog opens at a nonexistent `C:\` whenever the path input is empty.
- The path `QLineEdit` placeholder is hardcoded to the Windows Steam example (`main_window.py:106`), `"C:\\Program Files (x86)\\Steam\\steamapps\\common\\The Sims 4"` — a Windows-only hint shown on every OS.
- The download progress bar stylesheet hardcodes `font-family:'Segoe UI',Arial;` inside the `QProgressBar` block (`main_window.py:122`). Neither `MAIN_STYLESHEET` (`theme.py:22`) nor `apply_dark_palette` (`theme.py:5`) sets any `font-family`, so rendering varies. The log `QTextEdit` uses `QFont("Consolas", 9)` (`main_window.py:152`) — `Consolas` and `Segoe UI` are Windows-first fonts; on Linux they fall back, often to a low-quality substitute, producing inconsistent text rendering.
- `__main__.py:32` and `__main__.py:36` show the "Already Running" dialog with "Check your system tray or task manager." — "task manager" is Windows/macOS-biased wording in a cross-platform app.

## How it should work

- `browse_folder`: the dialog's default directory is `self.path_input.text()` when non-empty, otherwise the platform home directory (`Path.home()`). On Windows this still lands somewhere sane (e.g. `~`); `C:\` is never hardcoded.
- Placeholder text (`main_window.py:106`): set per platform — Windows keeps the current Steam example; Linux shows something like `/path/to/the-sims-4` or a generic "The Sims 4 folder"; macOS a similar generic hint. Computed once in `setup_ui` based on `sys.platform`.
- Fonts:
  - Replace `QFont("Consolas", 9)` (`main_window.py:152`) with a cross-platform monospace: prefer `QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)` at point size 9, or fall back to the generic family `"monospace"` (`QFont("monospace", 9)`), which Qt maps to a platform-appropriate monospace face on Linux/macOS/Windows. Import `QFontDatabase` from `PyQt6.QtGui` (the existing `QFont` import is at `main_window.py:6`).
  - Fix the `font-family:'Segoe UI',Arial` in `main_window.py:122` by leaving the font stack generic with a `sans-serif` fallback so Linux picks Noto/system sans: `font-family:'Segoe UI','Noto Sans','Arial',sans-serif;` (appending `'monospace'` here would be wrong — this is a progress-bar style, not monospace). Preferably resolve the family through a small module-level helper `_ui_font_family()` or centralize it in `theme.py`. Keep it minimal.
- `__main__.py:32,36`: reword to "Check your system tray / notification area." (drop "task manager") — neutral across OSes.
- Scan the surrounding UI chrome for any other hardcoded Windows strings in scope (e.g. `TS4_x64.exe`, stray `C:\\` in `main_window.py` / docs) but limit changes to UI chrome only.

## What needs fixing

1. `main_window.py:268` — default browse dir: `self.path_input.text() or str(Path.home())`. Add `from pathlib import Path` to the imports (`main_window.py:1-3`).
2. `main_window.py:106` — per-platform placeholder via a small module-level helper, e.g. `_game_placeholder(sys.platform)` returning the Windows example on `"win32"` and a generic hint ("The Sims 4 folder", `/path/to/the-sims-4`) elsewhere; call it once in `setup_ui`.
3. `main_window.py:122` — progress-bar font stack with a generic `sans-serif` fallback (`font-family:'Segoe UI','Noto Sans','Arial',sans-serif;`), or move font resolution into `theme.py`; keep the bar visually consistent with the dark palette.
4. `main_window.py:152` — `QFont` from `QFontDatabase.SystemFont.FixedFont` (or `QFont("monospace", 9)`); add `QFontDatabase` to the `PyQt6.QtGui` import at `main_window.py:6`.
5. `__main__.py:32` and `__main__.py:36` — neutral "already running" wording: "Check your system tray / notification area."
6. `docs/architecture.md` — nothing mandatory; optionally update the "Windows-only paths" note (`docs/architecture.md:241`) or §3 to mention the cross-platform UI-font / folder-default changes.
7. Tests (new `tests/test_ui_defaults.py` or extend an existing non-GUI test file):
   - Prefer testing pure helpers, not the window class (importing `main_window.py` works — PyQt6 is a dependency — but constructing widgets needs a `QApplication`, which should be avoided on headless CI). Factor the placeholder selection and browse-directory default into small module-level functions in `main_window.py` — e.g. `_browse_default_dir(path_text)` and `_game_placeholder(sys.platform)` — and unit-test those without instantiating the window, asserting:
     - `_browse_default_dir("")` returns `str(Path.home())` on any platform, and returns the given path when non-empty,
     - `_game_placeholder("win32")` returns the Windows example while `_game_placeholder("linux")` and `_game_placeholder("darwin")` return the generic hint.
   - For the font change, a test asserting `QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()` is reasonable is fine on the host, or skip GUI tests entirely and note that in the task.
   - Keep tests runnable on Linux CI headless (no `QApplication` needed); follow the plain `pytest`/`monkeypatch` style of `tests/test_config.py`.