# Task 15 — Cross-platform game detection (core/detection.py)

## How it works now

- `GameDetector.find_from_registry()` (`linua_updater/core/detection.py:6-28`) queries Windows Registry keys (Maxis/EA Games "Install Dir" values) via `winreg`. The whole body is wrapped in `try/except`, so on Linux/macOS the `import winreg` on `detection.py:8` raises and the method degrades to `return []` (detection.py:27-28) without crashing. That fallback is acceptable and should stay Windows-only.
- `GameDetector.find_game()` (`detection.py:31-58`):
  - validates the registry-returned paths only against the Windows exe `Game\Bin\TS4_x64.exe` (`detection.py:35`);
  - scans hardcoded drive letters C–H (`detection.py:38`) joined with hardcoded Windows subpaths (`detection.py:39-50`: `\Program Files (x86)\Steam\steamapps\common\The Sims 4`, `\SteamLibrary\...`, `\Origin Games\...`, etc.);
  - returns `found_paths[0]` or `None` (`detection.py:58`).
- On Linux/macOS there is no C:-style drive scan and no Steam library-folder awareness, so Auto Detect always fails ("Game not found. Please select manually", `main_window.py:285`) even though The Sims 4 is commonly installed via Steam on Linux (Native or Proton) and through Steam on macOS.

## How it should work

- Windows behavior is unchanged: registry + C–H drive scan.
- On Linux/macOS, add Steam library-folder detection:
  - Parse the Steam `libraryfolders.vdf` file at the standard locations:
    - Linux: `~/.local/share/Steam/steamapps/libraryfolders.vdf` (also `~/.steam/steam/steamapps/libraryfolders.vdf`).
    - macOS: `~/Library/Application Support/Steam/steamapps/libraryfolders.vdf`.
  - `libraryfolders.vdf` is a Valve KeyValues file with entries like `"1" "path" "D:\\SteamLibrary"` and `"path" "..."`; parse the `"path"` values. Avoid importing a heavy dependency — a small regex or a tiny hand-rolled parser keyed on lines starting with `"path"` is fine. Note the file legitimately contains an entry at the very top with `"path" "..."` pointing at the default `Steam` folder — that folder must be treated the same as any library folder, not skipped.
  - For each library folder path, check `<lib>/steamapps/common/The Sims 4` and validate `Game/Bin/TS4_x64.exe`. For Proton installs the exe lives inside a compatdata prefix (`compatdata/<appid>/pfx/drive_c/...`), so validation should be best-effort: accept the folder if `Game` exists and the `.exe` resolves anywhere under the prefix, while keeping the primary check the plain `<lib>/steamapps/common/The Sims 4` folder containing `Game/Bin`.
  - Keep a set of well-known relative guesses under the home dir (best-effort).
- Skip the hardcoded drive-letter scan entirely when `sys.platform != "win32"`.
- Return the same contract: `found_paths[0]` or `None` (`detection.py:58`).

## What needs fixing

1. `detection.py:6-28` — keep the registry lookup Windows-only; make the platform guard explicit with `if sys.platform != "win32": return []` at the top (the behavior is already implicit via the `try/except` on the `winreg` import at `detection.py:8`), so the method is self-documenting and reads clearly.
2. `detection.py:38-57` — wrap the drive scan in `if sys.platform == "win32":` so Linux/macOS skip it; extract the exe validation `Game / Bin / TS4_x64.exe` (`detection.py:35` and `detection.py:55-56`) into a small shared helper used by both the Windows paths and the new POSIX Steam scan.
3. Add `find_from_steam()` (or fold the logic into `find_game()`) that:
   - computes candidate vdf locations per platform (Linux: `~/.local/share/Steam/steamapps/libraryfolders.vdf`, `~/.steam/steam/steamapps/libraryfolders.vdf`; macOS: `~/Library/Application Support/Steam/steamapps/libraryfolders.vdf`);
   - parses `"path"` values with a tiny regex, e.g. `rb'"path"\s+"([^"]+)"'` on each line;
   - checks `<lib>/steamapps/common/The Sims 4` and validates the executable (including the Proton compatdata best-effort check);
   - returns any found paths (list).
4. `find_game()` — combine registry + win32 drive scan + Steam scan, dedupe results, and return the first or `None`.
5. `docs/architecture.md:130` — update the `GameDetector` row in section 5 to mention Steam library-folder scanning on Linux/macOS alongside the existing Registry/drive scanning on Windows. `docs/architecture.md:241` stays accurate for the noted win32 items but wording may need adjusting if it implies the whole app is Windows-only.
6. Add tests in `tests/test_detection.py`:
   - `find_from_steam` parses a temp `libraryfolders.vdf` written with two libraries (one default-`path`, one custom) and returns the valid Sims 4 folder — create a real `tmp_path/steamapps/common/The Sims 4/Game/Bin/TS4_x64.exe` file for the valid one and an empty folder for the invalid one.
   - Monkeypatch `Path.home()`/env to point at the tmp tree on POSIX, and guard the whole test so it runs on any platform (construct the expected locations via the same logic the code uses).
   - `find_game()` skips the drive scan off-win32 (patch `sys.platform` to `"linux"` and assert no `C:\`-style exe tests happen — e.g. via a monkeypatched `os.path.exists` recorder).
   - Registry path still returns `[]` with `sys.platform` mocked to `"linux"` (no `winreg` import attempted).
   - Keep tests deterministic and runnable on Linux CI.