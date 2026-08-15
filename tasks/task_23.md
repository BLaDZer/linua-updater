# Task 23 — Validate single-file DLC downloads against all available checksums (installers.py)

## How it works now

- `SingleDLCInstaller.run()` (`linua_updater/core/installers.py:26-73`) verifies a downloaded archive by **size only**: the temp file must exist (`installers.py:46`), not be empty (`installers.py:49`) and be at least 1024 bytes (`installers.py:51`). Content integrity is never checked; the file goes straight to `extract_zip` (`installers.py:54`).
- `MultiPartInstaller.run()` does the same per part (`installers.py:129-134`).
- Some catalogue entries already carry checksum data, e.g. `EP06` in `linua_updater/core/database.py:29-33`:
  ```python
  "checksum": {
      "sha256": "6ca5aae51994b388c0c1754b35a796b0aa2a70134d7d19cff3ad2d7c5e39f76b",
      "sha1":   "cdd5c4ebe754780e7bdf9bbadac040744d933b91",
      "md5":    "a6a32c44748cb864f95395060f02373b"
  }
  ```
  This dict is never read, so a corrupted-but-right-sized download passes and is extracted.

## How it should work

- When a DLC entry carries a `checksum` dict, **every** present variant from the supported set `md5`, `sha1`, `sha256` must be validated against the downloaded temp file **before extraction**. If several variants are present, all of them are checked.
- Entries with no `checksum` key, an empty dict, unknown algorithm keys, or empty/whitespace variant values are skipped silently — existing DLC and existing tests keep working.
- Any mismatch **aborts the install**: each failed variant is written to the app console via `self.log(...)` (which `ImprovedLogger.log`, `logging_util.py:47-76`, renders amber in the console widget), the failure is recorded in `stats` (`InstallationStats.record_error`, `linua_updater/core/models.py:26-28`), and `run()` returns `(False, message)` — the archive is not extracted.
- `MultiPartInstaller` stays size-only for now. Its `EP06` checksum block sits at the DLC level while the download is split across 7z volumes, so verifying it would need a per-part checksum schema; that is explicitly deferred (see note below).

## What needs fixing

1. New module `linua_updater/core/checksum.py`:
   - `SUPPORTED_CHECKSUMS = ("sha256", "sha1", "md5")` (order matters for deterministic output).
   - Pure helper `verify_file_checksums(file_path, checksums) -> list[str]`:
     - `checksums` is the `info["checksum"]` dict; `None`/empty → returns `[]`.
     - Only inspect keys in `SUPPORTED_CHECKSUMS` whose value is non-empty after `strip()`; anything else (unknown algorithm, empty value) is ignored.
     - Stream the file in ~1 MB chunks through the matching `hashlib.new(alg)` for every checked variant in one pass, compare hex digests case-insensitively.
     - Returns a list of error strings, empty list = OK; format `Checksum mismatch ({alg}): expected {expected}, got {actual}`.
     - Missing/unreadable file → a single error entry, e.g. `Checksum verification failed: file not found` (no partial variant results).
2. `SingleDLCInstaller.run()` (`linua_updater/core/installers.py`) — after the too-small check (`installers.py:52`) and **before** `self.log("Extracting...")` (`installers.py:53`):
   - `errors = verify_file_checksums(temp, self.info.get("checksum"))`;
   - if `errors`: log each entry with `self.log(error, "WARNING")`, `self.stats.record_error(self.dlc, "; ".join(errors))` and `return False, "; ".join(errors)`;
   - otherwise continue to extraction unchanged.
3. Tests:
   - New `tests/test_checksum.py` (headless, pure helper, `tmp_path`):
     - `verify_file_checksums(path, None)` and `verify_file_checksums(path, {})` → `[]`;
     - one correct checksum → `[]`; one wrong checksum → exactly one error naming the algorithm and both hashes;
     - all three of `sha256`/`sha1`/`md5` correct → `[]`; when only one of several is wrong, the error list contains that variant only;
     - empty/whitespace value (e.g. `{"md5": "   "}`) and unknown key (e.g. `{"crc32": "..."}`) → skipped → `[]`;
     - missing file → non-empty error.
   - `tests/test_installers.py` additions (reuse `StubDownloader`, which writes raw payload bytes at `tests/test_installers.py:26-33`, and `_single` at `tests/test_installers.py:66-68`):
     - `test_single_checksum_failure_records_error` — payload bytes whose digest differs from the expected value in `info["checksum"]` → `run()` returns `(False, message)` with `Checksum mismatch` in the message, `stats.errors` has exactly one entry, and the extractor's `extract_zip` was never called;
     - `test_single_checksum_success` — payload whose digest matches → `(True, "OK")`, extraction called, `stats.errors == []`.
     - Existing size-only tests must remain valid and unchanged — none of their `info` dicts carry `checksum`, so they now exercise the skip path.

Note: the `EP06` entry in `database.py` currently uses `mirrors[0].type == "parts"` while the installer reads `info["parts"]` — a pre-existing schema inconsistency, out of scope here. A follow-up task should introduce a per-part checksum schema (or a DLC-level checksum over concatenated volumes) before enabling verification for `MultiPartInstaller`.
