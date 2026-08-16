# Task 30 — Complete Task 29 CI bundling: static-build aria2 on Linux and bundle 7-Zip

## Context

Task 29 added aria2 download steps to both CI workflows, but the fix is incomplete:

1. **Linux uses `apt-get install aria2`** (`linux_build.yml:26-30`) — the distro package is dynamically linked, so the bundled `aria2c` can pull in shared-library expectations at runtime. There is no official prebuilt Linux x64 aria2 binary in the `release-1.37.0` release (only Windows/Android builds); the `.tar.gz` URL from Task 29 is the **source** archive. We must build `aria2c` from that source on the Linux runner to get the pinned static-project build, mirroring how Windows gets the official prebuilt binary.
2. **7-Zip is never bundled.** The app uses 7-Zip for `.7z` and `.001` (split RAR) extraction (`installers.py:111-112,148,238-243` → `extractor.extract_7z`, `extractor.py:47-62`), but `build.spec` only bundles aria2 (`build.spec:20-23`) and `SevenZipFinder.find()` (`sevenzip.py:18-46`) never checks `sys._MEIPASS`, so even a bundled 7-Zip would not be found inside the one-file PyInstaller exe.

No zip packaging is wanted — tools are bundled **inside the one-file executable** via `a.binaries` and found through `sys._MEIPASS`.

## How it works now

- Linux CI: `sudo apt-get install -y aria2` then `cp "$(command -v aria2c)" tools/` — dynamic distro binary.
- Windows CI: downloads `aria2-1.37.0-win-64bit-build1.zip` and copies `aria2c.exe` to `tools/` — fine, keep as-is.
- `build.spec:20-23` adds `tools/aria2c` (or `.exe`) to `a.binaries` with destination `"."`, so at runtime the one-file bootloader extracts it to `sys._MEIPASS` and `Aria2Finder` (`aria2.py:26-31`, `_MEIPASS` first) finds it.
- `SevenZipFinder` (`sevenzip.py`) searches exe dir → `POSSIBLE_LOCATIONS` → `shutil.which` → manual PATH walk, but **not** `_MEIPASS`.
- 7-Zip binaries needed (full version — RAR support for `.001`): Linux `7zz` (standalone), Windows `7z.exe` **plus** `7z.dll` (7z.exe is a thin client over the DLL).

## What needs fixing

1. **`linux_build.yml`** — replace the apt step with a compile-from-source step for the source tarball the workflows already link:
   ```bash
   sudo apt-get update
   sudo apt-get install -y build-essential autoconf automake autopoint libtool pkg-config intltool gettext zlib1g-dev libssl-dev libc-ares-dev libxml2-dev
   wget -q https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0.tar.gz
   tar xzf aria2-1.37.0.tar.gz
   cd aria2-1.37.0
   ./configure --disable-shared --enable-static --without-libssh2
   make -j"$(nproc)"
   mkdir -p ../tools
   cp src/aria2c ../tools/aria2c
   cd ..
   ```
   Note: glibc cannot be fully static, so the result still links the runner's system libs (libc/openssl/libxml2) — this is expected and acceptable.
2. **7-Zip download steps** in both workflows (official 7-Zip 26.02, https://github.com/ip7z/7zip/releases):
   - Linux: download `7z2602-linux-x64.tar.xz`, extract (`tar -xJf`), locate the `7zz` file (layout varies by version — use `find`), `cp 7zz tools/7zz`.
   - Windows: download `7zr.exe` (standalone bootstrap) and `7z2602-extra.7z`, extract with `7zr.exe x ... -o<temp>` (no system 7-Zip needed), copy `x64/7z.exe` and `x64/7z.dll` to `tools\`.
3. **`build.spec`** — after the existing aria2 block, add 7-Zip to `a.binaries` using the same optional-if-present pattern:
   - Linux: `tools/7zz` → `"."`.
   - Windows: `tools/7z.exe` **and** `tools/7z.dll` → `"."` (both land side by side in `_MEIPASS`, so `7z.exe` finds the DLL).
   Local/dev builds without `tools/` must keep working (guarded by `os.path.exists`).
4. **`linua_updater/utils/sevenzip.py`** — prepend a `sys._MEIPASS` check to `find()` mirroring `Aria2Finder` (`aria2.py:26-31`), before the exe-dir scan:
   ```python
   meipass = getattr(sys, "_MEIPASS", None)
   if meipass:
       for name in self._executable_names():
           local = os.path.join(meipass, name)
           if os.path.exists(local):
               return local
   ```
   This lets the one-file exe resolve the bundled `7zz` (Linux) / `7z.exe` (Windows).

## 5. Tests

Add a unit test to `tests/test_sevenzip.py` mirroring `test_aria2.py:38-46` (`test_meipass_wins_over_path`): with `sys._MEIPASS` monkeypatched to a `tmp_path` containing a `7zz` file, `SevenZipFinder.find()` returns that file before any PATH/which lookup. Existing `tests/test_sevenzip.py` and `tests/test_aria2.py` tests must keep passing.

## 6. Docs

Update `README.md` (bundled binaries section) to list 7-Zip alongside `aria2c`. No release format or `version.json` changes — the raw single-file executable stays the only release asset.

## Verification

```bash
./scripts/check.sh
python -m pytest tests/test_sevenzip.py tests/test_aria2.py -v
```

CI bundling cannot be exercised locally; confirm on the next `v*.*.*` tag run that the one-file executable contains `aria2c` + `7zz` (Linux) or `aria2c.exe` + `7z.exe` + `7z.dll` (Windows) and that `Aria2Finder`/`SevenZipFinder` resolve them via `sys._MEIPASS`.