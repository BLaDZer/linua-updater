# Task 38 — Remove redundant multipart download log lines

## Context

Multipart (parts) installs log noisy, duplicate lines:

```
[20:24:38] EP06: Downloading EP06: 7 parts from: https://.../EP06.7z.001, https://.../EP06.7z.002, ...  <-- full URL list
[20:24:38] Downloading EP06 Part 1 from https://.../EP06.7z.001                                        <-- keep
[20:24:38] Downloaded EP06 Part 1 (1.0 MB)                                                             <-- keep
[20:24:38] EP06: Part 1/7 downloaded (1.0 MB)                                                          <-- redundant
```

The user only wants to see `Downloading {dlc}: {N} parts` (no `from: url1, url2, ...` suffix) and the
`Downloading ... Part N from URL` / `Downloaded ... Part N (X MB)` lines produced by the downloader.
The `Part N/M downloaded` line duplicates what the downloader already logs, so it should be dropped.

## How it works now

`linua_updater/core/installers.py`:

- `installers.py:117` logs `Downloading {dlc}: {total_parts} parts from: {', '.join(parts)}` — dumps every
  part URL onto one line.
- `installers.py:145` logs `Part {i+1}/{total_parts} downloaded ({size} MB)` — fires right after each part
  download completes.

The downloader already produces the useful lines itself:

- `downloader.py:70` → `Downloading {name} from {url}`
- `downloader.py:64` → `Downloaded {name} ({size} MB)`

## How it should work

- The "Downloading ... parts" line reads exactly `EP06: Downloading EP06: 7 parts` — no `from: ` URL list.
- No `Part N/M downloaded` line — each part's completion is covered by the downloader's
  `Downloaded EP06 Part N (X MB)` line.

## What needs fixing

`linua_updater/core/installers.py`:

1. `:117` → `self.log(f"Downloading {self.dlc}: {total_parts} parts")`
2. Delete `:145` (`self.log(f"Part {i+1}/{total_parts} downloaded (...")`) entirely.

## Not in scope

- Downloader/progress-bar behavior or formatting.
- Failure and extraction log lines.

## Tests

`tests/test_installers.py` — update `test_multipart_logs_source_and_part_progress` (line 247):

- Replace the line 259 assertion (`all(part in t for t ...) and "parts from" in t`) with one that asserts a
  log line equals `Downloading MP01: 2 parts` and contains no URL/`parts from`.
- Remove the `Part 1/2 downloaded` and `Part 2/2 downloaded` assertions (lines 260–261).

## Docs

No `docs/architecture.md` change needed — behavior is log-message-only.

## Verification

```bash
python -m pytest tests/test_installers.py -v
./scripts/check.sh   # pytest + ruff
```

Manual smoke: install a multipart DLC and confirm the log shows `Downloading EP06: 7 parts` without a URL
list, and per-part completion appears only once (as `Downloaded EP06 Part N (X MB)`).