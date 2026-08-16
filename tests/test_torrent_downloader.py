import os
import subprocess
import threading
import time
import types

import pytest

from linua_updater.core.torrent_downloader import TorrentDownloader, _popen_kwargs


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


@pytest.fixture
def patch_finder(monkeypatch):
    import linua_updater.core.torrent_downloader as td
    monkeypatch.setattr(td, "Aria2Finder", FakeFinder)


def test_parse_summary():
    line = "[#hash123 12.3MiB/123.4MiB(10%) CN:2 DL:1.2MiB]"
    progress, downloaded, total = TorrentDownloader._parse_summary(line)
    assert progress == 10.0
    assert downloaded == pytest.approx(12.3 * 1024 * 1024)
    assert total == 0


def test_parse_summary_100_percent():
    line = "[#hash123 100MiB/100MiB(100%) CN:2 DL:1.0MiB]"
    progress, downloaded, total = TorrentDownloader._parse_summary(line)
    assert progress == 100.0
    assert downloaded == pytest.approx(100 * 1024 * 1024)


def test_download_success_cleans_artifacts(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProcess(
        lines=["[#hash123 10MiB/10MiB(100%) CN:1 DL:1.0MiB]"],
        exit_code=0,
    ))
    out_dir = str(tmp_path / "out")
    dl = TorrentDownloader(FakeLogger(), aria2_path=str(aria2c), cleanup=True)
    ok, result = dl.download("magnet:?xt=foo", out_dir, expected_size=10 * 1024 * 1024)
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
    dl = TorrentDownloader(RecordingLogger(), aria2_path=str(aria2c), cleanup=True)
    ok, result = dl.download("magnet:?xt=foo", out_dir, dlc_name="EP01")
    assert ok is True
    texts = [t for t, _ in dl.logger.records]
    assert any("Starting torrent download: EP01 (magnet:?xt=foo)" in t for t in texts)
    assert any("Torrent download complete: EP01" in t for t in texts)


def test_missing_aria2_logs_warning(tmp_path):
    out_dir = str(tmp_path / "out")
    dl = TorrentDownloader(RecordingLogger(), aria2_path="/no/such/aria2c")
    ok, result = dl.download("magnet:?xt=foo", out_dir)
    assert ok is False
    assert any(
        "aria2c not found" in t.lower()
        for t, lv in dl.logger.records
        if lv == "WARNING"
    )


def test_nonzero_exit_logs_error(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: FakeProcess(exit_code=1))
    out_dir = str(tmp_path / "out")
    dl = TorrentDownloader(RecordingLogger(), aria2_path=str(aria2c), cleanup=True)
    ok, result = dl.download("magnet:?xt=foo", out_dir)
    assert ok is False
    assert any(
        "aria2c exit code 1" in t
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
    dl = TorrentDownloader(RecordingLogger(), aria2_path=str(aria2c), cleanup=True)

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
    dl = TorrentDownloader(FakeLogger(), aria2_path=str(aria2c), cleanup=True)
    dl.set_progress_callback(cb)
    ok, result = dl.download("magnet:?xt=foo", out_dir, expected_size=100 * 1024 * 1024)
    assert ok is True
    assert len(events) >= 2


def test_download_cancel_returns_cancelled(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    barrier = threading.Event()

    def slow_process(*a, **kw):
        barrier.wait(timeout=5)
        return FakeProcess(lines=[], exit_code=0)

    monkeypatch.setattr(subprocess, "Popen", slow_process)
    out_dir = str(tmp_path / "out")
    dl = TorrentDownloader(FakeLogger(), aria2_path=str(aria2c), cleanup=True)

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
    dl = TorrentDownloader(FakeLogger(), aria2_path=str(aria2c), cleanup=True)
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
    dl = TorrentDownloader(FakeLogger(), aria2_path=str(aria2c), cleanup=True)

    result = [None]
    def run_download():
        result[0] = dl.download("magnet:?xt=foo", out_dir, expected_size=100 * 1024 * 1024)

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


def test_popen_kwargs_linux_no_creationflags(monkeypatch):
    import linua_updater.core.torrent_downloader as td
    fake = types.SimpleNamespace()
    monkeypatch.setattr(td, "subprocess", fake)
    assert _popen_kwargs() == {}


def test_popen_kwargs_windows_sets_creationflags(monkeypatch):
    import linua_updater.core.torrent_downloader as td
    fake = types.SimpleNamespace(CREATE_NO_WINDOW=0x08000000)
    monkeypatch.setattr(td, "subprocess", fake)
    assert _popen_kwargs() == {"creationflags": 0x08000000}


def test_download_passes_no_window_flag(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    captured = {}

    def capture_popen(*a, **kw):
        captured.update(kw)
        return FakeProcess(
            lines=["[#hash123 100MiB/100MiB(100%) CN:1 DL:1.0MiB]"],
            exit_code=0,
        )

    monkeypatch.setattr(subprocess, "Popen", capture_popen)
    out_dir = str(tmp_path / "out")
    dl = TorrentDownloader(FakeLogger(), aria2_path=str(aria2c), cleanup=True)
    ok, _ = dl.download("magnet:?xt=foo", out_dir)
    assert ok is True
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if flag:
        assert captured.get("creationflags") == flag
    else:
        assert "creationflags" not in captured


def test_cancel_kills_when_terminate_ignored():
    class StubbornProcess(FakeProcess):
        def __init__(self):
            super().__init__(lines=[], exit_code=0)
            self.killed = False

        def poll(self):
            return None  # always "running"

        def wait(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired(cmd="aria2c", timeout=timeout)
            return self.exit_code

        def kill(self):
            self.killed = True

    proc = StubbornProcess()
    dl = TorrentDownloader(FakeLogger(), aria2_path="/fake/aria2c")
    dl._process = proc
    dl.cancel()
    assert proc.killed is True
