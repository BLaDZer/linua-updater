import os
import subprocess
import threading
import time

import pytest

from linua_updater.constants import MB
from linua_updater.core.clients import Aria2TorrentClient, TorrentClient
from linua_updater.core.torrent_downloader import TorrentDownloader


class FakeProcess:
    def __init__(self, lines=None, exit_code=0):
        self.lines = lines or []
        self.exit_code = exit_code
        self._idx = 0
        self._lock = threading.Lock()
        self._terminated = False

    def poll(self):
        with self._lock:
            if self._idx >= len(self.lines):
                return self.exit_code
            return None

    @property
    def stdout(self):
        return self

    def readline(self):
        with self._lock:
            if self._idx < len(self.lines):
                line = self.lines[self._idx]
                self._idx += 1
                return line
            return ""

    @property
    def stderr(self):
        return self

    def wait(self):
        return self.exit_code

    def terminate(self):
        with self._lock:
            self._terminated = True

    def kill(self):
        with self._lock:
            self._terminated = True


class BlockingFakeProcess(FakeProcess):
    def __init__(self, gate, lines=None, exit_code=0):
        super().__init__(lines, exit_code)
        self._gate = gate

    def poll(self):
        if not self._gate.is_set():
            return None  # still "running" until released
        return super().poll()

    def readline(self):
        self._gate.wait(timeout=5)
        return super().readline()


class FakeFinder:
    def __init__(self, path="/fake/aria2c"):
        self._path = path

    def find(self):
        return self._path


class FakeLogger:
    def log(self, *args, **kwargs):
        pass


class RecordingLogger:
    def __init__(self):
        self.records = []

    def log(self, text, level="INFO"):
        self.records.append((text, level))


def make_dl(logger, aria2_path, cleanup=True):
    return TorrentDownloader(
        logger,
        Aria2TorrentClient(logger, aria2_path=aria2_path),
        cleanup=cleanup,
    )


@pytest.fixture
def patch_finder(monkeypatch):
    import linua_updater.core.clients as clients_mod

    monkeypatch.setattr(clients_mod, "Aria2Finder", FakeFinder)


class StubTorrentClient(TorrentClient):
    def __init__(self, available=True):
        self.available = available
        self.starts = 0
        self.ticks = []
        self.exits = []
        self.stopped = 0
        self.aborted = 0
        self.block = threading.Event()
        self.block.set()
        self.started = threading.Event()
        self._reads = 0

    @property
    def name(self):
        return "stub"

    def is_available(self):
        return self.available

    def start(self, magnet, out_dir):
        self.starts += 1

    def read_progress(self):
        self._reads += 1
        if self._reads == 1:
            self.started.set()
        if not self.block.is_set():
            self.block.wait(timeout=5)
        if self.ticks:
            return self.ticks.pop(0)
        return None

    def stop(self):
        self.stopped += 1

    def abort(self):
        self.aborted += 1

    def wait_exit(self):
        if self.exits:
            return self.exits.pop(0)
        return 0


def test_download_success_cleans_artifacts(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProcess(
        lines=["[#hash123 10MiB/10MiB(100%) CN:1 DL:1.0MiB]"],
        exit_code=0,
    ))
    out_dir = str(tmp_path / "out")
    dl = make_dl(FakeLogger(), str(aria2c), cleanup=True)
    ok, result = dl.download("magnet:?xt=foo", out_dir, expected_size=10 * MB)
    assert ok is True
    assert isinstance(result, list)


def test_download_logs_start_and_complete(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProcess(
        lines=["[#hash123 10MiB/10MiB(100%) CN:1 DL:1.0MiB]"],
        exit_code=0,
    ))
    out_dir = str(tmp_path / "out")
    dl = make_dl(RecordingLogger(), str(aria2c), cleanup=True)
    ok, result = dl.download("magnet:?xt=foo", out_dir, dlc_name="EP01")
    assert ok is True
    texts = [t for t, _ in dl.logger.records]
    assert any("Starting torrent download: EP01 (magnet:?xt=foo)" in t for t in texts)
    assert any("Torrent download complete: EP01" in t for t in texts)


