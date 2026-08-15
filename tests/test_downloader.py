import threading
import time

import pytest

import linua_updater.core.downloader as dl_mod
from linua_updater.core.downloader import SmartDownloader


class FakeLogger:
    def log(self, *args, **kwargs):
        pass


class FakeResponse:
    def __init__(self, chunks=None, headers=None, status_code=200):
        self.chunks = list(chunks or [])
        self.headers = {"content-length": str(sum(len(c) for c in self.chunks))}
        if headers:
            self.headers.update(headers)
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        return iter(self.chunks)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.headers = {}
        self.proxies = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class FakeDiagnostics:
    def __init__(self):
        self.working_proxies = [
            {"http": "http://127.0.0.1:1080", "https": "http://127.0.0.1:1080"}
        ]


class AdvancingTime:
    def __init__(self, step=1.1, start=1000.0):
        self.now = start
        self.step = step

    def time(self):
        self.now += self.step
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(dl_mod.time, "sleep", lambda _: None)


def _make_downloader(monkeypatch, *responses):
    session = FakeSession(list(responses))
    monkeypatch.setattr(dl_mod.requests, "Session", lambda: session)
    return SmartDownloader(FakeLogger()), session


def test_cancel_prevents_write(tmp_path, monkeypatch):
    dl, session = _make_downloader(monkeypatch, FakeResponse(chunks=[b"data"]))
    dl._cancelled = True
    out = tmp_path / "file.zip"
    ok, msg = dl._try_download("https://example.com/file.zip", str(out), str(tmp_path / "file.zip.part"))
    assert not ok
    assert msg == "Cancelled"


def test_pause_blocks_until_resume(tmp_path, monkeypatch):
    dl, session = _make_downloader(monkeypatch, FakeResponse(chunks=[b"a", b"b", b"c"]))
    dl.pause()
    out = tmp_path / "file.zip"
    result = []

    def run():
        result.append(dl._try_download("https://example.com/file.zip", str(out), str(tmp_path / "file.zip.part")))

    t = threading.Thread(target=run, daemon=True)
    t.start()
    try:
        time.sleep(0.1)
        SmartDownloader.resume(dl)
    finally:
        t.join(timeout=5)
    assert not t.is_alive()
    assert result == [(True, "OK")]


def test_resume_uses_range_header_and_appends(tmp_path, monkeypatch):
    dl, session = _make_downloader(monkeypatch, FakeResponse(chunks=[b"CD"]))
    part = tmp_path / "file.zip.part"
    part.write_bytes(b"AB")
    out = tmp_path / "file.zip"
    ok, msg = dl._try_download("https://example.com/file.zip", str(out), str(part), start_byte=2)
    assert ok
    assert msg == "OK"
    assert out.read_bytes() == b"ABCD"
    assert session.calls[0][1]["headers"]["Range"] == "bytes=2-"


def test_retry_after_connection_error(tmp_path, monkeypatch, no_sleep):
    dl, session = _make_downloader(monkeypatch, FakeResponse(chunks=[b"x"]))
    real = dl._try_download
    state = {"n": 0}

    def flaky(*args, **kwargs):
        state["n"] += 1
        if state["n"] == 1:
            raise ConnectionError("boom")
        return real(*args, **kwargs)

    monkeypatch.setattr(dl, "_try_download", flaky)
    out = tmp_path / "file.zip"
    ok, msg = dl._try_download_with_retry("https://example.com/file.zip", str(out), str(tmp_path / "file.zip.part"))
    assert ok
    assert msg == "OK"
    assert state["n"] == 2


def test_size_mismatch_detected(tmp_path, monkeypatch):
    dl, session = _make_downloader(monkeypatch, FakeResponse(chunks=[b"abcd"], headers={"content-length": "100"}))
    out = tmp_path / "file.zip"
    ok, msg = dl._try_download("https://example.com/file.zip", str(out), str(tmp_path / "file.zip.part"))
    assert not ok
    assert "Size mismatch" in msg


def test_file_too_large_rejected(tmp_path, monkeypatch):
    dl, session = _make_downloader(
        monkeypatch,
        FakeResponse(chunks=[b"x"], headers={"content-length": str(11 * 1024 * 1024 * 1024)}),
    )
    out = tmp_path / "file.zip"
    ok, msg = dl._try_download("https://example.com/file.zip", str(out), str(tmp_path / "file.zip.part"))
    assert not ok
    assert msg == "File too large (>10GB)"


def test_speed_threshold_aborts(tmp_path, monkeypatch):
    dl, session = _make_downloader(monkeypatch, FakeResponse(chunks=[b"a"] * 10))
    monkeypatch.setattr(dl_mod, "time", AdvancingTime())
    out = tmp_path / "file.zip"
    ok, msg = dl._try_download("https://example.com/file.zip", str(out), str(tmp_path / "file.zip.part"))
    assert not ok
    assert msg == "Speed too slow, trying alternative"


def test_mirror_fallback(tmp_path, monkeypatch, no_sleep):
    dl, session = _make_downloader(
        monkeypatch,
        FakeResponse(status_code=500),
        FakeResponse(status_code=500),
        FakeResponse(status_code=500),
        FakeResponse(chunks=[b"mirror data"]),
    )
    out = tmp_path / "file.zip"
    ok, msg = dl.download("https://github.com/foo/file.zip", str(out))
    assert ok
    assert msg == "Downloaded via mirror"
    assert "gh-proxy.com" in session.calls[-1][0]


def test_proxy_fallback_uses_working_proxies(tmp_path, monkeypatch, no_sleep):
    dl, session = _make_downloader(
        monkeypatch,
        FakeResponse(status_code=500),
        FakeResponse(status_code=500),
        FakeResponse(status_code=500),
        FakeResponse(chunks=[b"proxied"]),
    )
    dl.diagnostics = FakeDiagnostics()
    out = tmp_path / "file.zip"
    ok, msg = dl.download("https://github.com/foo/file.zip", str(out))
    assert ok
    assert msg == "Downloaded via proxy"
    assert session.proxies


def test_set_proxy_clears_proxies(monkeypatch):
    dl, session = _make_downloader(monkeypatch)
    dl.set_proxy({"http": "http://127.0.0.1:8080"})
    assert session.proxies
    dl.set_proxy(None)
    assert session.proxies == {}
