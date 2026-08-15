# Task 04 — Make Settings toggles take effect

## How it works now

- `SettingsDialog.get_settings()` (`:1173`) returns `max_threads`, `use_proxy`, `resume_downloads`, `cleanup_temp`.
- `show_settings` (`:2105`) saves them via `config.set("settings", ...)`.
- **Only `max_threads` is ever consumed**: `start_parallel_install` passes `self.settings.get('max_threads', 3)` into `InstallWorker` (`:2249`).
- The other three toggles are written to `config.json` but never read at runtime:
  - `resume_downloads`: ignore — `SingleDLCInstaller`/`MultiPartInstaller` call `download(..., resume=True)` unconditionally (`:925`, `:1002`).
  - `use_proxy`: ignore — proxy fallback in `SmartDownloader.download` (`:668`) runs whenever `diagnostics.working_proxies` is non-empty, without consulting the setting.
  - `cleanup_temp`: ignore — `finally` blocks always remove temp files (`:952`, `:1035`), and `DownloadQueue` is never cleaned.

## How it should work

- Each toggle behaves as its label promises:
  - **Resume interrupted downloads**: when unchecked, installs start fresh (no `Range` resume from `.part`, no `DownloadState` reuse).
  - **Use proxy if available**: when unchecked, `SmartDownloader` never tries the diagnostic proxies (direct + mirrors only).
  - **Clean temp files after install**: when unchecked, keep downloaded archives in the temp dir (for troubleshooting); when checked, current behavior (delete).
- Settings flow into `InstallWorker`, which passes them down to `SingleDLCInstaller`/`MultiPartInstaller`/`SmartDownloader`.
- Defaults stay as they are today (all checked / 3 threads).

## What needs fixing

1. Thread the settings dict from `LinuaUI.start_parallel_install` → `InstallWorker.__init__` → installers + downloader.
2. `SmartDownloader.download`/`_try_download_with_retry`: gate resume on the `resume_downloads` flag (skip loading/growth of `.part`, start at 0).
3. `SmartDownloader.download` proxy-fallback loop (`:668`): gate on `use_proxy`.
4. Temp-file cleanup in `SingleDLCInstaller.run` (`:952`) and `MultiPartInstaller.run` (`:1035`) `finally` blocks: gate on `cleanup_temp`.
5. Update `docs/architecture.md` §7 (`config.json` row) to reflect that all settings are now honored (or update §10 if any remain cosmetic).