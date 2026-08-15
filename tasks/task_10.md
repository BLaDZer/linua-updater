# Task 10 — Sync `docs/architecture.md` to post-fix reality

## How it works now

- `docs/architecture.md` documents **v4.3.0 as shipped**, including several Known Issues that the preceding tasks (01–09) either fix or change:
  - §4 `ParallelInstallManager` "downloads serially in the worker loop despite the parallel name" → fixed by task_01.
  - §10 "Dead/unwired code: `status_updated` and `download_detail` … `InstallWorker` has no `pause`/`resume`" → changed by task_03/task_09.
  - §10 "TLS verification is disabled (`verify=False`)" → changed by task_06.
  - §5 `DLCDatabase` "~150 DLC entries" and §4 multipart flow → corrected by task_07.
  - §7 config rows for `DownloadQueue`/`DownloadState` "wire is partial" → changed by task_03.
  - §8 build "console mode" → changed by task_09.
- The doc also documents behavior that task_02/04/05/08 alter (progress semantics, settings effectiveness, UI-thread network work, hardcoded endpoints/mirrors).

## How it should work

- `docs/architecture.md` reflects the **current** implementation after tasks 01–09: accurate class responsibilities, real data flow, corrected counts/fields, and an updated Known Issues section listing only genuinely remaining issues.
- Header metadata (version) updated to the release the doc describes; each section that changed carries a note or the change is reflected inline.

## What needs fixing

1. §1 Overview — refresh entry point/version references and the "~2500 lines" note if file length changes materially.
2. §2/§3 — describe threaded startup diagnostics (task_05) and correct signal/slot wiring (task_02/09).
3. §4 — `ParallelInstallManager` genuinely parallel (task_01); multipart flow as actually reachable or removed (task_07); pause/resume wiring (task_03).
4. §5 — `DLCDatabase` real entry count/fields and configurable endpoints (task_07/08).
5. §7 — persistence rows now accurate for `DownloadQueue`/`DownloadState` (task_03); config rows reflect honored settings (task_04).
6. §8 — build is windowed, no console (task_09).
7. §10 — Known Issues rewritten to the post-fix set (remaining items only); remove the fixed `verify=False`, dead-signal, and pause/resume notes.