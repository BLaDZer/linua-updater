# Task 42 — Generalize `HTTPClient` and migrate raw `requests` consumers

## Context

`HTTPClient` (`linua_updater/core/clients.py`) was extracted in task 41 as a low-level transport for `SmartDownloader`. Today its public surface is download-shaped: only `get_stream(url, start_byte=0)` (streaming `GET` + `Range` resume) plus `set_proxy`. It is not usable for the app's other network activity, which still calls `requests` directly:

- `DLCDatabase._download` — `requests.get` (`core/database.py:110`)
- `UpdateChecker.check_for_updates` — `requests.get` (`workers/update_checker.py:80`)
- `NetworkDiagnostics` — `requests.get` ×2 and `requests.head` (`core/diagnostics.py:48,60,68`)

These three duplicate "create session, set UA, accept a timeout/verify/proxies" logic that `HTTPClient` already owns. This task makes `HTTPClient` a generic reusable transport and migrates all three consumers to it.

## How it works now

- `HTTPClient.__init__` (`clients.py:14-23`) creates a session, sets `User-Agent: Linua-Updater/<APP_VERSION>`.
- `set_proxy` (`clients.py:25-29`) mutates `session.proxies`.
- `get_stream` (`clients.py:31-35`) is the only request method; it builds a `Range` header from `start_byte` and calls `session.get(..., stream=True, timeout=..., verify=...)`.
- `SmartDownloader._try_download` (`core/downloader.py:198`) is the only `HTTPClient` caller: `with self.client.get_stream(url, start_byte=start_byte) as response:`.
- `database.py`, `update_checker.py`, `diagnostics.py` construct their own `requests.get`/`head` calls with module-level constants (`HTTP_TIMEOUT_SEC`, `REGION_TIMEOUT_SEC`).

## How it should work

`HTTPClient` exposes generic verbs alongside the download convenience, with token overrides per call:

```python
class HTTPClient:
    def __init__(self, timeout=DEFAULT_DOWNLOAD_TIMEOUT_SEC, verify=True, session=None): ...
    def set_proxy(self, proxy_dict=None): ...

    def get(self, url, *, params=None, headers=None, timeout=None, verify=None, proxies=None, stream=False): ...
    def head(self, url, *, params=None, headers=None, allow_redirects=True, timeout=None, verify=None, proxies=None): ...
    def post(self, url, *, params=None, data=None, json=None, headers=None, timeout=None, verify=None, proxies=None): ...

    def get_stream(self, url, start_byte=0, **kwargs):
        # dict(kwargs.pop("headers") or {}) + Range header when start_byte > 0,
        # then delegates to self.get(..., stream=True, **kwargs)
```

Resolution rules:
- `timeout=None` → instance `self.timeout`; `verify=None` → instance `self.verify` (explicit `False`/`True` per call respected).
- `proxies=None` → pass through untouched; `requests` falls back to `session.proxies` (so `set_proxy` still works for every verb).
- All verbs return `requests.Response`; no auto raise/no status policy — caller decides (same as today).
- Exceptions (`requests.exceptions.Timeout`, `ConnectionError`, …) propagate unchanged.

Consumers delegate: `DLCDatabase`, `UpdateChecker`, `NetworkDiagnostics` each accept `client: Optional[HTTPClient] = None` (default `HTTPClient()`), call `self.client.get/head` with the same URL/timeout/verify/proxies they pass to `requests` today, and keep their existing status-code handling. `SmartDownloader` behavior is byte-for-byte identical (`get_stream` signature unchanged).

## What needs fixing

1. `core/clients.py`: add `get`/`head`/`post` (keyword-only args, per-call overrides as above); re-implement `get_stream` on `get(stream=True)`. Keep constructor and `set_proxy` signatures.
2. `core/database.py`: add `client` param to `DLCDatabase.__init__` (`:45`, store `self.client`); `_download` (`:110`) → `self.client.get(self.db_url, timeout=HTTP_TIMEOUT_SEC)`; remove now-unused `import requests` (`:7`).
3. `workers/update_checker.py`: add `client` param to `UpdateChecker.__init__` (`:25`); `check_for_updates` (`:80`) → `self.client.get(self.version_url, timeout=HTTP_TIMEOUT_SEC)`; **keep** `import requests` (`:5`) — `except requests.exceptions.Timeout/ConnectionError` remain.
4. `core/diagnostics.py`: add `client` param to `NetworkDiagnostics.__init__` (`:30`); `detect_region` (`:48`) → `self.client.get(self.region_api, timeout=REGION_TIMEOUT_SEC)`; `test_connection` (`:60`) → `self.client.head(url, timeout=timeout, allow_redirects=True)`; `test_proxy` (`:68`) → `self.client.get(GITHUB_URL, proxies=proxy_dict, timeout=HTTP_TIMEOUT_SEC, verify=True)`; remove `import requests` (no other use).
5. No behavior changes in any consumer: same URLs, timeouts, proxies, status-code checks, return values, error messages.

## Tests

- `tests/test_clients.py`: extend `FakeSession` with `head`/`post` (record calls + return `FakeResponse`). Existing UA/`set_proxy`/`get_stream` tests must keep passing unchanged. Add: generic `get` sends `params`/`headers`/`stream`; per-call `timeout`/`verify` override the instance defaults only when passed; `proxies` passed through when given; `head` forwards `allow_redirects`; `post` forwards `data`/`json`; `get_stream` passes extra kwargs to `get` and still emits `Range` only for `start_byte > 0`.
- `tests/test_database.py`: replace the `"linua_updater.core.database.requests.get"` monkeypatches (`:42`, `:109`, `:141`, `:153`, `:192`, `:219`, `:247`) with injecting a fake client. Update `isolated_db_env` (`:39-42`) to build `DLCDatabase(client=FakeHTTPClient(404))`; recording assertions (`calls == []`, `calls == [db.db_url]`) use a recording fake.
- `tests/test_update_checker.py`: replace `requests.get` monkeypatches (`:61,73,85,97,109,129,150`) with injecting a fake client; Timeout/ConnectionError cases make the fake raise the corresponding `requests.exceptions` so the except-clauses still fire.
- `tests/test_diagnostics.py`: replace `monkeypatch.setattr(diag_mod, "requests", fake)` (`:38,46,54,60,66,74,86,105,124`) with a queue-based fake HTTPClient (ordered responses, can raise `Exception`), injected as `client=` into `NetworkDiagnostics`. Preserve the ordering-sensitive `test_diagnose_*` scenarios.
- `tests/test_downloader.py`: unchanged — file works without edits; run to confirm `get_stream` compat.
- Run `./scripts/check.sh` (ruff + pytest + mypy). Mind `pyproject.toml`: `line-length = 160`; keywords must use typed generics (`Optional[Dict[str, str]]`, not bare `Dict`).

## Docs

- `docs/architecture.md`: `HTTPClient` row — note it is the generic transport now used by `SmartDownloader`, `DLCDatabase` and `NetworkDiagnostics`, not just the downloader.
- `tasks/refactoring-plan.md` already maps `HTTPClient` → `core/clients.py` (no change needed).