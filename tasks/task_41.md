# Task 41 — Split `SmartDownloader` into `SmartDownloader` + `HTTPClient`

## Context

`SmartDownloader` (`linua_updater/core/downloader.py`) mixes two concerns:
1. **Low-level HTTP transport** — owns `requests.Session`, the `User-Agent` header, proxy assignment, and the streaming `GET` (Range resume, timeout, verify).
2. **High-level orchestration** — retry-with-backoff, proxy/mirror fallback, `.part` resume bookkeeping, pause/resume/cancel state machine, slow-speed abort, size checks, progress callbacks, lifecycle logging.

Split the transport into a reusable `HTTPClient` in new module `linua_updater/core/clients.py`. `SmartDownloader` keeps orchestration and delegates HTTP to it.

## How it works now

- `__init__` (`downloader.py:34-60`) creates `self.session = requests.Session()` and sets `User-Agent` (`:50-51`).
- `set_proxy` (`:65-69`) mutates `self.session.proxies` directly.
- `_try_download` (`:192-276`) is the only HTTP call site: builds `Range` headers, `self.session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT_SEC, verify=True, headers=headers)` (`:205`), then iterates chunks with pause/cancel/speed/progress and writes the `.part` file.
- Nothing outside `downloader.py` touches `.session`/`set_proxy`; consumers (`main_window.py`, `install_worker.py`, `installers.py`) only use `set_progress_callback`/`cancel`/`pause`/`resume`/`download`.

## How it should work

`linua_updater/core/clients.py`:

```python
class HTTPClient:
    def __init__(
        self,
        timeout: int = DOWNLOAD_TIMEOUT_SEC,
        verify: bool = True,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = timeout
        self.verify = verify
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "Linua-Updater/" + APP_VERSION})

    def set_proxy(self, proxy_dict: Optional[Dict[str, str]]) -> None: ...

    def get_stream(self, url: str, start_byte: int = 0) -> requests.Response:
        # open streaming response (usable as a context manager); Range header
        # when start_byte > 0; uses self.timeout / self.verify
```

- `HTTPClient` does **no** retry/fallback/state logic.
- `SmartDownloader.__init__` gains `client: Optional[HTTPClient] = None` (default `HTTPClient()`); session/UA setup removed.
- `set_proxy` delegates to `self.client.set_proxy`.
- `_try_download` uses `with self.client.get_stream(url, start_byte=start_byte) as response:`; everything downstream stays in `SmartDownloader`. `requests` stays imported in `downloader.py` only for the `except requests.exceptions.*` branches (same exceptions must propagate from `get_stream`).
- Public API and all tunable constants (`DOWNLOAD_CHUNK_SIZE`, `MIN_SPEED_THRESHOLD`, `MAX_RETRIES`, etc.) stay in `downloader.py`. Behavior is byte-for-byte identical.

## What needs fixing

1. Create `linua_updater/core/clients.py` with `HTTPClient` per the signature above.
2. `downloader.py`: add `client` param, drop `self.session`/UA setup, delegate `set_proxy`, switch `_try_download` to `get_stream`.
3. Backward compat: `HTTPClient.session` is the canonical session access; `SmartDownloader` no longer exposes `.session`.

## Tests

- Rework `tests/test_downloader.py` helpers (`_make_downloader`, `FakeSession`, `:85` monkeypatch of `dl_mod.requests.Session`) to inject `HTTPClient(session=fake)` into `SmartDownloader`. Existing tests must pass with unchanged behavior.
- Add `tests/test_clients.py`: UA header set; `set_proxy` set/clear; `get_stream` sends `Range: bytes=<n>-` only when `start_byte > 0`, plus `stream=True`/`timeout`/`verify`; `Timeout`/`ConnectionError` propagate.
- Run `./scripts/check.sh`. Mind `pyproject.toml` (`line-length = 160`, explicit generic type args).

## Docs

- `docs/architecture.md`: core/ listing (`:34-36`) and `SmartDownloader` row (`:108`) — note transport lives in `HTTPClient` (`core/clients.py`).
- `tasks/refactoring-plan.md`: add `core/clients.py → HTTPClient` to the class→module map.
