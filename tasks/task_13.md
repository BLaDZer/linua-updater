# Task 13 — Cross-platform admin check, protected-path detection, and elevation (utils/admin.py)

## How it works now

- `AdminElevator.is_admin()` (`linua_updater/utils/admin.py:8-12`) calls `ctypes.windll.shell32.IsUserAnAdmin()`. On Linux/macOS `ctypes.windll` does not exist, so the bare `except:` swallows the `AttributeError` and returns `False` — meaning the UI always assumes the user is not elevated on POSIX even when running as root.
- `AdminElevator.requires_admin(path)` (`admin.py:15-29`) first matches a hardcoded lowercase Windows-path list only (`admin.py:19`: `c:\program files`, `c:\program files (x86)`, `c:\windows`, `c:\programdata`), then falls back to a write test (`admin.py:23-27`) that touches `path/.linua_write_test`. On POSIX, protected locations such as `/usr/games`, `/opt`, or `/etc` are not matched by the string list, so detection relies entirely on the write test.
- The string match itself is sloppy: the whole path is lowercased and matched with a bare prefix `startswith` (`admin.py:21`), which wrongly matches e.g. `C:\program files_whatever`, and uses raw `\`-style literals without any drive normalization.
- `AdminElevator.elevate()` (`admin.py:31-48`) uses `ctypes.windll.shell32.ShellExecuteW(None, "runas", ...)` to relaunch elevated and then `sys.exit(0)` on success (`admin.py:42-44`). No POSIX equivalent exists, so on Linux/macOS elevation silently fails: the `ShellExecuteW` call itself raises, is caught at `admin.py:46`, and `None` is returned as a truthy non-bool — installing DLC into a non-writable folder is therefore impossible.
- Callers: `main_window.py:326-337` (`on_update`) checks `AdminElevator.requires_admin(path)` then `AdminElevator.is_admin()`, shows a confirm dialog, and calls `AdminElevator.elevate()` (`main_window.py:332`); `__main__.py` uses elevation only indirectly. No other module relies on the return types of these methods.

## How it should work

- `is_admin()`:
  - Windows: keep `ctypes.windll.shell32.IsUserAnAdmin()`.
  - POSIX: `os.geteuid() == 0` (Linux/macOS). The module-level `import ctypes` stays safe on all platforms, but the `ctypes.windll` access must only happen under `sys.platform == "win32"` (keep the guard so importing the module on any OS never raises).
- `requires_admin(path)`:
  - Treat the write test as the single source of truth — it is already cross-platform and is the actual capability check. Improve it: use a unique temp filename, use `os.path.join(path, tempname)`, still touch + unlink, and guarantee cleanup in a `finally`.
  - Keep the Windows-path prefix list only as a fast-path to avoid needless `ShellExecuteW` prompts, but fix the matching to compare the drive-normalized path only under `sys.platform == "win32"` using `os.path.normcase`, and add POSIX protected prefixes (`/usr`, `/opt`, `/etc`, `/var`) so the heuristic is honest on Linux/macOS even though the write test remains primary.
- `elevate()`:
  - Windows: unchanged `ShellExecuteW(..., "runas", ...)` with `sys.exit(0)` when `ret > 32`.
  - Linux: relaunch via `pkexec` (polkit) when available, else `sudo -A` or `gksudo`, passing the current interpreter (`sys.executable`) and the original `sys.argv` (handling both frozen and non-frozen the way the current code does at `admin.py:34-41`); on success (`sys.exit(0)`), otherwise return `False`.
  - macOS: relaunch via `osascript -e 'do shell script "..." with administrator privileges'`, quoting `sys.argv` safely.
  - All branches keep the `(bool, reason)`-friendly behavior: the method still returns `False` on failure paths so the `main_window.py:332` call site (just calls elevate then returns) continues to work unchanged.
- The `main_window.py` flow at `main_window.py:326-337` stays as-is; no call site changes and no signature changes.

## What needs fixing

1. `admin.py:10` — gate the `ctypes.windll` call behind `sys.platform == "win32"`; add a POSIX branch using `os.geteuid() == 0` (import `os`).
2. `admin.py:19` — normalize with `os.path.normcase` under win32 only (avoid the lowercase-drive string hacks); keep the string list as a win32-only fast path, and add a POSIX prefix list (`/usr`, `/opt`, `/etc`, `/var`).
3. `admin.py:23-27` — the write test uses a unique temp filename, `os.path.join(path, tempname)`, and cleanup in a `finally`.
4. `admin.py:31-48` — add POSIX elevation branches (pkexec / sudo / osascript); keep the Windows branch; non-frozen launches must pass `sys.argv` correctly and frozen must pass `sys.executable`.
5. `docs/architecture.md` §6 (line 142 `AdminElevator` row) — update the description to mention pkexec/sudo/osascript alongside `IsUserAnAdmin`/`ShellExecuteW`.
6. Add tests (extend an existing test file or add `tests/test_admin.py`, mirroring the `tmp_path`/`monkeypatch` style of `tests/test_config.py:7-11`):
   - `is_admin()` returns a bool on the current host without raising on any platform.
   - `requires_admin` against a writable `tmp_path` returns `False`, and against a "protected" non-writable scenario returns `True` (simulate by making the touch fail via monkeypatched `Path.touch`/`os` calls, or run only the string-match branch).
   - The Windows string-match branch is unit-tested in isolation by calling a helper with a fake `c:\program files\...` input, validating the `os.path.normcase` fix.
   - `elevate()` never raises on the current host (monkeypatch away `ctypes.windll` / the subprocess callables) and returns `False` gracefully when no elevation is possible.
7. Call sites are unaffected: `main_window.py:326-337` keeps the same `requires_admin` / `is_admin` / `elevate` sequence with no signature changes.