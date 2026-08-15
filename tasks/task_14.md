# Task 14 — Cross-platform 7-Zip detection (utils/sevenzip.py)

## How it works now

- `SevenZipFinder` (`linua_updater/utils/sevenzip.py`) searches only Windows artifacts:
  - `POSSIBLE_LOCATIONS` (`sevenzip.py:7`) lists `7z.exe`, `7za.exe`, and `C:\Program Files\7-Zip\...` / `C:\Program Files (x86)\7-Zip\...`.
  - step 1 looks for `7z.exe` next to the running executable (`sevenzip.py:15`).
  - step 3 shells out to `where 7z` on win32 / `which 7z` elsewhere (`sevenzip.py:26-29`) — on POSIX this only finds the plain `7z`, never the `7zz`/`7za` variants.
  - step 4 manually walks `PATH` but only checks `7z.exe`/`7za.exe` (`sevenzip.py:41`), so a Linux install with `7z`/`7zz` on PATH is never found.
- On Linux a typical install (p7zip `/usr/bin/7z`, newer 7-Zip `7zz` in `/usr/bin` or `/snap/bin/7z`, macOS Homebrew `$(brew --prefix)/opt/p7zip/bin/7z`) is therefore never detected, so `MultiPartInstaller` reports "7z.exe not found".
- Error messages are Windows-centric wording: `extractor.py:50` returns `"7z.exe not found"` and `installers.py:102` returns `"7z.exe not found"`.

## How it should work

- Detect the 7-Zip executable name per platform: `7z.exe`, `7za.exe` on Windows; `7z`, `7za`, `7zz` on Linux/macOS.
- Replace the manual `where`/`which` subprocess hack (`sevenzip.py:26-29`) with `shutil.which(name)` loop across the per-platform name list — simpler and cross-platform.
- Keep the same-exe-dir scan but use the per-platform names (look for `7z.exe`/`7za.exe` next to `sys.argv[0]` on Windows, `7z`/`7zz`/`7za` on POSIX peers).
- Add POSIX locations to `POSSIBLE_LOCATIONS`: `/usr/bin/7z` and `/usr/bin/7za`, `/usr/bin/7zz`, `/usr/local/bin/7z`, `/snap/bin/7z`; on macOS optionally evaluate `$(brew --prefix)/opt/p7zip/bin/7z` via `shutil.which` and/or common paths.
- The manual PATH walk (`sevenzip.py:38-45`) should iterate the per-platform name list too.
- Log/return messages become platform-neutral: "7-Zip not found. Install 7-Zip from https://www.7-zip.org/ and make sure the binary is on PATH".
- Update `extractor.py:50` and `installers.py:102` messages from `"7z.exe not found"` to `"7-Zip not found"` so Windows-centric naming doesn't leak into user-visible text on POSIX.
- `workers/install_worker.py:95-100` call site is unchanged (`seven_finder.find()` returns a path string).

## What needs fixing

1. `sevenzip.py:7` — per-platform `POSSIBLE_LOCATIONS` (keep Windows entries; add POSIX entries listed above).
2. `sevenzip.py:15` — same-exe-dir scan uses per-platform names.
3. `sevenzip.py:26-29` — replace the `where`/`which` subprocess with `shutil.which` over a name list; drop the now-unneeded `subprocess` import if nothing else uses it (verify — the module may keep `subprocess` for other steps; if fully unused, drop it).
4. `sevenzip.py:41` — PATH walk uses per-platform names.
5. `sevenzip.py:48` — neutral "7-Zip not found" message.
6. `extractor.py:50` and `installers.py:102` — replace `"7z.exe not found"` with `"7-Zip not found"`.
7. `docs/architecture.md` §6 (line 143) — update `SevenZipFinder` description to "locates 7-Zip across common OS paths and PATH (7z/7zz on POSIX, 7z.exe on Windows)".
8. Add tests (new `tests/test_sevenzip.py` or extend existing):
   - With `sys.platform` monkeypatched to `"win32"`, `shutil.which` monkeypatched to return a path for `7z.exe`, assert `find()` returns it.
   - On POSIX (`sys.platform` != win32), monkeypatch `shutil.which` for `7z`/`7zz` and assert detection; and assert a fake `POSSIBLE_LOCATIONS`/exe-dir entry wins.
   - Ensure `find()` returns None (and logs once) when nothing is found so the installer's "7-Zip not found" path at `install_worker.py:98-99` triggers.
   - Use `monkeypatch.setattr(sys, "platform", "win32")` style; keep tests runnable on Linux CI.