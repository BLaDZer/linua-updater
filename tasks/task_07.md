# Task 07 — Align catalog with dead `size` / `parts` lookups

## How it works now

- `DLCDatabase.dlc` (`:1434`) contains **109 entries** (not ~150 as the doc claims), each shaped `{"name": ..., "url": ...}`.
- **No entry has `size` or `parts` fields.**
- Two code paths look for these fields that are therefore dead:
  - `DiskSpaceChecker.get_dlc_size` (`:1288`): "Try to get exact size from database first" — `info['size']` is never present (`:1293`), so every estimate comes from the static fallback table `DLC_SIZES` (largely made-up numbers, `:1220`).
  - `InstallWorker.run` (`:1091`): routes to `MultiPartInstaller` only when `info["parts"]` is truthy — never the case — so **`MultiPartInstaller` is unreachable in practice** despite `docs/architecture.md` §4 documenting "some DLC define `parts[]`".
- `docs/architecture.md` §4 and §10 describe a multipart/7-Zip flow ("requires 7-Zip") that cannot trigger with the current catalog.

## How it should work

- The catalog and the code agree. Either:
  - **Preferred:** enrich the 109 entries with real `size` (bytes) and, where applicable, `parts[]` URLs — so `DiskSpaceChecker` gives honest space estimates and the multipart flow (`.7z.001/002…` via 7-Zip) can actually run; or
  - If multipart is not used by the current distribution, remove the `parts` routing and `MultiPartInstaller` assumptions from the doc and code paths to avoid the misleading "some DLC are multipart" claim.
- `DiskSpaceChecker` stops relying on hardcoded guesses: DB `size` wins, static table is the fallback only for genuinely unknown ids, default 500 MB removed or made explicit.
- `size` / `expected_size` from the DB is actually used to validate downloads (see task_06), not just for the space dialog.

## What needs fixing

1. Decide the catalog posture (multipart used or not) and apply consistently.
2. `DLCDatabase` — add `size` to entries (real values, fix the "Known from database" decoys at `:1223`, `:1226`, `:1241` if they do not match the DB).
3. `DLCDatabase` — add `parts[]` to any genuinely multipart DLC; otherwise remove the `parts` check in `InstallWorker.run` and any doc references.
4. `DiskSpaceChecker.DLC_SIZES` (`:1220`) — clean up erroneous/misplaced comments and entries (e.g. GP entries listed under kit ranges, GP10/GP11 duplicating EP names).
5. `Extractor`/`MultiPartInstaller` — only exercised if multipart entries exist; verify 7-Zip find → extract on a real multipart archive.
6. Update `docs/architecture.md` §4 (`DLCDatabase` row: correct count & fields) and §5.