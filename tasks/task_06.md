# Task 06 — Harden extraction & TLS

## How it works now

- Every HTTP request in `SmartDownloader` uses `verify=False` (`:710`), i.e. **TLS certificate verification is disabled** — all traffic (including downloads from the third-party Cloudflare Workers CDN `penis.nicole-popova66.workers.dev`) is unauthenticated.
- `NetworkDiagnostics.test_proxy` also uses `verify=False` (`:582`).
- `Extractor.extract_zip` (`:828`) uses `z.extract(member, out_dir)` (`:839`). `zipfile.extract()` follows archive member paths **without sanitization**: a malicious/modified archive member like `../../Windows/evil` or an absolute path can write outside `out_dir` (Zip Slip).
- These together mean: untrusted, unverified downloads are unpacked directly into the user's game folder with path-traversal capability.

## How it should work

- TLS verification is enabled (`verify=True`) for all endpoints; if a specific endpoint genuinely needs an exception, it is scoped, logged, and documented rather than global.
- ZIP extraction sanitizes every member path: strip leading `/`, reject `..` components and absolute paths, join under a resolved root, and only write inside `out_dir` (or use `shutil`-based copying for full control).
- Behavior on a malicious/bad archive: extraction fails with a clear message and the temp archive is removed (existing cleanup already handles temp removal).
- The download-size validation (≥1 KB at `:935`) still runs; `expected_size` validation should also be tightened (see task_07) so size mismatches abort before extraction.

## What needs fixing

1. `SmartDownloader._try_download` (`:704`) — change `verify=False` → `verify=True` (default). Test that all current endpoints (`workers.dev`, GitHub raw, mirrors) serve valid certs; if the proxy fallback (SOCKS) needs `verify=False`, keep it isolated there with a comment.
2. `NetworkDiagnostics.test_proxy` (`:582`) — same `verify=True` change.
3. `Extractor.extract_zip` (`:828`) — replace `z.extract(member, out_dir)` with a sanitizing extraction: resolve `out_dir` with `os.path.abspath`, reject `..`/absolute member paths, extract via `open(member, 'w')` inside the resolved root only.
4. Add a regression check: `testzip()` already runs (`:834`); ensure the path guard can't be bypassed by backslashes on Windows or by `os.path.normpath` tricks.
5. Update `docs/architecture.md` §10 Known Issues — remove/rewrite the "TLS verification is disabled" note to reflect the hardened posture.