def test_missing_aria2_logs_warning(tmp_path):
    out_dir = str(tmp_path / "out")
    dl = make_dl(RecordingLogger(), str(tmp_path / "no" / "such" / "aria2c"))
    ok, result = dl.download("magnet:?xt=foo", out_dir)
    assert ok is False
    assert any(
        "no available torrent client found" in t.lower()
        for t, lv in dl.logger.records
        if lv == "WARNING"
    )


def test_nonzero_exit_logs_error(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProcess(exit_code=1))
    out_dir = str(tmp_path / "out")
    dl = make_dl(RecordingLogger(), str(aria2c), cleanup=True)
    ok, result = dl.download("magnet:?xt=foo", out_dir)
    assert ok is False
    assert any(
        "aria2 exit code 1" in t
        for t, lv in dl.logger.records
        if lv == "ERROR"
    )


def test_cancel_logs_warning(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    barrier = threading.Event()

    def slow_process(*a, **kw):
        barrier.wait(timeout=5)
        return FakeProcess(lines=[], exit_code=0)

    monkeypatch.setattr(subprocess, "Popen", slow_process)
    out_dir = str(tmp_path / "out")
    dl = make_dl(RecordingLogger(), str(aria2c), cleanup=True)

    def cancel_later():
        time.sleep(0.1)
        dl.cancel()

    t = threading.Thread(target=cancel_later)
    t.start()
    ok, result = dl.download("magnet:?xt=foo", out_dir)
    t.join(timeout=2)
    assert ok is False
    assert result == "Cancelled"
    assert any(
        "Torrent download cancelled" in t
        for t, lv in dl.logger.records
        if lv == "WARNING"
    )


def test_download_progress_callback(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    events = []

    def cb(progress, downloaded, total):
        events.append((progress, downloaded, total))

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProcess(
        lines=[
            "[#hash123 10MiB/100MiB(10%) CN:1 DL:1.0MiB]",
            "[#hash123 50MiB/100MiB(50%) CN:1 DL:1.0MiB]",
            "[#hash123 100MiB/100MiB(100%) CN:1 DL:1.0MiB]",
        ],
        exit_code=0,
    ))
    out_dir = str(tmp_path / "out")
    dl = make_dl(FakeLogger(), str(aria2c), cleanup=True)
    dl.set_progress_callback(cb)
    ok, result = dl.download("magnet:?xt=foo", out_dir, expected_size=100 * MB)
    assert ok is True
    assert len(events) >= 2


def test_download_cancelled_before_start_returns_cancelled(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    popen_calls = []

    def capturing_popen(*a, **kw):
        popen_calls.append(a)
        return FakeProcess(lines=["[#hash123 100MiB/100MiB(100%) CN:1 DL:1.0MiB]"], exit_code=0)

    monkeypatch.setattr(subprocess, "Popen", capturing_popen)
    out_dir = str(tmp_path / "out")
    dl = make_dl(FakeLogger(), str(aria2c), cleanup=True)
    dl.cancel()  # cancel lands before download() starts
    ok, result = dl.download("magnet:?xt=foo", out_dir)
    assert ok is False
    assert result == "Cancelled"
    assert popen_calls == []


def test_download_cancel_returns_cancelled(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    barrier = threading.Event()

    def slow_process(*a, **kw):
        barrier.wait(timeout=5)
        return FakeProcess(lines=[], exit_code=0)

    monkeypatch.setattr(subprocess, "Popen", slow_process)
    out_dir = str(tmp_path / "out")
    dl = make_dl(FakeLogger(), str(aria2c), cleanup=True)

    def cancel_later():
        time.sleep(0.1)
        dl.cancel()

    t = threading.Thread(target=cancel_later)
    t.start()
    ok, result = dl.download("magnet:?xt=foo", out_dir)
    t.join(timeout=2)
    assert ok is False
    assert result == "Cancelled"


def test_download_nonzero_exit(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProcess(exit_code=1))
    out_dir = str(tmp_path / "out")
    dl = make_dl(FakeLogger(), str(aria2c), cleanup=True)
    ok, result = dl.download("magnet:?xt=foo", out_dir)
    assert ok is False
    assert "exit code 1" in result


def test_download_pause_resume_restarts(tmp_path, patch_finder, monkeypatch):
    """Pause terminates the process; resume restarts aria2c and completes."""
    gate = threading.Event()
    started = threading.Event()
    call_count = [0]

    def counting_popen(*a, **kw):
        call_count[0] += 1
        if call_count[0] == 1:
            started.set()
            return BlockingFakeProcess(gate,
                lines=["[#hash 10MiB/100MiB(10%) CN:1 DL:1.0MiB]"], exit_code=0)
        return FakeProcess(lines=["[#hash 100MiB/100MiB(100%) CN:1 DL:1.0MiB]"], exit_code=0)

    monkeypatch.setattr(subprocess, "Popen", counting_popen)
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    out_dir = str(tmp_path / "out")
    dl = make_dl(FakeLogger(), str(aria2c), cleanup=True)

    result = [None]

    def run_download():
        result[0] = dl.download("magnet:?xt=foo", out_dir, expected_size=100 * MB)

    t = threading.Thread(target=run_download)
    t.start()
    assert started.wait(timeout=2)  # first Popen is running, blocked on readline

    dl.pause()   # sets _paused and terminates the process
    gate.set()   # unblock the fake process (EOF / next summary line after terminate)
    time.sleep(0.1)
    dl.resume()  # clears _paused → download() restarts aria2c internally
    t.join(timeout=5)

    assert result[0][0] is True
    assert call_count[0] == 2  # aria2c was re-invoked (restarted) after resume


def test_stub_client_missing_aria2(tmp_path):
    client = StubTorrentClient(available=False)
    dl = TorrentDownloader(RecordingLogger(), client, cleanup=True)
    ok, result = dl.download("magnet:?xt=foo", str(tmp_path / "out"))
    assert ok is False
    assert "no available torrent client found" in result
    assert any(
        "no available torrent client found" in t.lower()
        for t, lv in dl.logger.records
        if lv == "WARNING"
    )
    assert client.starts == 0


def test_stub_client_progress_dedupe(tmp_path):
    client = StubTorrentClient()
    client.ticks = [
        (10.0, 10 * MB, 0),
        (10.0, 20 * MB, 0),
        (50.0, 50 * MB, 0),
        (50.0, 50 * MB, 0),
        (100.0, 100 * MB, 0),
    ]
    events = []
    dl = TorrentDownloader(FakeLogger(), client, cleanup=True)
    dl.set_progress_callback(lambda p, d, t: events.append(p))
    out_dir = str(tmp_path / "out")
    ok, result = dl.download("magnet:?xt=foo", out_dir, expected_size=100 * MB)
    assert ok is True
    assert isinstance(result, list)
    assert events == [0, 10.0, 10.0, 50.0, 100.0]  # repeated 50% was deduped


def test_stub_client_restart_loop(tmp_path):
    """Pause/resume with a stub client drives the restart loop without subprocess."""
    client = StubTorrentClient()
    client.block.clear()
    client.ticks = [(10.0, 10 * MB, 0), (100.0, 100 * MB, 0)]
    dl = TorrentDownloader(FakeLogger(), client, cleanup=True)
    out_dir = str(tmp_path / "out")

    result = [None]

    def run():
        result[0] = dl.download("magnet:?xt=foo", out_dir, expected_size=100 * MB)

    t = threading.Thread(target=run)
    t.start()
    assert client.started.wait(timeout=2)

    dl.pause()      # sets _paused; the blocked read_progress returns once released
    client.block.set()
    time.sleep(0.1)
    dl.resume()     # clears _paused → download() restarts the client
    t.join(timeout=5)

    assert result[0][0] is True
    assert client.starts == 2
    assert client.stopped == 1